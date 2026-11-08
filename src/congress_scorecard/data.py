"""Load frozen forecasts and one explicit, self-contained results snapshot."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .transforms import SHARE_SOURCES, prepare_forecasts, two_candidate_share, validate_range

SENATE_COLUMNS = (
    "race_id", "candidate_a", "candidate_b", "winner", "call_status", "call_source",
    "call_timestamp", "call_verified", "call_evidence", "recount_status",
    "percent_reporting", "reporting_type", "a_share", "b_share", "other_share",
    "round_used", "vote_complete", "vote_evidence", "snapshot_timestamp",
    *[f"share_compatible_{s}" for s in SHARE_SOURCES],
)
HOUSE_COLUMNS = (
    "race_id", "dem_seats", "gop_seats", "undecided_seats", "control",
    "control_source", "control_timestamp", "control_verified", "control_evidence",
    "control_method", "seats_final", "seats_evidence", "dem_share", "gop_share",
    "vote_complete", "vote_evidence", "vote_compatible", "snapshot_timestamp",
)
FROZEN_FILES = ("senate_forecasts.csv", "house_forecasts.csv", "senate_results.csv", "house_results.csv")


def project_root():
    return Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside release root: {relative}")
    return path


def _booleans(frame, columns):
    for column in columns:
        values = frame[column].astype("string").fillna("").str.lower()
        if not values.isin(["true", "false", ""]).all():
            raise ValueError(f"Invalid nullable boolean in {column}")
        frame[column] = values.map({"true": True, "false": False, "": pd.NA}).astype("boolean")


def _timestamp(value):
    parsed = pd.Timestamp(value)
    if pd.isna(parsed) or parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include an offset: {value}")
    return parsed


def _schema(frame, columns, label):
    if set(columns) - set(frame.columns):
        raise ValueError(f"Missing {label} columns: {sorted(set(columns) - set(frame.columns))}")
    if frame.race_id.isna().any() or frame.race_id.duplicated().any():
        raise ValueError(f"Invalid {label} race identifiers")
    for value in frame.snapshot_timestamp:
        _timestamp(value)


def _validate_forecasts(raw):
    senate = raw["senate_forecasts"]
    if len(senate) != 35 or senate.Race_ID.isna().any() or senate.Race_ID.duplicated().any():
        raise ValueError("Frozen Senate forecasts require 35 unique race identifiers")
    if not senate.Record_Date.eq("2026-11-02").all():
        raise ValueError("Forecast snapshot must remain November 2")
    for table in (senate, raw["house_forecasts"]):
        for column in table:
            if "Probability" in column or column.endswith(("_A_Share", "_B_Share")):
                validate_range(table[column], name=column)
            elif "Vote_Share" in column:
                validate_range(table[column], 0, 100, column)
        if table.Kalshi_Total_Volume.isna().any():
            raise ValueError("Frozen volume is missing")
        validate_range(table.Kalshi_Total_Volume, 0, float("inf"), "volume")
    house = raw["house_forecasts"]
    if len(house) != 1 or house.iloc[0].RaceID != "House" or house.iloc[0].Record_Date != "2026-11-02":
        raise ValueError("Frozen House forecast identity/date invalid")


def _validate_senate(results, forecast, manifest, root):
    _schema(results, SENATE_COLUMNS, "Senate")
    if any(_timestamp(t) != _timestamp(manifest["senate_timestamp"]) for t in results.snapshot_timestamp):
        raise ValueError("Senate row timestamps differ from manifest component timestamp")
    _booleans(results, ["call_verified", "vote_complete", *[f"share_compatible_{s}" for s in SHARE_SOURCES]])
    if set(results.race_id) != set(forecast.index):
        raise ValueError("Results must retain exactly the frozen Senate field")
    results = results.set_index("race_id").reindex(forecast.index)
    for derived, recorded in (("candidate_a", "Candidate_A"), ("candidate_b", "Candidate_B")):
        if not results[derived].eq(forecast[recorded]).all():
            raise ValueError("Result candidate orientation differs from forecasts")
    if not results.call_status.isin(["called", "pending", "unverified"]).all():
        raise ValueError("Invalid call status")
    if not results.recount_status.astype("string").fillna("unknown").isin(["unknown", "none", "active", "completed"]).all():
        raise ValueError("Invalid recount status")
    for column in ("percent_reporting", "a_share", "b_share", "other_share"):
        validate_range(results[column], 0, 100, column)
    sums = results[["a_share", "b_share", "other_share"]].sum(axis=1, min_count=3)
    if (sums.dropna() - 100).abs().gt(1e-6).any():
        raise ValueError("Reported Senate shares must sum to 100 when all are present")
    for race_id, row in results.iterrows():
        if pd.notna(row.winner) and row.winner not in (row.candidate_a, row.candidate_b):
            raise ValueError(f"Unknown winner in {race_id}")
        verified = pd.notna(row.call_verified) and bool(row.call_verified)
        if row.call_status == "called" and (not verified or pd.isna(row.winner)):
            raise ValueError(f"Called outcome lacks verified winner in {race_id}")
        if verified:
            if row.call_status != "called" or row.call_source != "DDHQ" or pd.isna(row.call_evidence):
                raise ValueError(f"Verified outcome lacks DDHQ call evidence in {race_id}")
            if _timestamp(row.call_timestamp) > _timestamp(row.snapshot_timestamp):
                raise ValueError("Call occurs after snapshot")
            if row.call_evidence not in manifest["hashes"]:
                raise ValueError("Call evidence must be hashed in the snapshot manifest")
            evidence = read_json(_inside(root, row.call_evidence))
            proof = next((r for r in evidence["rows"] if r["raceId"] == race_id), None)
            if not proof or proof["winner"] != row.winner:
                raise ValueError(f"Call evidence does not match {race_id}")
            called_id = proof["candidateAId"] if row.winner == row.candidate_a else proof["candidateBId"]
            times = [r["called_time"] for r in proof["callTimes"] if r["cand_id"] == called_id]
            if called_id not in proof["calledCandidateIds"] or not times or _timestamp(times[0]) != _timestamp(row.call_timestamp):
                raise ValueError(f"Call identifier/timestamp does not match {race_id}")
            if bool(evidence.get("synthetic", False)) != manifest["synthetic"]:
                raise ValueError("Synthetic evidence and snapshot labels differ")
        if row.vote_complete is not pd.NA and row.vote_complete:
            if pd.isna(row.vote_evidence) or pd.isna(row.a_share) or pd.isna(row.b_share) or pd.isna(row.round_used):
                raise ValueError("Complete vote share requires evidence, shares and round")
            if row.vote_evidence not in manifest["hashes"]:
                raise ValueError("Vote evidence must be hashed in the snapshot manifest")
            _inside(root, row.vote_evidence).read_bytes()
        if any(pd.notna(row[f"share_compatible_{s}"]) and row[f"share_compatible_{s}"] for s in SHARE_SOURCES):
            if not bool(row.vote_complete if pd.notna(row.vote_complete) else False):
                raise ValueError("Share compatibility requires documented vote completeness")
    return results


def _validate_house(results, manifest, root):
    _schema(results, HOUSE_COLUMNS, "House")
    if len(results) != 1 or results.iloc[0].race_id != "House":
        raise ValueError("Expected one House result")
    _booleans(results, ["control_verified", "seats_final", "vote_complete", "vote_compatible"])
    row = results.iloc[0]
    if _timestamp(row.snapshot_timestamp) != _timestamp(manifest["house_timestamp"]):
        raise ValueError("House timestamp differs from manifest component timestamp")
    seats = results[["dem_seats", "gop_seats", "undecided_seats"]]
    for column in seats:
        validate_range(seats[column], 0, 435, column)
    present = seats.iloc[0].dropna()
    if not (present % 1 == 0).all() or (len(present) == 3 and present.sum() != 435):
        raise ValueError("House seat counts must be integers totaling 435")
    for column in ("dem_share", "gop_share"):
        validate_range(results[column], 0, 100, column)
    if pd.notna(row.dem_share) and pd.notna(row.gop_share) and row.dem_share + row.gop_share > 100 + 1e-8:
        raise ValueError("House shares exceed 100")
    if pd.notna(row.control) and row.control not in ("Democratic", "Republican"):
        raise ValueError("Unknown House control")
    if pd.notna(row.control_verified) and row.control_verified:
        if row.control_source != "DDHQ" or pd.isna(row.control_evidence):
            raise ValueError("House control requires DDHQ evidence")
        if row.control_evidence not in manifest["hashes"]:
            raise ValueError("House evidence must be hashed in the snapshot manifest")
        proof = read_json(_inside(root, row.control_evidence))
        if bool(proof.get("synthetic", False)) != manifest["synthetic"]:
            raise ValueError("Synthetic House evidence labels differ")
        if _timestamp(row.control_timestamp) > _timestamp(row.snapshot_timestamp):
            raise ValueError("House control occurs after snapshot")
        if row.control_method == "district_threshold":
            counts = proof["calledSeatsByParty"]
            races = proof.get("races", [])
            if len(races) != 435 or len({r["raceId"] for r in races}) != 435:
                raise ValueError("Threshold evidence requires 435 unique voting districts")
            observed = Counter(r["winnerParty"] for r in races if r["calledCandidateIds"])
            if any(observed.get(party, 0) != counts.get(party, 0) for party in ("Democratic", "Republican")):
                raise ValueError("House district calls disagree with reported party counts")
            if (row.dem_seats != counts.get("Democratic", 0)
                    or row.gop_seats != counts.get("Republican", 0)):
                raise ValueError("House snapshot counts differ from attached threshold capture")
            party_count = counts.get(row.control, 0)
            if party_count < 218 or counts.get("Democratic", 0) + counts.get("Republican", 0) > 435:
                raise ValueError("House threshold evidence does not establish control")
            captured = _timestamp(proof["retrievedAtEastern"])
            if captured != _timestamp(row.snapshot_timestamp):
                raise ValueError("House evidence timestamp differs from the selected snapshot")
        elif row.control_method == "chamber_projection":
            if proof.get("projectedControl") != row.control or proof.get("source") != "DDHQ":
                raise ValueError("House projection evidence does not match")
        else:
            raise ValueError("Unknown House control method")
    if pd.notna(row.seats_final) and row.seats_final:
        if len(present) != 3 or row.undecided_seats != 0 or pd.isna(row.seats_evidence):
            raise ValueError("Final seats require complete counts and evidence")
        if row.seats_evidence not in manifest["hashes"]:
            raise ValueError("Final seat evidence must be hashed in the snapshot manifest")
        _inside(root, row.seats_evidence).read_bytes()
    if pd.notna(row.vote_complete) and row.vote_complete:
        if pd.isna(row.vote_evidence) or pd.isna(row.dem_share) or pd.isna(row.gop_share):
            raise ValueError("Complete House vote needs shares and evidence")
        if row.vote_evidence not in manifest["hashes"]:
            raise ValueError("Vote evidence must be hashed in the snapshot manifest")
        _inside(root, row.vote_evidence).read_bytes()
    if pd.notna(row.vote_compatible) and row.vote_compatible:
        if not (pd.notna(row.vote_complete) and row.vote_complete):
            raise ValueError("House vote compatibility requires completeness evidence")
    return results.set_index("race_id")


@dataclass
class Inputs:
    snapshot_id: str
    raw: dict
    senate: pd.DataFrame
    house: pd.DataFrame
    manifest: dict
    diagnostics: dict
    hashes: dict


def load_inputs(*, snapshot=None, root=None):
    root = Path(root).resolve() if root else project_root()
    snapshot = snapshot or os.environ.get("CONGRESS_SCORECARD_SNAPSHOT")
    if not snapshot or Path(snapshot).name != snapshot or snapshot in (".", ".."):
        raise ValueError("Select an explicit snapshot identifier")
    directory = _inside(root, f"data/results/{snapshot}")
    manifest = read_json(directory / "manifest.json")
    if manifest.get("schema_version") != 1 or manifest["snapshot_id"] != snapshot or type(manifest["synthetic"]) is not bool:
        raise ValueError("Invalid snapshot manifest identity")
    frozen = read_json(root / "data/provenance/frozen-inputs.json")
    hashes = {}
    for relative, expected in list(frozen["hashes"].items()) + list(manifest["hashes"].items()):
        actual = sha256(_inside(root, relative))
        if actual != expected:
            raise ValueError(f"Input hash mismatch: {relative}")
        hashes[relative] = actual
    required_hashes = {f"data/results/{snapshot}/{name}.csv" for name in ("senate_results", "house_results")}
    if not required_hashes.issubset(manifest["hashes"]):
        raise ValueError("Snapshot result hashes are required")
    raw = {Path(name).stem: pd.read_csv(root / "data/input" / name) for name in FROZEN_FILES}
    _validate_forecasts(raw)
    senate = prepare_forecasts(raw["senate_forecasts"])
    results = _validate_senate(pd.read_csv(directory / "senate_results.csv"), senate, manifest, root)
    house_results = _validate_house(pd.read_csv(directory / "house_results.csv"), manifest, root)
    raw["selected_senate_results"] = results.copy()
    raw["selected_house_results"] = house_results.copy()
    for column in results:
        senate[f"result_{column}"] = results[column]
    senate["call_eligible"] = (results.call_status.eq("called") & results.call_verified.fillna(False)
                               & ~results.recount_status.eq("active"))
    senate["call_exclusion"] = np.where(results.recount_status.eq("active"), "active recount",
                                        "no verified DDHQ call")
    senate["y"] = results.winner.eq(results.candidate_a).astype(float).where(senate.call_eligible)
    senate["actual_share"] = two_candidate_share(results.a_share, results.b_share, scale=100)
    for source in SHARE_SOURCES:
        senate[f"share_eligible_{source}"] = (
            results.vote_complete.fillna(False) & results[f"share_compatible_{source}"].fillna(False)
            & ~results.recount_status.eq("active") & senate.actual_share.notna()
            & senate[f"share_{source}"].notna())
    senate["share_exclusion"] = "vote completeness or forecast-target compatibility unverified"
    house = raw["house_forecasts"].copy().set_index("RaceID")
    house.index.name = "race_id"
    for column in house_results:
        house[f"result_{column}"] = house_results[column]
    hr = house_results.iloc[0]
    house["control_eligible"] = house_results.control_verified.fillna(False) & house_results.control.notna()
    house["control_exclusion"] = "House control lacks verified DDHQ evidence for selected snapshot"
    house["y"] = house_results.control.eq("Democratic").astype(float).where(house.control_eligible)
    house["call_eligible"] = house.control_eligible
    house["call_exclusion"] = house.control_exclusion
    house["seats_eligible"] = house_results.seats_final.fillna(False)
    house["vote_eligible"] = house_results.vote_complete.fillna(False) & house_results.vote_compatible.fillna(False)
    house["actual_share"] = two_candidate_share(house_results.dem_share, house_results.gop_share, scale=100)
    for source, label in (("kalshi", "Kalshi"), ("economist", "Economist"), ("votehub", "VoteHub")):
        house[f"p_{source}"] = house[f"{label}_DEM_Probability"]
    from .transforms import normalize_probabilities
    house["p_kalshi_normalized"] = normalize_probabilities(house.Kalshi_DEM_Probability, house.Kalshi_GOP_Probability)
    house["p_model_mean"] = (house.p_economist + house.p_votehub) / 2
    for source, label in (("rcp", "RCP"), ("silver", "Silver")):
        house[f"share_{source}"] = two_candidate_share(house[f"{label}_DEM_Vote_Share"], house[f"{label}_GOP_Vote_Share"], scale=100)
        house[f"share_eligible_{source}"] = house.vote_eligible
    qualifications = ["SYNTHETIC fixture; illustrative outcomes only."] if manifest["synthetic"] else ["Preliminary results; eligibility varies by metric."]
    for frame in (senate, house):
        frame.attrs["qualifications"] = qualifications.copy()
    diagnostics = {
        "snapshot": snapshot, "synthetic": manifest["synthetic"],
        "senate_rows": len(senate), "verified_calls": int(senate.call_eligible.sum()),
        "pending_or_ineligible": senate.index[~senate.call_eligible].tolist(),
        "samples": {s: int(senate[f"sample_{s}"].sum()) for s in ("all", "non_solid", "robust")},
        "share_eligible": {s: int(senate[f"share_eligible_{s}"].sum()) for s in SHARE_SOURCES},
        "house_control_eligible": bool(house.control_eligible.iloc[0]),
        "house_seats_final": bool(house.seats_eligible.iloc[0]),
        "house_vote_eligible": bool(house.vote_eligible.iloc[0]),
        "caucus_eligible": False,
        "qualifications": qualifications + manifest.get("qualifications", []),
    }
    return Inputs(snapshot, raw, senate, house, manifest, diagnostics, hashes)
