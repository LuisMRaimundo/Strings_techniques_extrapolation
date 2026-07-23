"""Mute submodel driven by model_selection marks.

spectral_transfer_model > scalar approximation > constant assumption > qualitative/NA
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from string_technique_model.extrapolation.nonlinear.baseline import BaselineFit, BaselineFitCollection
from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, SensitivityStatus, ValueKind
from string_technique_model.extrapolation.nonlinear.provenance import trace_mute_prediction
from string_technique_model.extrapolation.nonlinear.splines import fit_penalized_bspline, predict_bspline

_MUTE_TECHNIQUE = "con_sordino"
_HEAVY_MUTE_MARKERS = frozenset(
    {"heavy_practice", "practice_mute", "heavy", "metal", "weighted", "sordino_pesado"}
)
_LITERATURE_DB_PRIOR = {"vln": 6.0, "vla": 4.0}

ShapeMode = Literal["constant", "linear", "spline", "spectral", "qualitative"]


def _db_to_log_ratio(db: float) -> float:
    return math.log(10.0 ** (-float(db) / 10.0))


def _shape_mode_from_selection(selected_model_id: str) -> ShapeMode:
    mid = selected_model_id.lower()
    if "spectral" in mid:
        return "spectral"
    if "qualitative" in mid or mid.endswith("_na") or "na_mute" in mid:
        return "qualitative"
    if "spline" in mid:
        return "spline"
    if "linear" in mid:
        return "linear"
    return "constant"


def _fit_ridge_linear(x: np.ndarray, y: np.ndarray, lam: float = 1.0) -> tuple[float, float, float, float]:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    center = float(np.mean(x))
    xc = x - center
    denom = float(np.dot(xc, xc) + lam)
    slope = float(np.dot(xc, y) / denom) if denom > 0 else 0.0
    intercept = float(np.mean(y - slope * xc))
    resid = y - (intercept + slope * xc)
    sd = float(np.std(resid, ddof=1)) if len(resid) > 2 else float(np.std(resid))
    return intercept, slope, center, sd


@dataclass
class MuteFit:
    instrument: str
    dynamic: str
    alpha_mute: float
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
    evidence_tier: EvidenceTier = EvidenceTier.LEVEL_2_METADATA_CONSTRAINED
    model_reduction: str = "scalar_descriptor_approximation"
    prior_ids: list[str] = field(default_factory=list)
    record_ids: list[str] = field(default_factory=list)
    submodel_id: str = "mute_log_scalar"
    effect_kind: str = "user_assumption"
    alpha_origin: str = ""
    attenuation_db_power: float | None = None
    source_ids: list[str] = field(default_factory=list)
    marks: list[str] = field(default_factory=list)
    assumption_ids: list[str] = field(default_factory=list)

    @property
    def register_shape_identified(self) -> bool:
        return self.shape_mode in {"linear", "spline", "spectral"}

    @property
    def model_id(self) -> str:
        return self.selected_model_id

    @property
    def shape_source(self) -> str:
        return {
            "spline": "technique_observations_penalized_spline",
            "linear": "technique_observations_regularized_linear",
            "spectral": "spectral_transfer_A_m_f",
            "qualitative": "qualitative_only",
            "constant": "constant_effect",
        }[self.shape_mode]

    def log_ratio(self, midi: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        midi_arr = np.asarray(midi, dtype=float).ravel()
        outside = np.zeros(len(midi_arr), dtype=bool)
        if self.shape_mode in {"constant", "qualitative"}:
            return np.full(len(midi_arr), self.alpha_mute), outside
        if self.shape_mode == "linear":
            return self.alpha_mute + float(self.linear_slope or 0.0) * (
                midi_arr - float(self.midi_center or 0.0)
            ), outside
        if self.spline_coeffs is None or self.knots is None:
            return np.full(len(midi_arr), self.alpha_mute), outside
        g, outside = predict_bspline(midi_arr, self.knots, self.degree, self.spline_coeffs)
        return self.alpha_mute + g, outside

    def predict(self, baseline: BaselineFit, midi: float | np.ndarray) -> dict[str, Any]:
        if self.shape_mode == "qualitative":
            return {
                "mean": None,
                "na_reason": "qualitative_or_na_mute",
                "model_id": self.selected_model_id,
                "value_kind": ValueKind.QUALITATIVE_ONLY,
                "prior_dominated": True,
                "evidence_tier": EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE,
                "assumptions_used": ["numeric_assumption_not_authorized"],
                "warnings": ["Mute numeric extrapolation withheld."],
                "register_shape_identified": False,
                "shape_source": self.shape_source,
                "target_technique_observations": self.n_observations,
                "g_t_active": False,
                "marks": list(self.marks),
            }
        if self.shape_mode == "spectral":
            return {
                "mean": None,
                "na_reason": "spectral_transfer_pipeline_not_implemented",
                "model_id": "spectral_transfer_model",
                "value_kind": ValueKind.UNAVAILABLE,
                "prior_dominated": False,
                "evidence_tier": EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL,
                "assumptions_used": ["selected_spectral_transfer_but_A_m_f_fit_not_implemented"],
                "warnings": [
                    "Model selection chose spectral_transfer_model; LTAS/A_m(f) fitting not yet implemented.",
                    "Refusing silent scalar fallback that would mislabel the mechanism.",
                ],
                "register_shape_identified": True,
                "shape_source": "spectral_transfer_A_m_f",
                "target_technique_observations": self.n_observations,
                "g_t_active": False,
                "marks": ["spectral_transfer_model"],
            }

        b_mean, b_outside = baseline.predict(midi)
        log_r, r_outside = self.log_ratio(midi)
        mean = b_mean * np.exp(log_r)
        combined_outside = b_outside | r_outside
        log_ratio_sd = math.sqrt(self.alpha_sd**2 + self.residual_sd**2)
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
            "calculation_trace": trace_mute_prediction(
                instrument=self.instrument,
                alpha_mute=self.alpha_mute,
                n_obs=self.n_observations,
                prior_dominated=self.prior_dominated,
                model_reduction=self.model_reduction,
                register_shape_identified=self.register_shape_identified,
                model_id=self.model_id,
            ),
            "prior_dominated": self.prior_dominated,
            "evidence_tier": self.evidence_tier,
            "prior_ids": list(self.prior_ids),
            "source_ids": list(self.source_ids),
            "assumptions_used": list(self.assumption_ids)
            + [
                f"effect_kind={self.effect_kind}",
                f"alpha_origin={self.alpha_origin}",
                f"model_reduction={self.model_reduction}",
                f"marks={','.join(self.marks)}",
                "not_spectral_transfer_A_m_f" if "spectral" not in self.marks else "spectral_transfer",
                "interval_type=assumption_distribution_interval"
                if self.prior_dominated
                else "interval_type=approximate_predictive_interval_logR",
            ],
            "warnings": [
                "Mute scalar path is not equivalent to spectral_transfer_model.",
            ],
            "alpha_t": self.alpha_mute,
            "alpha_origin": self.alpha_origin,
            "effect_kind": self.effect_kind,
            "technique_multiplier": float(math.exp(self.alpha_mute))
            if self.shape_mode == "constant"
            else float(np.exp(float(log_r.ravel()[0]))),
            "attenuation_db_power": self.attenuation_db_power,
            "qualitative_effect_vs_ordinary": "reduces_radiated_power_proxy",
            "register_shape_identified": self.register_shape_identified,
            "shape_source": self.shape_source,
            "target_technique_observations": self.n_observations,
            "g_t_active": self.shape_mode != "constant",
            "model_id": self.model_id,
            "submodel_id": self.submodel_id,
            "model_reduction": self.model_reduction,
            "marks": list(self.marks),
            "sensitivity_status": (
                SensitivityStatus.OUTSIDE_BASELINE_RANGE
                if np.any(combined_outside)
                else SensitivityStatus.PRIOR_SENSITIVE
                if self.prior_dominated
                else SensitivityStatus.STABLE
            ),
            "value_kind": (
                ValueKind.ASSUMPTION_BASED_EXTRAPOLATION
                if self.shape_mode == "constant"
                else ValueKind.EXTRAPOLATED
            ),
        }


def _is_heavy_mute(row: pd.Series) -> bool:
    for col in ("mute_type", "mute_state", "technique_variant", "notes"):
        val = str(row.get(col) or "").lower().replace(" ", "_")
        if any(marker in val for marker in _HEAVY_MUTE_MARKERS):
            return True
    return False


def fit_mute_effect(
    ordinary_baseline: BaselineFitCollection | BaselineFit,
    technique_observations: pd.DataFrame | None,
    *,
    instrument: str,
    dynamic: str,
    selected_model_id: str = "constant_assumption_fallback",
    marks: list[str] | None = None,
) -> MuteFit | dict[str, Any]:
    inst = str(instrument).strip().lower()
    dyn = str(dynamic).strip().lower()
    shape_mode = _shape_mode_from_selection(selected_model_id)
    marks = list(marks or [])

    if isinstance(ordinary_baseline, BaselineFitCollection):
        baseline = ordinary_baseline.get(inst, dyn)
    else:
        baseline = ordinary_baseline
    if baseline is None:
        return {"refused": True, "reason": "missing_baseline", "evidence_tier": EvidenceTier.LEVEL_0_UNSUPPORTED}

    obs = technique_observations
    if obs is not None and not obs.empty:
        obs = obs[
            (obs["technique"].astype(str).str.lower() == _MUTE_TECHNIQUE)
            & (obs["instrument"].astype(str).str.lower() == inst)
            & (obs["dynamic"].astype(str).str.lower() == dyn)
        ]
        if any(_is_heavy_mute(row) for _, row in obs.iterrows()):
            return {
                "refused": True,
                "reason": "heavy_practice_mute_unsupported",
                "evidence_tier": EvidenceTier.LEVEL_0_UNSUPPORTED,
            }

    if inst in _LITERATURE_DB_PRIOR:
        db = float(_LITERATURE_DB_PRIOR[inst])
        alpha_prior = _db_to_log_ratio(db)
        alpha_sd = 0.35
        prior_ids = [f"alpha_mute_{inst}", "literature_db_power_proxy"]
        effect_kind = "user_assumption"
        alpha_origin = (
            f"configs/extrapolation_priors.yaml::alpha_mute_{inst} "
            f"(user_assumption: {db:g} dB power → 10^(-dB/10) on EWSD scalar)"
        )
        attenuation_db: float | None = db
        source_ids = []  # configured numeric assumption — not a bibliographic source id
        mute_assumption_ids = [
            f"ASSUMP_MUTE_ATTENUATION_{int(db)}DB",
            "ASSUMP_EWSD_PROPORTIONAL_TO_POWER",
        ]
    else:
        alpha_prior = -0.25
        alpha_sd = 0.9
        prior_ids = ["alpha_mute_generic"]
        effect_kind = "regularization_assumption"
        alpha_origin = "configs/extrapolation_priors.yaml::alpha_mute_generic"
        attenuation_db = None
        source_ids = []
        mute_assumption_ids = ["ASSUMP_MUTE_GENERIC_ALPHA"]

    if shape_mode == "qualitative":
        return MuteFit(
            instrument=inst,
            dynamic=dyn,
            alpha_mute=alpha_prior,
            alpha_sd=alpha_sd,
            shape_mode="qualitative",
            selected_model_id="qualitative_or_na_mute",
            n_observations=0,
            prior_dominated=True,
            evidence_tier=EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE,
            model_reduction="none",
            marks=["qualitative_or_na"],
            effect_kind="none",
            alpha_origin="numeric_withheld",
        )

    if shape_mode == "spectral":
        n_obs = 0 if obs is None or obs.empty else len(obs)
        return MuteFit(
            instrument=inst,
            dynamic=dyn,
            alpha_mute=alpha_prior,
            alpha_sd=alpha_sd,
            shape_mode="spectral",
            selected_model_id="spectral_transfer_model",
            n_observations=n_obs,
            prior_dominated=False,
            evidence_tier=EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL,
            model_reduction="none",
            marks=["spectral_transfer_model"],
            effect_kind="spectral_transfer",
            alpha_origin="spectral_A_m_f_required",
        )

    ratios: list[float] = []
    midis: list[float] = []
    record_ids: list[str] = []
    if obs is not None and not obs.empty:
        for _, row in obs.dropna(subset=["midi", "value"]).iterrows():
            b_mean, _ = baseline.predict(float(row["midi"]))
            b0 = float(np.asarray(b_mean).ravel()[0])
            if b0 <= 0:
                continue
            ratios.append(math.log(float(row["value"]) / b0))
            midis.append(float(row["midi"]))
            record_ids.append(str(row.get("source_path") or row.get("note")))

    n_obs = len(ratios)
    reduction = "scalar_descriptor_approximation"
    if "constant_assumption" in selected_model_id or shape_mode == "constant":
        marks = list(dict.fromkeys(marks + ["constant_assumption_fallback"]))
    else:
        marks = list(dict.fromkeys(marks + [reduction]))

    if shape_mode == "constant" or n_obs == 0:
        return MuteFit(
            instrument=inst,
            dynamic=dyn,
            alpha_mute=alpha_prior if n_obs == 0 else float(np.mean(ratios)),
            alpha_sd=alpha_sd,
            shape_mode="constant",
            selected_model_id=selected_model_id
            if "constant" in selected_model_id
            else "constant_assumption_fallback",
            residual_sd=0.0,
            n_observations=n_obs,
            prior_dominated=True,
            evidence_tier=EvidenceTier.LEVEL_1_ASSUMPTION_ONLY
            if n_obs == 0
            else EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL,
            model_reduction=reduction,
            prior_ids=prior_ids,
            record_ids=record_ids,
            effect_kind=effect_kind if n_obs == 0 else "partial_empirical_constant",
            alpha_origin=alpha_origin if n_obs == 0 else f"mean_log_ratio_n={n_obs}",
            attenuation_db_power=attenuation_db if n_obs == 0 else None,
            source_ids=source_ids,
            marks=marks,
            assumption_ids=mute_assumption_ids if n_obs == 0 else [],
        )

    x = np.asarray(midis, dtype=float)
    y = np.asarray(ratios, dtype=float)
    if shape_mode == "linear":
        intercept, slope, center, resid_sd = _fit_ridge_linear(x, y, lam=2.0)
        return MuteFit(
            instrument=inst,
            dynamic=dyn,
            alpha_mute=intercept,
            alpha_sd=max(alpha_sd * 0.7, 0.25),
            shape_mode="linear",
            selected_model_id="scalar_descriptor_approximation_linear",
            linear_slope=slope,
            midi_center=center,
            residual_sd=resid_sd,
            n_observations=n_obs,
            prior_dominated=False,
            evidence_tier=EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL,
            model_reduction=reduction,
            prior_ids=prior_ids,
            record_ids=record_ids,
            effect_kind="empirical_regularized_linear",
            alpha_origin=f"regularized_linear_mute_n={n_obs}",
            source_ids=["technique_observations"],
            marks=marks,
        )

    fit = fit_penalized_bspline(x, y, degree=3, n_basis=6, lam=2.0)
    alpha_hat = float(np.mean(y - fit.fitted))
    resid = y - (alpha_hat + fit.fitted)
    residual_sd = float(np.std(resid, ddof=1) or alpha_sd)
    return MuteFit(
        instrument=inst,
        dynamic=dyn,
        alpha_mute=alpha_hat,
        alpha_sd=max(alpha_sd * 0.5, 0.12),
        shape_mode="spline",
        selected_model_id="scalar_descriptor_approximation_spline",
        spline_coeffs=fit.coeffs,
        knots=fit.knots,
        degree=fit.degree,
        penalty=2.0,
        residual_sd=residual_sd,
        n_observations=n_obs,
        prior_dominated=False,
        evidence_tier=EvidenceTier.LEVEL_4_MATCHED_EMPIRICAL,
        model_reduction=reduction,
        prior_ids=prior_ids,
        record_ids=record_ids,
        effect_kind="empirical_register_spline",
        alpha_origin=f"empirical_mute_spline_n={n_obs}",
        source_ids=["technique_observations"],
        marks=marks,
    )
