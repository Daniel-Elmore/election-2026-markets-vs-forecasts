import json
import pandas as pd
import pytest

from congress_scorecard import house_control, house_seat_error, load_inputs, senate_caucus_seats
from congress_scorecard.runtime import load_context
from conftest import rehash_snapshot


def edit_senate(root, mutate):
    path = root / "data/results/synthetic-complete/senate_results.csv"
    frame = pd.read_csv(path)
    mutate(frame)
    frame.to_csv(path, index=False)
    rehash_snapshot(root)


def test_current_snapshot_preserves_rows_and_nullable_metadata(partial):
    assert len(partial.senate) == 35
    assert partial.diagnostics["verified_calls"] == 33
    assert partial.senate.loc[["AK-SEN", "MS-SEN"], "y"].isna().all()
    assert partial.senate.result_recount_status.isna().all()
    assert partial.senate.result_vote_complete.isna().all()
    assert partial.diagnostics["share_eligible"] == dict.fromkeys(["economist", "votehub", "rcp", "silver"], 0)
    assert partial.raw["senate_forecasts"].iloc[0].Kalshi_A_Probability == .71
    assert partial.senate.iloc[0].p_kalshi_normalized == pytest.approx(.71 / 1.01)


def test_partial_complete_switch_and_final_house_gates(partial, complete):
    assert complete.diagnostics["synthetic"] and complete.diagnostics["verified_calls"] == 35
    assert partial.senate.index.equals(complete.senate.index)
    pd.testing.assert_series_equal(partial.senate.p_kalshi, complete.senate.p_kalshi)
    assert house_control(partial, "p_kalshi").value is None
    assert house_seat_error(partial, "economist").value is None
    assert house_seat_error(complete, "economist").value["actual"] == 240
    assert house_control(complete, "cook").value["calls_made"] == 1
    assert house_control(complete, "p_kalshi").value is not None
    assert senate_caucus_seats(complete, "p_kalshi").status == "unavailable"


def test_archived_house_threshold_has_evidence():
    data = load_inputs(snapshot="ddhq-20261104-222052-est")
    assert data.diagnostics["house_control_eligible"]
    assert not data.diagnostics["house_seats_final"]
    assert data.house.result_dem_seats.iloc[0] == 247
    assert house_control(data, "p_economist").n_eligible == 1


def test_snapshot_selection_required(monkeypatch):
    monkeypatch.delenv("CONGRESS_SCORECARD_SNAPSHOT", raising=False)
    with pytest.raises(ValueError):
        load_inputs()
    monkeypatch.setenv("CONGRESS_SCORECARD_SNAPSHOT", "synthetic-complete")
    assert load_inputs().manifest["synthetic"]
    with pytest.raises(ValueError):
        load_inputs(snapshot="../outside")


def test_hash_tampering_rejected(copied_root):
    path = copied_root / "data/input/senate_forecasts.csv"
    path.write_text(path.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_inputs(snapshot="current-partial", root=copied_root)


@pytest.mark.parametrize("column,value", [("candidate_a", "Wrong name"), ("winner", "Unlisted candidate"),
    ("call_source", "AP"), ("call_verified", "maybe"), ("a_share", 101),
    ("call_timestamp", "2026-11-06T23:00:00"), ("call_timestamp", "2026-11-07T23:00:00-05:00")])
def test_invalid_snapshot_rejected(copied_root, column, value):
    edit_senate(copied_root, lambda frame: frame.__setitem__(column, value))
    with pytest.raises(ValueError):
        load_inputs(snapshot="synthetic-complete", root=copied_root)


def test_active_recount_is_scored_last(copied_root):
    edit_senate(copied_root, lambda frame: frame.__setitem__("recount_status", "active"))
    data = load_inputs(snapshot="synthetic-complete", root=copied_root)
    assert data.senate.call_eligible.sum() == 0
    assert data.senate.share_eligible_economist.sum() == 0


def test_all_pending_with_vote_leads_never_become_calls(copied_root):
    def pending(frame):
        frame["winner"] = None
        frame["call_verified"] = False
        frame["call_status"] = "pending"
        frame["call_timestamp"] = None
        frame["call_evidence"] = None
    edit_senate(copied_root, pending)
    data = load_inputs(snapshot="synthetic-complete", root=copied_root)
    assert data.senate.y.isna().all()
    # Share completeness remains independent of the missing call.
    assert data.senate.share_eligible_economist.all()


def test_house_finality_validation(copied_root):
    path = copied_root / "data/results/synthetic-complete/house_results.csv"
    frame = pd.read_csv(path)
    frame["undecided_seats"] = 1
    frame.to_csv(path, index=False)
    rehash_snapshot(copied_root)
    with pytest.raises(ValueError):
        load_inputs(snapshot="synthetic-complete", root=copied_root)


def test_context_selects_snapshot_and_rejects_reused_output(monkeypatch, tmp_path):
    monkeypatch.setenv("CONGRESS_SCORECARD_SNAPSHOT", "current-partial")
    monkeypatch.setenv("CONGRESS_SCORECARD_OUTPUT_DIR", str(tmp_path / "run"))
    first = load_context("01_congress_scorecard")
    second = load_context("02_forecast_accuracy")
    assert first.output_dir == second.output_dir and first.figures_dir != second.figures_dir
    monkeypatch.setenv("CONGRESS_SCORECARD_SNAPSHOT", "synthetic-complete")
    with pytest.raises(ValueError, match="different snapshot"):
        load_context("01_congress_scorecard")


def test_unhashed_call_evidence_is_rejected(copied_root):
    path = copied_root / "data/results/synthetic-complete/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    del manifest["hashes"]["data/results/synthetic-complete/evidence.json"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="must be hashed"):
        load_inputs(snapshot="synthetic-complete", root=copied_root)


def test_house_threshold_must_reconcile_to_district_calls(copied_root):
    snapshot = "ddhq-20261104-222052-est"
    manifest_path = copied_root / "data/results" / snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    evidence_path = copied_root / "data/provenance/ddhq-house-provenance-20261104-222052-EST.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    evidence["calledSeatsByParty"]["Democratic"] -= 1
    evidence_path.write_text(json.dumps(evidence))
    rehash_snapshot(copied_root, snapshot)
    with pytest.raises(ValueError, match="disagree"):
        load_inputs(snapshot=snapshot, root=copied_root)


def test_manifest_component_timestamps_must_match_rows(copied_root):
    path = copied_root / "data/results/synthetic-complete/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    manifest["senate_timestamp"] = "2026-11-07T23:00:00-05:00"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="component timestamp"):
        load_inputs(snapshot="synthetic-complete", root=copied_root)

def test_source_share_coverage_is_reported_after_missing_forecasts(complete):
    assert complete.diagnostics["share_eligible"] == {
        "economist": 35, "votehub": 35, "rcp": 18, "silver": 24,
    }
