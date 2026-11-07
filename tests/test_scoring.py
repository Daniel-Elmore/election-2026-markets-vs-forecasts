import numpy as np
import pandas as pd
import pytest

from congress_scorecard import (brier_loss, brier_skill, calls_correct, cook_probability,
    expected_wins, favorite, house_expected_seats, log_loss, match_sample,
    normalize_probabilities, paired_difference, probability_score, select_sample,
    two_candidate_share, vote_share_score)


def frame():
    return pd.DataFrame({"first": [.8, .2, .5], "second": [.6, .1, .5],
        "y": [1., 0., np.nan], "call_eligible": [True, True, False],
        "call_exclusion": ["", "", "pending"], "volume": [1., 3., 100.]},
        index=pd.Index(["A", "B", "C"], name="race_id"))


@pytest.mark.parametrize("mapping,expected", [("primary", [.99, .97, .94]), ("senate", [.99, .978, .981]), ("wide", [.99, .9, .7])])
def test_cook_mappings_and_orientation(mapping, expected):
    for bucket, p in zip(["Solid", "Likely", "Lean"], expected):
        assert cook_probability(bucket + " D", mapping=mapping) == p
        assert cook_probability(bucket + " R", mapping=mapping) == pytest.approx(1 - p)
        assert cook_probability(bucket + " R", mapping=mapping, a_party="Independent") == pytest.approx(1 - p)
        assert cook_probability(bucket + " R", mapping=mapping, a_party="Republican") == p
    assert cook_probability("Toss-Up", mapping=mapping) == .5


def test_brier_and_clipping_are_distinct():
    assert brier_loss([1., 0.], [0., 1.]).tolist() == [1., 1.]
    assert log_loss([1., 0.], [0., 1.]).tolist() == pytest.approx([-np.log(.01)] * 2)
    assert np.isinf(log_loss([1., 0.], [0., 1.], clip=False)).all()
    assert log_loss([1., 0.], [1., 0.], clip=False).tolist() == [0., 0.]


def test_missing_and_invalid_binary_inputs():
    assert np.isnan(log_loss([.5], [np.nan]).iloc[0])
    with pytest.raises(ValueError):
        brier_loss([1.1], [1])
    with pytest.raises(ValueError):
        log_loss([.5], [.2])
    with pytest.raises(ValueError):
        brier_loss(pd.Series([.5], index=["a"]), pd.Series([1], index=["b"]))


def test_two_candidate_share_and_overround():
    assert two_candidate_share([49.2], [47.8], scale=100).iloc[0] == pytest.approx(49.2 / 97)
    assert normalize_probabilities([.71], [.3]).iloc[0] == pytest.approx(.71 / 1.01)
    assert np.isnan(normalize_probabilities([0], [0]).iloc[0])
    assert np.isnan(two_candidate_share([np.nan], [.5]).iloc[0])
    with pytest.raises(ValueError):
        two_candidate_share([.9], [.9])


def test_exact_half_is_abstention():
    work = frame()
    work["call_eligible"] = True
    work["y"] = [1, 0, 1]
    result = calls_correct(work, "first")
    assert result.value == {"correct": 2, "calls_made": 2, "abstentions": 1, "accuracy": 1.}
    assert favorite([.5, np.nan, .50001, .49999]).iloc[2:].tolist() == [1, 0]


def test_missing_outcomes_and_weight_normalization():
    work = frame()
    result = probability_score(work, "first", weights="volume")
    assert result.n_eligible == 2 and result.n_planned == 3
    assert result.race_ids == ["A", "B"]
    assert result.weight_sum == 4
    assert result.value == pytest.approx(.04)
    assert result.per_race._weight.tolist() == [.25, .75]
    assert result.exclusions["C"] == ["missing y", "pending"]


def test_pairing_and_skill_use_same_rows_and_weights():
    work = frame()
    work.loc["B", "second"] = np.nan
    result = paired_difference(work, "first", "second", weights="volume")
    assert result.race_ids == ["A"]
    assert result.value == pytest.approx(.04 - .16)
    assert brier_skill(work, "first", "second", weights="volume").value == pytest.approx(.75)
    work = work.iloc[::-1]
    assert paired_difference(work, "first", "second").value == pytest.approx(-.12)


