"""Compare M0 constant legacy vs M1 hierarchical spline."""

from __future__ import annotations

import math
from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import ModelComparisonResult
from string_technique_model.extrapolation.nonlinear.prediction import predict_register


def _rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    return float(math.sqrt(sum(e * e for e in errors) / len(errors)))


def _mae(errors: list[float]) -> float | None:
    if not errors:
        return None
    return float(sum(abs(e) for e in errors) / len(errors))


def compare_models(
    measured_rows: list[dict[str, Any]],
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    target_quantity: str = "EWSD_score_acoustic_balanced",
    min_holdout: int = 3,
) -> ModelComparisonResult:
    """Hold-out comparison when enough matched technique observations exist."""
    tech = str(technique).strip().lower()
    inst = str(instrument).strip().lower()
    dyn = str(dynamic).strip().lower()
    comparison_id = f"{inst}:{dyn}:{tech}:{target_quantity}"

    tech_rows = [
        r
        for r in measured_rows
        if str(r.get("technique", "")).lower() == tech
        and str(r.get("instrument", "")).lower() == inst
        and str(r.get("dynamic", "")).lower() == dyn
        and r.get("value") is not None
        and r.get("note")
    ]
    if len(tech_rows) < min_holdout:
        return ModelComparisonResult(
            comparison_id=comparison_id,
            instrument=inst,
            technique=tech,
            dynamic=dyn,
            target_quantity=target_quantity,
            status="insufficient_for_comparison",
            n_holdout=len(tech_rows),
            warnings=[f"Need at least {min_holdout} technique observations; have {len(tech_rows)}."],
        )

    ordinary_rows = [r for r in measured_rows if str(r.get("technique", "ordinary")).lower() in {"ordinary", "ordinario"}]
    errors_m0: list[float] = []
    errors_m1: list[float] = []
    coverage_m0 = coverage_m1 = 0
    n_eval = 0

    for held in tech_rows:
        train = [r for r in measured_rows if r is not held]
        note = str(held["note"])
        observed = float(held["value"])

        m0_preds = predict_register(
            ordinary_rows,
            technique=tech,
            instrument=inst,
            dynamic=dyn,
            pitches=[note],
            target_quantity=target_quantity,
            method="constant",
            technique_observations=[r for r in train if str(r.get("technique", "")).lower() == tech],
        )
        m1_preds = predict_register(
            ordinary_rows,
            technique=tech,
            instrument=inst,
            dynamic=dyn,
            pitches=[note],
            target_quantity=target_quantity,
            method="hierarchical_spline",
            technique_observations=[r for r in train if str(r.get("technique", "")).lower() == tech],
        )
        p0 = m0_preds[0].posterior_mean if m0_preds else None
        p1 = m1_preds[0].posterior_mean if m1_preds else None
        if p0 is None or p1 is None:
            continue
        errors_m0.append(observed - p0)
        errors_m1.append(observed - p1)
        lo0, hi0 = m0_preds[0].credible_interval_low, m0_preds[0].credible_interval_high
        lo1, hi1 = m1_preds[0].credible_interval_low, m1_preds[0].credible_interval_high
        if lo0 is not None and hi0 is not None and lo0 <= observed <= hi0:
            coverage_m0 += 1
        if lo1 is not None and hi1 is not None and lo1 <= observed <= hi1:
            coverage_m1 += 1
        n_eval += 1

    if n_eval < min_holdout:
        return ModelComparisonResult(
            comparison_id=comparison_id,
            instrument=inst,
            technique=tech,
            dynamic=dyn,
            target_quantity=target_quantity,
            status="insufficient_for_comparison",
            n_holdout=n_eval,
            warnings=["Too few evaluable hold-out notes after NA predictions."],
        )

    rmse0 = _rmse(errors_m0)
    rmse1 = _rmse(errors_m1)
    preferred = None
    if rmse0 is not None and rmse1 is not None:
        preferred = "M1_hierarchical_spline" if rmse1 < rmse0 else "M0_constant_legacy"

    return ModelComparisonResult(
        comparison_id=comparison_id,
        instrument=inst,
        technique=tech,
        dynamic=dyn,
        target_quantity=target_quantity,
        status="completed",
        n_holdout=n_eval,
        rmse_m0=rmse0,
        rmse_m1=rmse1,
        mae_m0=_mae(errors_m0),
        mae_m1=_mae(errors_m1),
        coverage_m0=coverage_m0 / n_eval if n_eval else None,
        coverage_m1=coverage_m1 / n_eval if n_eval else None,
        preferred_model=preferred,
        warnings=["coverage_metric_is_placeholder_interval_check"],
    )
