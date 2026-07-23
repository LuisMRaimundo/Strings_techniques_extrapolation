"""Bow-contact submodel (sul tasto / sul ponticello).

Complexity is chosen by ``model_selection``:
constant → linear trend → penalized spline → (physical-informed later).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from string_technique_model.extrapolation.nonlinear.baseline import BaselineFit, BaselineFitCollection
from string_technique_model.extrapolation.nonlinear.domain import (
    EvidenceTier,
    SensitivityStatus,
    TechniqueSubmodelSpec,
    ValueKind,
)
from string_technique_model.extrapolation.nonlinear.priors import get_prior
from string_technique_model.extrapolation.nonlinear.provenance import trace_log_ratio_prediction
from string_technique_model.extrapolation.nonlinear.splines import fit_penalized_bspline, predict_bspline

_BOW_TECHNIQUES = frozenset({"sul_tasto", "sul_ponticello"})

_LITERATURE_DIRECTION = {
    "sul_tasto": {
        "prior_id": "alpha_t_sul_tasto",
        "direction": "decrease",
        "qualitative": "tends_to_reduce_upper_partial_energy",
        "effect_kind": "regularization_assumption",
        "alpha_origin": "configs/extrapolation_priors.yaml::alpha_t_sul_tasto (regularization_assumption; not a measured coefficient)",
        "assumption_id": "ASSUMP_SUL_TASTO_ALPHA_MINUS_012",
    },
    "sul_ponticello": {
        "prior_id": "alpha_t_sul_ponticello",
        "direction": "increase",
        "qualitative": "tends_to_increase_upper_partial_energy_and_noise",
        "effect_kind": "regularization_assumption",
        "alpha_origin": "configs/extrapolation_priors.yaml::alpha_t_sul_ponticello (regularization_assumption; not inverse of sul_tasto)",
        "assumption_id": "ASSUMP_SUL_PONTICELLO_ALPHA_PLUS_020",
    },
}

ShapeMode = Literal["constant", "linear", "spline"]


@dataclass
class BowContactFit:
    technique: str
    instrument: str
    dynamic: str
    alpha_t: float
    alpha_sd: float
    shape_mode: ShapeMode
    selected_model_id: str
    linear_slope: float | None = None
    midi_center: float | None = None
    spline_coeffs: np.ndarray | None = None
    knots: np.ndarray | None = None
    degree: int = 3
    penalty: float = 1.0
    residual_sd: float = 0.0
    n_observations: int = 0
    prior_dominated: bool = True
    evidence_tier: EvidenceTier = EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE
    prior_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    submodel_id: str = "bow_contact_log_ratio"
    effect_kind: str = "regularization_assumption"
    alpha_origin: str = ""
    qualitative_effect: str = ""
    source_ids: list[str] = field(default_factory=list)
    assumption_ids: list[str] = field(default_factory=list)

    @property
    def register_shape_identified(self) -> bool:
        return self.shape_mode in {"linear", "spline"}

    @property
    def model_id(self) -> str:
        return self.selected_model_id

    @property
    def shape_source(self) -> str:
        if self.shape_mode == "spline":
            return "technique_observations_penalized_spline"
        if self.shape_mode == "linear":
            return "technique_observations_regularized_linear"
        return "constant_effect"

    def log_ratio(self, midi: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        midi_arr = np.asarray(midi, dtype=float).ravel()
        outside = np.zeros(len(midi_arr), dtype=bool)
        if self.shape_mode == "constant" or self.linear_slope is None and self.spline_coeffs is None:
            return np.full(len(midi_arr), self.alpha_t, dtype=float), outside
        if self.shape_mode == "linear":
            center = float(self.midi_center or 0.0)
            slope = float(self.linear_slope or 0.0)
            return self.alpha_t + slope * (midi_arr - center), outside
        g, outside = predict_bspline(midi_arr, self.knots, self.degree, self.spline_coeffs)  # type: ignore[arg-type]
        return self.alpha_t + g, outside

    def predict(self, baseline: BaselineFit, midi: float | np.ndarray) -> dict[str, Any]:
        b_mean, b_outside = baseline.predict(midi)
        log_r, r_outside = self.log_ratio(midi)
        mean = b_mean * np.exp(log_r)
        combined_outside = b_outside | r_outside
        log_ratio_sd = math.sqrt(self.alpha_sd**2 + self.residual_sd**2)
        assumptions = list(self.assumption_ids) + [
            f"effect_kind={self.effect_kind}",
            f"alpha_origin={self.alpha_origin}",
            f"shape_mode={self.shape_mode}",
            f"selected_model_id={self.selected_model_id}",
            "Y=B(p)*exp(logR(p))",
            "intervals_multiplicative_on_logR",
            "interval_type=assumption_distribution_interval"
            if self.prior_dominated
            else "interval_type=approximate_predictive_interval_logR",
        ]
        if self.technique in _BOW_TECHNIQUES:
            assumptions.append("sul_tasto_and_sul_ponticello_are_not_inverse_transforms")

        warnings: list[str] = []
        if self.shape_mode == "constant":
            warnings.append(
                "register_shape_identified=false: constant technique effect; "
                "only ordinary baseline may be nonlinear."
            )

        return {
            "mean": mean,
            "log_ratio_mean": log_r,
            "log_ratio_sd": log_ratio_sd,
            "uncertainty_scale": "logR",
            "sigma_origin": (
                "prior_config_alpha_sd_not_estimated_from_data"
                if self.prior_dominated
                else "logR_fit_residual_and_alpha_sd"
            ),
            "sigma_value": log_ratio_sd,
            "sigma_estimated_from_data": False if self.prior_dominated else True,
            "assumption_ids": list(self.assumption_ids),
            "outside_range": combined_outside,
            "baseline_mean": b_mean,
            "baseline_record_ids": list(baseline.record_ids),
            "baseline_n_observations": baseline.n_observations,
            "baseline_midi_min": baseline.midi_min,
            "baseline_midi_max": baseline.midi_max,
            "baseline_penalty_lambda": baseline.penalty,
            "baseline_spline_degree": baseline.degree,
            "baseline_n_knots": int(len(baseline.knots)),
            "calculation_trace": trace_log_ratio_prediction(
                technique=self.technique,
                alpha_t=self.alpha_t,
                n_obs=self.n_observations,
                prior_dominated=self.prior_dominated,
                register_shape_identified=self.register_shape_identified,
                model_id=self.model_id,
            ),
            "prior_dominated": self.prior_dominated,
            "evidence_tier": self.evidence_tier,
            "prior_ids": list(self.prior_ids),
            "source_ids": list(self.source_ids),
            "assumptions_used": assumptions,
            "warnings": warnings,
            "alpha_t": self.alpha_t,
            "alpha_origin": self.alpha_origin,
            "effect_kind": self.effect_kind,
            "technique_multiplier": float(np.exp(float(log_r.ravel()[0]))),
            "qualitative_effect_vs_ordinary": self.qualitative_effect,
            "register_shape_identified": self.register_shape_identified,
            "shape_source": self.shape_source,
            "target_technique_observations": self.n_observations,
            "g_t_active": self.shape_mode != "constant",
            "model_id": self.model_id,
            "submodel_id": self.submodel_id,
            "sensitivity_status": (
                SensitivityStatus.OUTSIDE_BASELINE_RANGE
                if np.any(combined_outside)
                else (
                    SensitivityStatus.PRIOR_SENSITIVE
                    if self.prior_dominated
                    else SensitivityStatus.DATA_LIMITED
                    if self.n_observations < 3
                    else SensitivityStatus.STABLE
                )
            ),
            "value_kind": (
                ValueKind.ASSUMPTION_BASED_EXTRAPOLATION
                if self.shape_mode == "constant"
                else ValueKind.EXTRAPOLATED
            ),
        }


def _prior_log_normal_center(prior_id: str) -> tuple[float, float]:
    spec = get_prior(prior_id)
    if spec is None or spec.mean is None:
        return 0.0, 1.0
    return float(spec.mean), float(spec.sd or 1.0)


def _shape_mode_from_selection(selected_model_id: str) -> ShapeMode:
    mid = selected_model_id.lower()
    if "spline" in mid:
        return "spline"
    if "linear" in mid:
        return "linear"
    return "constant"


def _fit_ridge_linear(x: np.ndarray, y: np.ndarray, lam: float = 1.0) -> tuple[float, float, float]:
    """Return intercept-at-center, slope, residual_sd for y ≈ a + b*(x-x̄)."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    center = float(np.mean(x))
    xc = x - center
    # ridge on slope only
    denom = float(np.dot(xc, xc) + lam)
    slope = float(np.dot(xc, y) / denom) if denom > 0 else 0.0
    intercept = float(np.mean(y - slope * xc))
    resid = y - (intercept + slope * xc)
    sd = float(np.std(resid, ddof=1)) if len(resid) > 2 else float(np.std(resid))
    return intercept, slope, sd


