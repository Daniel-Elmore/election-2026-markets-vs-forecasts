"""Race-keyed scoring with explicit common samples and exclusions."""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .transforms import favorite, validate_range


@dataclass
class MatchedSample:
    rows: pd.DataFrame
    n_planned: int
    excluded: dict
    weighted: bool
    weight_sum: float
    qualifications: list = field(default_factory=list)


@dataclass
class ScoreResult:
    value: object
    status: str
    n_planned: int
    n_eligible: int
    race_ids: list
    exclusions: dict
    weighted: bool = False
    weight_sum: float = 0.
    qualifications: list = field(default_factory=list)
    per_race: pd.DataFrame = field(default_factory=pd.DataFrame)

    def summary(self):
        return {k: v for k, v in vars(self).items() if k != "per_race"}


def match_sample(frame, columns, *, outcome="y", eligibility="call_eligible", weights=None):
    if frame.index.has_duplicates or frame.index.isna().any():
        raise ValueError("Race identifiers must be unique and present")
    required = list(dict.fromkeys([*columns, outcome]))
    missing = set(required + ([eligibility] if eligibility else []) + ([weights] if weights else [])) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if weights:
        validate_range(frame[weights], 0, float("inf"), "weights")
    excluded = {}
    for race_id, row in frame.iterrows():
        reasons = [f"missing {column}" for column in required if pd.isna(row[column])]
        if eligibility and (pd.isna(row[eligibility]) or not bool(row[eligibility])):
            reason_column = eligibility.replace("_eligible", "_exclusion")
            reasons.append(str(row.get(reason_column, eligibility + " false")))
        if weights and pd.isna(row[weights]):
            reasons.append("missing weight")
        if reasons:
            excluded[race_id] = reasons
    rows = frame.loc[~frame.index.isin(excluded)].copy()
    total = float(rows[weights].sum()) if weights else float(len(rows))
    if len(rows) and total <= 0:
        raise ValueError("Eligible weights must have positive total")
    rows["_weight"] = rows[weights] / total if weights else (1 / len(rows) if len(rows) else pd.Series(dtype=float))
    qualifications = list(frame.attrs.get("qualifications", []))
    if any("kalshi" in c or c in ("p_blend", "p_model_mean") for c in columns):
        qualifications.append("Kalshi provenance incomplete; recorded probabilities approved for provisional scoring. Model mean includes market-informed VoteHub Complete.")
    return MatchedSample(rows, len(frame), excluded, bool(weights), total, qualifications)


def _result(sample, value, per_race=None):
    status = "ok" if len(sample.rows) else "unavailable"
    if len(sample.rows) and sample.qualifications:
        status = "qualified"
    return ScoreResult(value, status, sample.n_planned, len(sample.rows),
                       sample.rows.index.tolist(), sample.excluded, sample.weighted,
                       sample.weight_sum, sample.qualifications,
                       sample.rows.copy() if per_race is None else per_race)


def brier_loss(probability, outcome):
    p = validate_range(probability, name="probability")
    y = validate_range(outcome, name="outcome")
    if not p.index.equals(y.index) or not y.dropna().isin([0, 1]).all():
        raise ValueError("Binary outcomes and matching indices required")
    return (p - y) ** 2


def log_loss(probability, outcome, *, clip=True):
    p = validate_range(probability, name="probability")
    y = validate_range(outcome, name="outcome")
    if not p.index.equals(y.index) or not y.dropna().isin([0, 1]).all():
        raise ValueError("Binary outcomes and matching indices required")
    if clip:
        p = p.clip(.01, .99)
    with np.errstate(divide="ignore", invalid="ignore"):
        loss = pd.Series(np.where(y == 1, -np.log(p), -np.log1p(-p)), index=p.index)
    return loss.where(p.notna() & y.notna())


def _weighted_mean(values, rows):
    # Zero weights contribute nothing even when unclipped loss is infinite.
    positive = rows["_weight"] > 0
    return float((values.loc[positive] * rows.loc[positive, "_weight"]).sum())


def probability_score(frame, source, *, metric="brier", weights=None, clip=True,
                      outcome="y", eligibility="call_eligible"):
    validate_range(frame[source], name=source)
    sample = match_sample(frame, [source], outcome=outcome, eligibility=eligibility, weights=weights)
    rows = sample.rows
    if metric == "brier":
        rows["loss"] = brier_loss(rows[source], rows[outcome])
    elif metric == "log":
        rows["loss"] = log_loss(rows[source], rows[outcome], clip=clip)
    else:
        raise ValueError("metric must be brier or log")
    return _result(sample, _weighted_mean(rows.loss, rows) if len(rows) else None)