@pytest.mark.parametrize("weights", [[-1, 3, 100], [np.inf, 3, 100], [0, 0, 100]])
def test_bad_weights_rejected(weights):
    work = frame()
    work["volume"] = weights
    with pytest.raises(ValueError):
        probability_score(work, "first", weights="volume")


def test_zero_weight_does_not_produce_nan_from_infinity():
    work = frame().iloc[:2].copy()
    work["first"] = [0, .2]
    work["volume"] = [0, 1]
    result = probability_score(work, "first", metric="log", clip=False, weights="volume")
    assert result.value == pytest.approx(-np.log(.8))


def test_missing_weights_exclude_and_renormalize():
    work = frame()
    work.loc["A", "volume"] = np.nan
    result = probability_score(work, "first", weights="volume")
    assert result.race_ids == ["B"] and result.per_race._weight.sum() == 1


def test_empty_eligible_and_zero_reference():
    work = frame()
    work["call_eligible"] = False
    result = probability_score(work, "first")
    assert result.value is None and result.status == "unavailable" and result.n_eligible == 0
    work = frame()
    work["perfect"] = work.y
    result = brier_skill(work, "first", "perfect")
    assert result.value is None and result.status == "unavailable"


def test_duplicate_races_and_missing_columns_rejected():
    with pytest.raises(ValueError):
        match_sample(pd.concat([frame(), frame()]), ["first"])
    with pytest.raises(ValueError):
        match_sample(frame(), ["missing"])


def test_unclipped_infinite_paired_losses_are_explicit():
    work = frame().iloc[:1].copy()
    work["first"] = 0
    work["second"] = 0
    result = paired_difference(work, "first", "second", metric="log", clip=False)
    assert result.value is None and result.status == "unavailable"


def test_expected_counts_use_common_resolved_rows():
    result = expected_wins(frame(), "first")
    assert result.value["full_field_expected"] == 1.5
    assert result.value["eligible_expected"] == 1
    assert result.value["eligible_actual"] == 1
    assert not result.value["all_resolved"]


def test_frozen_samples_and_partial_outcomes(partial, complete):
    for data in (partial, complete):
        assert [len(select_sample(data.senate, s)) for s in ("all", "non_solid", "robust")] == [35, 15, 11]
    result = paired_difference(select_sample(partial.senate, "non_solid"), "p_kalshi", "p_model_mean")
    assert result.n_planned == 15 and result.n_eligible == 13
    assert result.status == "qualified" and any("provisional" in q for q in result.qualifications)
    assert not partial.senate.loc["MS-SEN", "call_eligible"]


def test_house_cook_seat_calculations(partial):
    row = partial.house.iloc[0]
    assert house_expected_seats(row) == pytest.approx(229.3764)
    assert house_expected_seats(row, "symmetric") == pytest.approx(230.6)
    assert house_expected_seats(row, "tossup_half") == pytest.approx(229.7724)
    assert house_expected_seats(row, "deterministic") == 231


def test_vote_share_eligibility_and_common_poll_sample(partial, complete):
    assert vote_share_score(partial.senate, "share_economist").n_eligible == 0
    frame = complete.senate
    result = vote_share_score(frame, "share_rcp", peers=["share_silver"], metric="bias")
    assert result.n_eligible == int((frame.share_rcp.notna() & frame.share_silver.notna()).sum())
    assert abs(result.per_race.centered_error.mean()) < 1e-12
    frame = frame.copy()
    frame.loc[result.race_ids[0], "share_eligible_silver"] = False
    assert vote_share_score(frame, "share_rcp", peers=["share_silver"]).n_eligible == result.n_eligible - 1


def test_invalid_probability_is_rejected_even_on_pending_row():
    work = frame()
    work.loc["C", "first"] = 1.2
    with pytest.raises(ValueError):
        probability_score(work, "first")

def test_opposing_infinite_paired_losses_are_unavailable():
    work = frame().iloc[:2].copy()
    work["first"] = [0., .2]
    work["second"] = [.8, 1.]
    result = paired_difference(work, "first", "second", metric="log", clip=False)
    assert result.value is None and result.status == "unavailable"


def test_zero_weight_undefined_paired_difference_does_not_affect_aggregate():
    work = frame().iloc[:2].copy()
    work["first"] = [0., .2]
    work["second"] = [0., .1]
    work["volume"] = [0., 1.]
    result = paired_difference(work, "first", "second", metric="log", clip=False, weights="volume")
    assert result.value == pytest.approx(-np.log(.8) + np.log(.9))
