"""Explicit transformations. Raw inputs are never modified."""
import numpy as np
import pandas as pd

COOK_MAPPINGS = {
    "primary": {"Solid": .99, "Likely": .97, "Lean": .94},
    "senate": {"Solid": .99, "Likely": .978, "Lean": .981},
    "wide": {"Solid": .99, "Likely": .90, "Lean": .70},
}
SHARE_SOURCES = ("economist", "votehub", "rcp", "silver")
INDEPENDENTS = ("NE-SEN", "MT-SEN", "ID-SEN", "SD-SEN")


def validate_range(values, low=0, high=1, name="values"):
    values = pd.Series(values, dtype=float)
    present = values.dropna()
    if not np.isfinite(present).all() or not present.between(low, high).all():
        raise ValueError(f"{name} must be finite and in [{low}, {high}]")
    return values


def two_candidate_share(a, b, *, scale=1):
    a = validate_range(a, 0, scale, "A share")
    b = validate_range(b, 0, scale, "B share")
    if not a.index.equals(b.index):
        raise ValueError("A and B indices must match")
    if ((a + b) > scale + 1e-8).any():
        raise ValueError("Vote shares exceed their recorded scale")
    return a.div((a + b).where((a + b) > 0))


def normalize_probabilities(a, b):
    # Prices may sum above one. This conditions on A or B winning.
    a = validate_range(a, name="A probability")
    b = validate_range(b, name="B probability")
    if not a.index.equals(b.index):
        raise ValueError("A and B indices must match")
    return a.div((a + b).where((a + b) > 0))


def cook_probability(rating, *, mapping="primary", a_party="Democratic"):
    if rating == "Toss-Up":
        return .5
    bucket, direction = rating.rsplit(" ", 1)
    if direction not in ("D", "R"):
        raise ValueError(f"Unknown Cook direction: {rating}")
    favored = COOK_MAPPINGS[mapping][bucket]
    if a_party not in ("Democratic", "Independent", "Republican"):
        raise ValueError(f"Unsupported candidate A party: {a_party}")
    a_direction = "R" if a_party == "Republican" else "D"
    return favored if direction == a_direction else 1 - favored


def favorite(probability):
    probability = validate_range(probability, name="probability")
    return pd.Series(np.where(probability > .5, 1., np.where(probability < .5, 0., np.nan)),
                     index=probability.index).where(probability.notna())


def prepare_forecasts(raw):
    frame = raw.copy().set_index("Race_ID")
    if not frame.index.is_unique:
        raise ValueError("Race identifiers must be unique")
    frame.index.name = "race_id"
    for source, label in (("kalshi", "Kalshi"), ("economist", "Economist"), ("votehub", "VoteHub")):
        frame[f"p_{source}"] = validate_range(frame[f"{label}_A_Probability"], name=source)
    frame["p_kalshi_normalized"] = normalize_probabilities(
        frame.Kalshi_A_Probability, frame.Kalshi_B_Probability)
    frame["p_model_mean"] = (frame.p_economist + frame.p_votehub) / 2
    frame["p_blend"] = (frame.p_kalshi + frame.p_model_mean) / 2
    for mapping in COOK_MAPPINGS:
        frame[f"p_cook_{mapping}"] = [
            cook_probability(r, mapping=mapping, a_party=p)
            for r, p in zip(frame.Cook_Rating, frame.Candidate_A_Party)
        ]
    frame["p_constant"] = frame.p_cook_primary.map(lambda p: .5 if p == .5 else (.95 if p > .5 else .05))
    frame["p_uniform"] = .5
    frame["sample_all"] = True
    frame["sample_non_solid"] = ~frame.Cook_Rating.str.startswith("Solid")
    frame["sample_robust"] = ((frame.p_kalshi + frame.p_economist + frame.p_votehub) / 3).between(.1, .9)
    frame["sample_cook_directional"] = frame.Cook_Rating.ne("Toss-Up")
    for source in SHARE_SOURCES:
        label = {"economist": "Economist", "votehub": "VoteHub", "rcp": "RCP", "silver": "Silver"}[source]
        a = f"{label}_A_Share" if source in ("economist", "votehub") else f"{label}_A_Vote_Share"
        b = a.replace("_A_", "_B_")
        frame[f"share_{source}"] = two_candidate_share(frame[a], frame[b], scale=1 if source in ("economist", "votehub") else 100)
    frame["volume"] = validate_range(frame.Kalshi_Total_Volume, 0, float("inf"), "volume")
    return frame


def select_sample(frame, sample="all"):
    column = f"sample_{sample}"
    if column not in frame:
        raise ValueError(f"Unknown sample: {sample}")
    return frame.loc[frame[column]].copy()


def house_expected_seats(row, method="directional"):
    counts = [float(row[f"Cook_{rating}_Rating"]) for rating in
              ("SolidD", "LikelyD", "LeanD", "TossUp", "LeanR", "LikelyR", "SolidR")]
    weights = {
        "directional": [.9997, .961, .907, .478, .049, .023, .0003],
        "symmetric": [.99, .97, .94, .5, .06, .03, .01],
        "tossup_half": [.9997, .961, .907, .5, .049, .023, .0003],
        "deterministic": [1, 1, 1, .5, 0, 0, 0],
    }
    if sum(counts) != 435 or any(c < 0 or not c.is_integer() for c in counts):
        raise ValueError("Cook House counts must be nonnegative integers totaling 435")
    return float(np.dot(counts, weights[method]))
