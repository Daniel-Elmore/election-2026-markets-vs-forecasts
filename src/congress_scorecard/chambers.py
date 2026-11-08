"""Seat and control reporting with explicit finality gates."""
from .scoring import ScoreResult, calls_correct, match_sample, _result, probability_score
from .transforms import INDEPENDENTS, house_expected_seats


def senate_caucus_seats(inputs, source, *, holdover=None, scenario="primary"):
    if scenario not in ("primary", *INDEPENDENTS):
        raise ValueError("Scenario must be primary or an independent race to exclude")
    # Approval remains withheld in this release. A future methodology decision
    # must supply caucus evidence, holdovers and the control tie convention.
    return ScoreResult(None, "unavailable", len(inputs.senate), 0, [],
                       {r: ["Caucus methodology and supporting evidence pending"] for r in inputs.senate.index},
                       qualifications=["Rule 10 scenarios retained. Candidate A outcome scores remain available."])


def house_control(inputs, source, *, metric="brier", clip=True):
    if source == "cook":
        work = inputs.house.copy()
        row = work.iloc[0]
        favored = sum(row[f"Cook_{r}_Rating"] for r in ("SolidD", "LikelyD", "LeanD"))
        republican = sum(row[f"Cook_{r}_Rating"] for r in ("SolidR", "LikelyR", "LeanR"))
        work["p_cook_call"] = 1. if favored >= 218 else 0. if republican >= 218 else .5
        return calls_correct(work, "p_cook_call")
    return probability_score(inputs.house, source, metric=metric, clip=clip,
                             eligibility="control_eligible")


def house_seat_error(inputs, source, *, cook_method="directional"):
    work = inputs.house.copy()
    if source == "cook":
        work["expected"] = [house_expected_seats(row, cook_method) for _, row in work.iterrows()]
    elif source in ("economist", "votehub"):
        label = {"economist": "Economist", "votehub": "VoteHub"}[source]
        work["expected"] = work[f"{label}_DEM_Seats"]
    else:
        raise ValueError("House seats support cook, economist and votehub")
    work["actual"] = work.result_dem_seats
    work["seats_exclusion"] = "Final House district outcomes unavailable"
    sample = match_sample(work, ["expected"], outcome="actual", eligibility="seats_eligible")
    rows = sample.rows
    value = None
    if len(rows):
        error = float(rows.expected.iloc[0] - rows.actual.iloc[0])
        value = {"expected": float(rows.expected.iloc[0]), "actual": int(rows.actual.iloc[0]),
                 "signed_error": error, "absolute_error": abs(error)}
    return _result(sample, value)
