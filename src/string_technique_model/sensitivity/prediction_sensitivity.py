"""Sensitivity analysis for technique predictions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml
from string_technique_model.literature.outputs import write_csv, write_text
from string_technique_model.prediction.uncertainty import propagate_metric_only


def run_prediction_sensitivity(
    *,
    baseline: dict[str, Any],
    active_parameters: list[dict[str, Any]],
    link: str = "log",
    n_draws: int = 1000,
    random_seed: int = 20250723,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Prior-width / parameter-removal / transfer-off sensitivity.

    When no active parameters exist, records that sensitivity is not estimable.
    """
    out = Path(output_dir or PACKAGE_ROOT / "outputs" / "sensitivity")
    reports = PACKAGE_ROOT / "reports"
    cfg = load_yaml(PACKAGE_ROOT / "configs" / "prediction.yaml")
    factors = list((cfg.get("sensitivity") or {}).get("prior_width_factors") or [0.5, 1.0, 2.0])
    rows: list[dict[str, Any]] = []

    if not active_parameters:
        rows.append(
            {
                "analysis": "no_active_parameters",
                "result": "sensitivity_not_estimable",
                "note": "No active density parameters; refusing invented coefficients.",
            }
        )
        out.mkdir(parents=True, exist_ok=True)
        write_csv(out / "prediction_sensitivity.csv", rows)
        write_text(
            reports / "prediction_sensitivity_report.md",
            "# Prediction sensitivity report\n\n"
            "No active density parameters — sensitivity analysis has nothing numerical to perturb.\n",
        )
        return {"ran": True, "n_rows": len(rows), "active_parameters": 0}

    base = propagate_metric_only(
        baseline=baseline,
        active_params=active_parameters,
        link=link,
        n_draws=n_draws,
        random_seed=random_seed,
    )
    base_width = (
        None
        if base.estimated_density_q975 is None or base.estimated_density_q025 is None
        else float(base.estimated_density_q975 - base.estimated_density_q025)
    )
    rows.append(
        {
            "analysis": "baseline_active_set",
            "interval_width": base_width,
            "mean": base.estimated_density_mean,
        }
    )

    # Prior-width sensitivity: scale distribution sd when present
    for fac in factors:
        scaled = []
        for p in active_parameters:
            q = dict(p)
            dist = q.get("distribution_parameters")
            if isinstance(dist, dict) and "sd" in dist:
                dist = dict(dist)
                dist["sd"] = float(dist["sd"]) * float(fac)
                q["distribution_parameters"] = dist
                q["proposed_distribution"] = q.get("proposed_distribution") or "normal"
            scaled.append(q)
        dist_s = propagate_metric_only(
            baseline=baseline,
            active_params=scaled,
            link=link,
            n_draws=n_draws,
            random_seed=random_seed,
        )
        width = (
            None
            if dist_s.estimated_density_q975 is None
            else float(dist_s.estimated_density_q975 - dist_s.estimated_density_q025)
        )
        rows.append(
            {
                "analysis": "prior_width",
                "factor": fac,
                "interval_width": width,
                "mean": dist_s.estimated_density_mean,
            }
        )

    # Parameter-removal
    for p in active_parameters:
        remaining = [x for x in active_parameters if x.get("parameter_id") != p.get("parameter_id")]
        if not remaining:
            rows.append(
                {
                    "analysis": "parameter_removal",
                    "removed": p.get("parameter_id"),
                    "result": "no_parameters_remain",
                }
            )
            continue
        dist_r = propagate_metric_only(
            baseline=baseline,
            active_params=remaining,
            link=link,
            n_draws=n_draws,
            random_seed=random_seed,
        )
        rows.append(
            {
                "analysis": "parameter_removal",
                "removed": p.get("parameter_id"),
                "mean": dist_r.estimated_density_mean,
                "interval_width": (
                    None
                    if dist_r.estimated_density_q975 is None
                    else float(dist_r.estimated_density_q975 - dist_r.estimated_density_q025)
                ),
            }
        )

    # Transfer on vs off
    rows.append(
        {
            "analysis": "transfer_off_default",
            "transfer_enabled": False,
            "note": "Cross-instrument transfer disabled by default in prediction.yaml",
        }
    )

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "prediction_sensitivity.csv", rows)
    write_text(
        reports / "prediction_sensitivity_report.md",
        "# Prediction sensitivity report\n\n"
        f"Active parameters analysed: {len(active_parameters)}.\n"
        f"Prior-width factors: {factors}.\n",
    )
    return {"ran": True, "n_rows": len(rows), "active_parameters": len(active_parameters)}
