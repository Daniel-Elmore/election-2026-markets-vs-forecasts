"""Recreate initial snapshot adapters from the original local artifacts.

This bootstrap is explicit and refuses to overwrite an existing snapshot.
It is not a forecast refresh or a network fetch.
"""
import argparse
from collections import Counter
import json
from pathlib import Path, PureWindowsPath

import pandas as pd

from congress_scorecard.data import HOUSE_COLUMNS, SENATE_COLUMNS, project_root, read_json, sha256
from congress_scorecard.transforms import SHARE_SOURCES


def publication_paths(value):
    """Replace machine-specific artifact locations with their filenames."""
    if isinstance(value, dict):
        return {key: publication_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [publication_paths(item) for item in value]
    if isinstance(value, str) and PureWindowsPath(value).is_absolute():
        return PureWindowsPath(value).name
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=project_root().parent)
    args = parser.parse_args()
    root = project_root()
    workspace = args.workspace
    snapshot_ids = ("current-partial", "ddhq-20261104-222052-est", "synthetic-complete")
    if any((root / "data/results" / s).exists() for s in snapshot_ids):
        raise SystemExit("Initial snapshots exist; choose a new dated snapshot for new results.")
    planning = workspace / ".planning"
    provenance = root / "data/provenance"
    senate_proof_name = "ddhq-senate-provenance-20261104-220502-EST.json"
    house_proof_name = "ddhq-house-provenance-20261104-222052-EST.json"
    for name in (senate_proof_name, house_proof_name):
        write_json(provenance / name, publication_paths(read_json(planning / name)))
    senate_proof_path = "data/provenance/" + senate_proof_name
    house_proof_path = "data/provenance/" + house_proof_name
    proof = read_json(planning / senate_proof_name)
    raw_capture = read_json(planning / "ddhq-senate-snapshot-20261104-220502-EST.json")
    races = {r["race_id"]: r for response in raw_capture["responses"] for r in response["data"]}
    call_extract = []
    for row in proof["rows"]:
        race = races[row["ddhqRaceId"]]
        if race["topline_results"]["called_candidates"] != row["calledCandidateIds"]:
            raise ValueError("Provenance calls differ from raw DDHQ capture")
        if race["topline_results"]["call_times"] != row["callTimes"]:
            raise ValueError("Provenance timestamps differ from raw DDHQ capture")
        call_extract.append({k: race[k] for k in ("race_id", "state", "last_updated", "candidates")}
                            | {"topline_results": race["topline_results"]})
    write_json(provenance / "ddhq-senate-call-extract.json", {
        "source": "Decision Desk HQ", "original_capture_sha256": sha256(planning / "ddhq-senate-snapshot-20261104-220502-EST.json"),
        "omitted_fields": ["counties", "race configuration"], "races": call_extract,
    })
    fixed_hashes = {f"data/input/{name}": sha256(root / "data/input" / name)
                    for name in ("senate_forecasts.csv", "house_forecasts.csv", "senate_results.csv", "house_results.csv")}
    write_json(provenance / "frozen-inputs.json", {"hashes": fixed_hashes})
    recorded = pd.read_csv(root / "data/input/senate_results.csv")
    senate_rows = []
    for _, row in recorded.iterrows():
        p = next(r for r in proof["rows"] if r["raceId"] == row.Race_ID)
        winner = row.Winner if pd.notna(row.Winner) else None
        if winner != p["winner"]:
            raise ValueError("Frozen winner differs from DDHQ provenance")
        called_id = p["candidateAId"] if winner == row.Candidate_A else p["candidateBId"]
        times = [t["called_time"] for t in p["callTimes"] if t["cand_id"] == called_id] if winner else []
        senate_rows.append({
            "race_id": row.Race_ID, "candidate_a": row.Candidate_A, "candidate_b": row.Candidate_B,
            "winner": winner, "call_status": "called" if winner else "pending", "call_source": "DDHQ",
            "call_timestamp": times[0] if times else None, "call_verified": bool(winner),
            "call_evidence": senate_proof_path if winner else None, "recount_status": None,
            "percent_reporting": row["Percent of Vote In"], "reporting_type": p["reportingType"],
            "a_share": row.Candidate_A_Vote_Share, "b_share": row.Candidate_B_Vote_Share,
            "other_share": row.Other_Vote_Share, "round_used": p["roundUsed"],
            "vote_complete": None, "vote_evidence": None,
            "snapshot_timestamp": proof["retrievedAtEastern"],
            **{f"share_compatible_{s}": None for s in SHARE_SOURCES},
        })
    house = pd.read_csv(root / "data/input/house_results.csv").iloc[0]
    current_house = {
        "race_id": "House", "dem_seats": house.DEM_Seats, "gop_seats": house.GOP_Seats,
        "undecided_seats": house.Undecided_Seats, "control": house.House_Control,
        "control_source": "DDHQ", "control_timestamp": None, "control_verified": False,
        "control_evidence": None, "control_method": "district_threshold", "seats_final": False,
        "seats_evidence": None, "dem_share": house.DEM_Vote_Share, "gop_share": house.GOP_Vote_Share,
        "vote_complete": False, "vote_evidence": None, "vote_compatible": None,
        "snapshot_timestamp": "2026-11-06T20:25:52-05:00",
    }
    hp = read_json(provenance / house_proof_name)
    archived_house = current_house | {
        "dem_seats": hp["results"]["demSeats"], "gop_seats": hp["results"]["gopSeats"],
        "undecided_seats": hp["results"]["undecided"], "control": hp["results"]["control"],
        "control_timestamp": hp["retrievedAtEastern"], "control_verified": True,
        "control_evidence": house_proof_path, "dem_share": hp["results"]["demShare"],
        "gop_share": hp["results"]["gopShare"], "snapshot_timestamp": hp["retrievedAtEastern"],
    }
    fixtures = {}
    fixtures["current-partial"] = (senate_rows, current_house, False)
    fixtures["ddhq-20261104-222052-est"] = (senate_rows, archived_house, False)
    synthetic_rows = []
    synthetic_proof = {"synthetic": True, "source": "Illustrative DDHQ-shaped fixture", "rows": []}
    stamp = "2026-11-06T23:00:00-05:00"
    fixture_evidence = "data/results/synthetic-complete/evidence.json"
    for i, original in enumerate(senate_rows):
        winner = original["candidate_a"] if i % 2 == 0 else original["candidate_b"]
        row = original | {
            "winner": winner, "call_status": "called", "call_source": "DDHQ",
            "call_timestamp": stamp, "call_verified": True, "call_evidence": fixture_evidence,
            "recount_status": "none", "percent_reporting": 100, "reporting_type": "synthetic complete",
            "a_share": 60 if i % 2 == 0 else 40, "b_share": 40 if i % 2 == 0 else 60,
            "other_share": 0, "round_used": "Synthetic comparable round", "vote_complete": True,
            "vote_evidence": fixture_evidence, "snapshot_timestamp": stamp,
            **{f"share_compatible_{s}": True for s in SHARE_SOURCES},
        }
        synthetic_rows.append(row)
        synthetic_proof["rows"].append({
            "raceId": row["race_id"], "winner": winner, "candidateAId": i * 2 + 1,
            "candidateBId": i * 2 + 2, "calledCandidateIds": [i * 2 + (1 if i % 2 == 0 else 2)],
            "callTimes": [{"cand_id": i * 2 + (1 if i % 2 == 0 else 2), "called_time": stamp}],
        })
    synthetic_proof |= {
        "retrievedAtEastern": stamp, "calledSeatsByParty": {"Democratic": 240, "Republican": 195},
        "races": [{"raceId": i, "winnerParty": "Democratic" if i < 240 else "Republican",
                   "calledCandidateIds": [i + 1]} for i in range(435)],
        "note": "SYNTHETIC complete results for software tests. Not observed election data.",
    }
    synthetic_house = current_house | {
        "dem_seats": 240, "gop_seats": 195, "undecided_seats": 0, "control": "Democratic",
        "control_timestamp": stamp, "control_verified": True, "control_evidence": fixture_evidence,
        "seats_final": True, "seats_evidence": fixture_evidence, "dem_share": 52,
        "gop_share": 48, "vote_complete": True, "vote_evidence": fixture_evidence,
        "vote_compatible": True, "snapshot_timestamp": stamp,
    }
    fixtures["synthetic-complete"] = (synthetic_rows, synthetic_house, True)
    for snapshot_id, (sr, hr, synthetic) in fixtures.items():
        directory = root / "data/results" / snapshot_id
        directory.mkdir(parents=True)
        if synthetic:
            write_json(directory / "evidence.json", synthetic_proof)
        pd.DataFrame(sr, columns=SENATE_COLUMNS).to_csv(directory / "senate_results.csv", index=False)
        pd.DataFrame([hr], columns=HOUSE_COLUMNS).to_csv(directory / "house_results.csv", index=False)
        evidence_files = {row["call_evidence"] for row in sr if row["call_evidence"]}
        if hr["control_evidence"]:
            evidence_files.add(hr["control_evidence"])
        evidence_files.add("data/provenance/ddhq-senate-call-extract.json")
        relatives = [f"data/results/{snapshot_id}/{name}.csv" for name in ("senate_results", "house_results")]
        relatives += sorted(evidence_files)
        write_json(directory / "manifest.json", {
            "schema_version": 1, "snapshot_id": snapshot_id, "synthetic": synthetic,
            "description": "SYNTHETIC complete-results test fixture" if synthetic else "Preserved preliminary results adapter",
            "senate_timestamp": sr[0]["snapshot_timestamp"], "house_timestamp": hr["snapshot_timestamp"],
            "caucus_analysis_approved": False, "volume_units": None, "kalshi_price_measure": None,
            "qualifications": [
                "Kalshi recorded probabilities provisionally approved despite unverified price measures and KY contract URL.",
                "Currency volume labels and dollar cutoff unavailable pending unit verification.",
                "Independent caucus evidence contradicts plan assumption; caucus seat/control reporting withheld.",
            ],
            "approved_exceptions": ["DDHQ district threshold of 218 may establish House control with evidence.",
                                    "Provisional Kalshi scoring may use preserved recorded probabilities."],
            "hashes": {relative: sha256(root / relative) for relative in relatives},
        })
    write_json(provenance / "audit-record.json", {
        "workbooks": {f.name: sha256(f) for f in (workspace / "data").glob("*.xlsx") if not f.name.startswith("~$")},
        "captures": {name: sha256(planning / name) for name in
                     (senate_proof_name, house_proof_name, "ddhq-senate-snapshot-20261104-220502-EST.json",
                      "ddhq-house-snapshot-20261104-222052-EST.json")},
        "known_discrepancies": [
            "House workbook/CSV row is dated November 6 and differs from November 4 archive.",
            "Archived Senate AP convention note predates current DDHQ rule.",
            "KY-SEN Kalshi URL names Louisiana. Frozen note says confirmed as entered; contract identity remains unverified.",
            "Forecast workbook has no comments or saved price-measure/volume-unit captures.",
            "Snapshot Record_Timestamp is a row recording time, not source-specific publication/retrieval evidence.",
        ],
    })
    print("INITIAL SNAPSHOTS CREATED")


if __name__ == "__main__":
    main()
