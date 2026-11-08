"""Check notebook numerical definitions without executing its I/O cells."""
from itertools import product
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
import pytest

from congress_scorecard import (
    brier_skill, load_inputs, match_sample, paired_difference, select_sample,
    vote_share_score,
)


@pytest.fixture(scope="module")
def helpers():
    notebook = nbformat.read(Path(__file__).resolve().parents[1] /
                             "notebooks/02_forecast_accuracy.ipynb", as_version=4)
    namespace = {}
    for cell in notebook.cells:
        if set(cell.metadata.get("tags", [])) & {"imports", "numerical-helpers"}:
            exec(compile(cell.source, "forecast_accuracy_helpers", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("d,expected", [([], None), ([0, 0], 1), ([1, 1], .5),
                                       ([1, -1], 1), ([1, 1, 0], .5)])
def test_exact_sign_flip(helpers, d, expected):
    result = helpers["exact_sign_flip"](d)
    assert result["p_two_sided"] == expected
    assert result["n_nonzero"] == np.count_nonzero(d)
    assert result["n_pairs"] == len(d)


def test_primary_contrast_independent_loop_and_sign_patterns(helpers):
    f = select_sample(load_inputs(snapshot="current-partial").senate, "non_solid")
    r = paired_difference(f, "p_kalshi", "p_model_mean")
    rows = f.loc[r.race_ids]
    differences = np.array([(float(x.p_kalshi) - float(x.y)) ** 2 -
                            ((float(x.p_economist) + float(x.p_votehub)) / 2 - float(x.y)) ** 2
                            for x in rows.itertuples()])
    assert (r.n_planned, r.n_eligible) == (15, 13)
    assert r.value == pytest.approx(differences.mean(), abs=1e-14)
    signed = np.array(list(product([-1, 1], repeat=len(differences)))) @ differences
    expected = np.mean(np.abs(signed) >= abs(differences.sum()) - 1e-12)
    assert helpers["exact_sign_flip"](differences)["p_two_sided"] == expected


def test_bootstrap_is_paired_and_reproducible(helpers):
    first, second = np.array([1., 3., 4.]), np.array([.5, 2., 5.])
    result = helpers["bootstrap_difference"](first - second, draws=10000)
    idx = np.random.default_rng(20261104).integers(0, 3, size=(10000, 3))
    expected = (first[idx] - second[idx]).mean(axis=1)
    np.testing.assert_array_equal(result["draws"], expected)
    np.testing.assert_allclose([result["low"], result["high"]], np.quantile(expected, [.025, .975]))
    assert helpers["bootstrap_difference"]([])["low"] is None
    one = helpers["bootstrap_difference"]([.2])
    assert one["low"] == one["high"] == .2


def test_paired_influence_and_degenerate_samples(helpers):
    f = load_inputs(snapshot="synthetic-complete").senate
    summary, rows, loo, _ = helpers["paired_analysis"](f, "p_kalshi", "p_model_mean")
    assert len(loo) == len(rows) == 35
    for r in loo.itertuples():
        manual = paired_difference(f.drop(index=r.race_id), "p_kalshi", "p_model_mean")
        assert r.leave_one_out == pytest.approx(manual.value)
    empty = f.copy()
    empty["call_eligible"] = False
    summary, _, loo, draws = helpers["paired_analysis"](empty, "p_kalshi", "p_model_mean")
    assert summary["value"] is None and loo.empty and len(draws) == 0
    assert helpers["paired_analysis"](f.iloc[:1], "p_kalshi", "p_model_mean")[2].empty


def test_copula_margins_endpoints_and_binary_correlation(helpers):
    shared, residual = helpers["latent_draws"](5, draws=100000)
    p = np.array([0., .01, .5, .9, 1.])
    for rho in [0, .1, .25, .5, 1]:
        y = helpers["copula_outcomes"](p, rho, shared, residual)
        np.testing.assert_allclose(y.mean(axis=0), p, atol=.005)
        assert not y[:, 0].any() and y[:, 4].all()
    y = helpers["copula_outcomes"](p, .5, shared, residual)
    # Latent correlation .5 does not imply binary correlation .5.
    assert abs(np.corrcoef(y[:, 1], y[:, 2])[0, 1] - .5) > .1
    with pytest.raises(ValueError):
        helpers["copula_outcomes"]([1.1], 0, shared, residual[:, :1])


def test_simulation_matches_analytic_gap_and_variance(helpers):
    f = load_inputs(snapshot="current-partial").senate
    shared, residual = helpers["latent_draws"](len(f), draws=100000)
    p, k = f.p_model_mean.to_numpy(), f.p_kalshi.to_numpy()
    expected_mean = np.mean((k - p) ** 2)
    expected_sd = np.sqrt(np.sum(4 * (p - k) ** 2 * p * (1 - p))) / len(f)
    independent_sd = None
    for rho in [0, .1, .25, .5]:
        y = helpers["copula_outcomes"](p, rho, shared, residual)
        gaps = ((y - k) ** 2 - (y - p) ** 2).mean(axis=1)
        assert abs(gaps.mean() - expected_mean) < 5 * gaps.std() / np.sqrt(len(y))
        if rho == 0:
            independent_sd = gaps.std()
            assert independent_sd == pytest.approx(expected_sd, rel=.02)
        if rho == .5:
            assert gaps.std() > independent_sd


def test_spiegelhalter_and_zero_variance(helpers):
    p, y = np.array([.2, .7, .9]), np.array([0, 1, 0])
    numerator = np.sum((y - p) ** 2 - p * (1 - p))
    variance = np.sum((1 - 2 * p) ** 2 * p * (1 - p))
    assert helpers["spiegelhalter"](p, y) == pytest.approx(numerator / np.sqrt(variance))
    assert helpers["spiegelhalter"]([.5, .5], [0, 1]) is None
    assert helpers["spiegelhalter"]([], []) is None


def test_share_gates_common_polls_and_decomposition():
    partial = load_inputs(snapshot="current-partial").senate
    complete = load_inputs(snapshot="synthetic-complete").senate
    for source in ["economist", "votehub", "rcp", "silver"]:
        assert vote_share_score(partial, "share_" + source).n_eligible == 0
    a = vote_share_score(complete, "share_rcp", peers=("share_silver",), metric="bias")
    b = vote_share_score(complete, "share_silver", peers=("share_rcp",), metric="bias")
    assert a.race_ids == b.race_ids and a.n_eligible > 0
    for r in [a, b]:
        np.testing.assert_allclose(r.per_race.error, r.value + r.per_race.centered_error)
        assert np.dot(r.per_race.centered_error, r.per_race._weight) == pytest.approx(0, abs=1e-15)


def test_clipping_matching_skill_and_mapping_ranks(helpers):
    f = load_inputs(snapshot="synthetic-complete").senate
    f.loc[f.index[0], "p_kalshi"] = 0
    f.loc[f.index[0], "y"] = 1
    from congress_scorecard import probability_score
    assert np.isinf(probability_score(f, "p_kalshi", metric="log", clip=False).value)
    assert np.isfinite(probability_score(f, "p_kalshi", metric="log").value)
    f.loc[f.index[1], "p_cook_primary"] = np.nan
    skill = brier_skill(f, "p_kalshi", "p_cook_primary")
    matched = match_sample(f, ["p_kalshi", "p_cook_primary"]).rows
    source_loss = ((matched.p_kalshi - matched.y) ** 2).mean()
    reference_loss = ((matched.p_cook_primary - matched.y) ** 2).mean()
    assert skill.value == pytest.approx(1 - source_loss / reference_loss)
    for mapping in ["primary", "senate", "wide"]:
        expected = {name: probability_score(f, col).value for col, name in helpers["SOURCES"].items() if name != "Cook"}
        expected["Cook"] = probability_score(f, "p_cook_" + mapping).value
        pd.testing.assert_series_equal(helpers["rank_cook_scores"](f, mapping), pd.Series(expected).rank(method="min"))


def test_longshots_one_event_per_race_and_ties(helpers):
    f = load_inputs(snapshot="synthetic-complete").senate
    r = helpers["longshot_rows"](f)
    assert len(r) == 35 and r.index.is_unique
    assert r.loc[r.tie, "longshot_won"].isna().all()
    assert r.loc[~r.tie, "band"].notna().all()
    assert r.loc[~r.tie, "longshot_probability"].lt(.5).all()


def test_calibration_empty_and_single_eligible_race(helpers):
    frame = load_inputs(snapshot="synthetic-complete").senate
    helpers["full_frame"] = frame
    shared, residual = helpers["latent_draws"](len(frame))
    empty = frame.copy()
    empty["call_eligible"] = False
    result = helpers["calibration"](empty, "p_kalshi", shared, residual)
    assert result.iloc[0].status == "unavailable" and result.iloc[0].n_eligible == 0
    result = helpers["calibration"](frame.iloc[:1], "p_kalshi", shared, residual)
    assert len(result) == 4 and result.n_eligible.eq(1).all()


def test_cook_rank_changes_and_ties_are_retained(helpers):
    frame = load_inputs(snapshot="synthetic-complete").senate.copy()
    frame["p_cook_primary"] = 1 - frame.y
    frame["p_cook_wide"] = frame.y
    frame["p_kalshi"] = frame.y
    primary = helpers["rank_cook_scores"](frame, "primary")
    wide = helpers["rank_cook_scores"](frame, "wide")
    assert primary["Cook"] > wide["Cook"]
    assert wide["Cook"] == wide["Kalshi"] == 1