def fit_bow_contact_effect(
    ordinary_baseline: BaselineFitCollection | BaselineFit,
    technique_observations: pd.DataFrame | None,
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    selected_model_id: str = "constant_technique_effect_over_smoothed_baseline",
    spec: TechniqueSubmodelSpec | None = None,
) -> BowContactFit | None:
    """Fit logR according to the selected complexity rung."""
    tech = str(technique).strip().lower()
    if tech not in _BOW_TECHNIQUES:
        return None

    inst = str(instrument).strip().lower()
    dyn = str(dynamic).strip().lower()
    shape_mode = _shape_mode_from_selection(selected_model_id)
    spec = spec or TechniqueSubmodelSpec(
        submodel_id="bow_contact_log_ratio",
        technique=tech,
        model_family="log_ratio_spline",
    )

    if isinstance(ordinary_baseline, BaselineFitCollection):
        baseline = ordinary_baseline.get(inst, dyn)
    else:
        baseline = ordinary_baseline
    if baseline is None:
        return None

    meta = _LITERATURE_DIRECTION[tech]
    prior_id = meta["prior_id"]
    alpha_prior_mean, alpha_prior_sd = _prior_log_normal_center(prior_id)

    obs = technique_observations
    if obs is not None and not obs.empty:
        obs = obs[
            (obs["technique"].astype(str).str.lower() == tech)
            & (obs["instrument"].astype(str).str.lower() == inst)
            & (obs["dynamic"].astype(str).str.lower() == dyn)
        ].dropna(subset=["midi", "value"])

    ratios: list[float] = []
    midis: list[float] = []
    record_ids: list[str] = []
    if obs is not None and not obs.empty:
        for _, row in obs.iterrows():
            b_mean, _ = baseline.predict(float(row["midi"]))
            b0 = float(np.asarray(b_mean).ravel()[0])
            if b0 <= 0:
                continue
            ratios.append(math.log(float(row["value"]) / b0))
            midis.append(float(row["midi"]))
            record_ids.append(str(row.get("source_path") or row.get("note")))

    n_obs = len(ratios)

    if shape_mode == "constant" or n_obs == 0:
        return BowContactFit(
            technique=tech,
            instrument=inst,
            dynamic=dyn,
            alpha_t=alpha_prior_mean if n_obs == 0 else float(np.mean(ratios)),
            alpha_sd=max(alpha_prior_sd, 0.45),
            shape_mode="constant",
            selected_model_id=selected_model_id
            if "constant" in selected_model_id
            else "constant_technique_effect_over_smoothed_baseline",
            residual_sd=0.0 if n_obs == 0 else max(float(np.std(ratios, ddof=1)) if n_obs > 1 else 0.0, 0.0),
            n_observations=n_obs,
            prior_dominated=n_obs < 3,
            evidence_tier=(
                EvidenceTier.LEVEL_1_ASSUMPTION_ONLY
                if n_obs == 0
                else EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL
            ),
            prior_ids=[prior_id],
            record_ids=record_ids,
            submodel_id=spec.submodel_id,
            effect_kind=str(meta["effect_kind"]) if n_obs == 0 else "partial_empirical_constant",
            alpha_origin=str(meta["alpha_origin"])
            if n_obs == 0
            else f"mean_log_ratio_n={n_obs}",
            qualitative_effect=str(meta["qualitative"]),
            # Do not put effect_kind labels into source_ids — those are not bibliographic sources.
            source_ids=[] if n_obs == 0 else ["partial_empirical"],
            assumption_ids=[str(meta["assumption_id"])] if n_obs == 0 else [],
        )

    x = np.asarray(midis, dtype=float)
    y = np.asarray(ratios, dtype=float)

    if shape_mode == "linear":
        intercept, slope, resid_sd = _fit_ridge_linear(x, y, lam=2.0)
        return BowContactFit(
            technique=tech,
            instrument=inst,
            dynamic=dyn,
            alpha_t=intercept,
            alpha_sd=max(alpha_prior_sd * 0.7, 0.25),
            shape_mode="linear",
            selected_model_id="regularized_linear_register_trend",
            linear_slope=slope,
            midi_center=float(np.mean(x)),
            residual_sd=resid_sd,
            n_observations=n_obs,
            prior_dominated=False,
            evidence_tier=EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL,
            prior_ids=[prior_id],
            record_ids=record_ids,
            submodel_id=spec.submodel_id,
            effect_kind="empirical_regularized_linear",
            alpha_origin=f"regularized_linear_log_ratio_n={n_obs}",
            qualitative_effect=str(meta["qualitative"]),
            source_ids=["technique_observations"],
        )

    # spline
    fit = fit_penalized_bspline(
        x,
        y,
        degree=spec.spline.degree,
        n_basis=spec.spline.n_basis,
        lam=spec.spline.penalty_lambda,
    )
    alpha_hat = float(np.mean(y - fit.fitted))
    resid = y - (alpha_hat + fit.fitted)
    residual_sd = float(np.std(resid, ddof=min(1, len(resid) - 1)) or alpha_prior_sd)
    return BowContactFit(
        technique=tech,
        instrument=inst,
        dynamic=dyn,
        alpha_t=alpha_hat,
        alpha_sd=max(alpha_prior_sd * 0.5, 0.15),
        shape_mode="spline",
        selected_model_id="penalized_register_spline",
        spline_coeffs=fit.coeffs,
        knots=fit.knots,
        degree=fit.degree,
        penalty=spec.spline.penalty_lambda,
        residual_sd=residual_sd,
        n_observations=n_obs,
        prior_dominated=False,
        evidence_tier=EvidenceTier.LEVEL_4_MATCHED_EMPIRICAL,
        prior_ids=[prior_id],
        record_ids=record_ids,
        submodel_id=spec.submodel_id,
        effect_kind="empirical_register_spline",
        alpha_origin=f"empirical_log_ratio_spline_n={n_obs}",
        qualitative_effect=str(meta["qualitative"]),
        source_ids=["technique_observations"],
    )