def paired_difference(frame, first, second, *, metric="brier", weights=None, clip=True):
    validate_range(frame[first], name=first)
    validate_range(frame[second], name=second)
    sample = match_sample(frame, [first, second], weights=weights)
    rows = sample.rows
    loss = brier_loss if metric == "brier" else log_loss if metric == "log" else None
    if loss is None:
        raise ValueError("metric must be brier or log")
    kwargs = {} if metric == "brier" else {"clip": clip}
    rows["loss_first"] = loss(rows[first], rows.y, **kwargs)
    rows["loss_second"] = loss(rows[second], rows.y, **kwargs)
    rows["difference"] = rows.loss_first - rows.loss_second
    active_differences = rows.loc[rows["_weight"] > 0, "difference"]
    opposite_infinities = np.isposinf(active_differences).any() and np.isneginf(active_differences).any()
    if active_differences.isna().any() or opposite_infinities:
        result = _result(sample, None)
        result.status = "unavailable"
        result.qualifications.append("Unclipped paired difference is undefined for opposing infinite losses.")
        return result
    return _result(sample, _weighted_mean(rows.difference, rows) if len(rows) else None)


def brier_skill(frame, source, reference, *, weights=None):
    validate_range(frame[source], name=source)
    validate_range(frame[reference], name=reference)
    sample = match_sample(frame, [source, reference], weights=weights)
    rows = sample.rows
    rows["loss_source"] = brier_loss(rows[source], rows.y)
    rows["loss_reference"] = brier_loss(rows[reference], rows.y)
    denominator = _weighted_mean(rows.loss_reference, rows) if len(rows) else 0
    result = _result(sample, 1 - _weighted_mean(rows.loss_source, rows) / denominator if denominator else None)
    if len(rows) and denominator == 0:
        result.status = "unavailable"
        result.qualifications.append("Reference Brier loss is zero.")
    return result


def calls_correct(frame, source):
    validate_range(frame[source], name=source)
    sample = match_sample(frame, [source])
    rows = sample.rows
    rows["favorite"] = favorite(rows[source])
    made = rows.favorite.notna()
    correct = int(rows.loc[made, "favorite"].eq(rows.loc[made, "y"]).sum())
    value = {"correct": correct, "calls_made": int(made.sum()),
             "abstentions": int((~made).sum()), "accuracy": correct / made.sum() if made.any() else None}
    return _result(sample, value if len(rows) else None)


def vote_share_score(frame, source, *, metric="mae", peers=(), weights=None):
    # All peer compatibilities participate in the common eligibility mask.
    work = frame.copy()
    sources = [source, *peers]
    eligibility_columns = [c.replace("share_", "share_eligible_") for c in sources]
    work["_share_eligible"] = work[eligibility_columns].fillna(False).all(axis=1)
    sample = match_sample(work, sources, outcome="actual_share", eligibility="_share_eligible", weights=weights)
    rows = sample.rows
    rows["error"] = rows[source] - rows.actual_share
    validate_range(rows[source], name=source)
    validate_range(rows.actual_share, name="actual share")
    bias = _weighted_mean(rows.error, rows) if len(rows) else None
    rows["centered_error"] = rows.error - bias if bias is not None else pd.Series(dtype=float)
    if metric == "mae":
        values = rows.error.abs()
    elif metric == "bias":
        values = rows.error
    elif metric == "rmse":
        values = rows.error ** 2
    else:
        raise ValueError("metric must be mae, bias or rmse")
    value = _weighted_mean(values, rows) if len(rows) else None
    if metric == "rmse" and value is not None:
        value = float(np.sqrt(value))
    return _result(sample, value)


def expected_wins(frame, source):
    # Full-field forecast and resolved-race comparison have separate denominators.
    validate_range(frame[source], name=source)
    sample = match_sample(frame, [source])
    rows = sample.rows
    value = {
        "full_field_expected": float(frame[source].sum()) if frame[source].notna().all() else None,
        "full_field_n": len(frame),
        "eligible_expected": float(rows[source].sum()) if len(rows) else None,
        "eligible_actual": int(rows.y.sum()) if len(rows) else None,
        "signed_error": float(rows[source].sum() - rows.y.sum()) if len(rows) else None,
        "absolute_error": abs(float(rows[source].sum() - rows.y.sum())) if len(rows) else None,
        "all_resolved": len(rows) == len(frame),
    }
    return _result(sample, value)
