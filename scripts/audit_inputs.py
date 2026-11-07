"""Check frozen CSV extracts against workbooks and calls against archived DDHQ data."""
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from congress_scorecard.data import load_inputs, project_root, read_json, sha256


def compare_extract(csv_path, worksheet):
    csv = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    values = list(worksheet.values)
    if list(csv.columns) != list(values[0]) or len(csv) != len(values) - 1:
        raise AssertionError(f"Extract shape differs: {csv_path.name}")
    for row_index, workbook_row in enumerate(values[1:]):
        for column, recorded in zip(csv.columns, workbook_row):
            actual = csv.iloc[row_index][column]
            if recorded is None:
                assert actual == "", (csv_path.name, row_index, column)
            elif isinstance(recorded, datetime):
                assert pd.Timestamp(actual) == pd.Timestamp(recorded), (row_index, column)
            elif isinstance(recorded, (int, float)):
                assert np.isclose(float(actual), recorded, rtol=1e-13, atol=1e-12), (row_index, column)
            else:
                assert actual == str(recorded), (row_index, column)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=project_root().parent)
    args = parser.parse_args()
    root = project_root()
    manifest = pd.read_csv(root / "data/provenance/sources.csv")
    source = args.workspace / "data" / manifest.workbook.iloc[0]
    assert sha256(source) == manifest.workbook_sha256.iloc[0], "Working workbook hash differs"
    workbook = load_workbook(source, data_only=True)
    for row in manifest.itertuples():
        compare_extract(root / "data" / row.file, workbook[row.worksheet])
    original = load_workbook(args.workspace / "data/Election-Night-2026-Markets-Scorecard.xlsx", data_only=True)
    compare_extract(root / "data/input/senate_forecasts.csv", original["Predictions"])
    compare_extract(root / "data/input/house_forecasts.csv", original["HousePredictions"])
    capture = read_json(args.workspace / ".planning/ddhq-senate-snapshot-20261104-220502-EST.json")
    races = {r["race_id"]: r for response in capture["responses"] for r in response["data"]}
    proof = read_json(root / "data/provenance/ddhq-senate-provenance-20261104-220502-EST.json")
    for row in proof["rows"]:
        race = races[row["ddhqRaceId"]]
        assert race["topline_results"]["called_candidates"] == row["calledCandidateIds"]
        assert race["topline_results"]["call_times"] == row["callTimes"]
        a = row["candidateAId"]
        b = row["candidateBId"]
        votes = race["topline_results"]["votes"]
        total = race["topline_results"]["total_votes"]
        assert np.isclose(votes[str(a)] / total * 100, row["shares"][0])
        assert np.isclose(votes[str(b)] / total * 100, row["shares"][1])
    for snapshot in ("current-partial", "ddhq-20261104-222052-est", "synthetic-complete"):
        load_inputs(snapshot=snapshot)
    print("AUDIT PASSED — four extracts, two original forecasts, 35 DDHQ call/share records, three adapters")


if __name__ == "__main__":
    main()
