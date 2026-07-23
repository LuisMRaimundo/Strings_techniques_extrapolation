"""Pydantic domain models for nonlinear hierarchical extrapolation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceTier(str, Enum):
    LEVEL_0_UNSUPPORTED = "LEVEL_0_UNSUPPORTED"
    LEVEL_1_ASSUMPTION_ONLY = "LEVEL_1_ASSUMPTION_ONLY"
    LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE = "LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE"
    LEVEL_2_METADATA_CONSTRAINED = "LEVEL_2_METADATA_CONSTRAINED"
    LEVEL_3_PARTIAL_EMPIRICAL = "LEVEL_3_PARTIAL_EMPIRICAL"
    LEVEL_4_MATCHED_EMPIRICAL = "LEVEL_4_MATCHED_EMPIRICAL"


class ValueKind(str, Enum):
    MEASURED = "measured"
    DERIVED_FROM_MEASURED = "derived_from_measured"
    EXTRAPOLATED = "extrapolated"
    APPROXIMATE_FROM_PENALIZED_FIT = "approximate_from_penalized_fit"
    ASSUMPTION_BASED_EXTRAPOLATION = "assumption_based_extrapolation"
    QUALITATIVE_ONLY = "qualitative_only"
    UNAVAILABLE = "unavailable"


class ConvergenceStatus(str, Enum):
    CONVERGED = "converged"
    APPROXIMATE_FREQUENTIST = "approximate_frequentist"
    DIVERGED = "diverged"
    NOT_APPLICABLE = "not_applicable"
    BACKEND_UNAVAILABLE = "backend_unavailable"


class SensitivityStatus(str, Enum):
    STABLE = "stable"
    PRIOR_SENSITIVE = "prior_sensitive"
    DATA_LIMITED = "data_limited"
    OUTSIDE_BASELINE_RANGE = "outside_baseline_range"
    NOT_EVALUATED = "not_evaluated"


class ExtrapolationModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    model_version: str = "1.0.0"
    description: str = ""
    method: Literal[
        "constant",
        "hierarchical_spline",
        "physical_informed_bayesian",
        "evidence_only",
    ] = "hierarchical_spline"
    submodel_ids: list[str] = Field(default_factory=list)
    enabled: bool = True


class BaselineModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spline_degree: int = 3
    n_basis: int = 8
    penalty_lambda: float = 1.0
    log_transform: bool = True
    quantity: str = "EWSD_score_acoustic_balanced"


class SplineSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    degree: int = 3
    n_basis: int = 8
    penalty_lambda: float = 1.0


class PriorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prior_id: str
    parameter: str
    family: str
    mean: float | None = None
    sd: float | None = None
    lower: float | None = None
    upper: float | None = None
    activation_status: Literal["active", "inactive", "fallback_only"] = "active"
    source: str | None = None
    notes: str | None = None


class BayesianSamplingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draws: int = 1000
    tune: int = 1000
    chains: int = 2
    target_accept: float = 0.9
    random_seed: int | None = 42


class TechniqueSubmodelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submodel_id: str
    technique: str
    model_family: Literal["log_ratio_spline", "mute_scalar", "harmonic_stub", "constant_legacy"]
    spline: SplineSpec = Field(default_factory=SplineSpec)
    min_observations: int = 3
    prior_ids: list[str] = Field(default_factory=list)


class PosteriorPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mean: float | None = None
    median: float | None = None
    sd: float | None = None
    log_ratio_mean: float | None = None
    log_ratio_sd: float | None = None
    credible_interval_low: float | None = None
    credible_interval_high: float | None = None
    credible_level: float = 0.95
    interval_kind: str = "approximate_interval_from_penalized_fit"
    interval_formula: str | None = None
    probability_above_ordinary: float | None = None


class PosteriorDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rhat_max: float | None = None
    ess_bulk_min: float | None = None
    ess_tail_min: float | None = None
    divergences: int | None = None
    flags: list[str] = Field(default_factory=list)


class ExtrapolationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_tier: EvidenceTier
    source_ids: list[str] = Field(default_factory=list)
    source_pages: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    extrapolation_distance: float | None = None
    prior_dominated: bool = False


class ExtrapolationResult(BaseModel):
    """Auditable nonlinear extrapolation output for one register cell."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    instrument: str
    technique: str
    dynamic: str
    pitch: str
    midi: int | None = None
    target_quantity: str
    # Neutral estimate fields (always preferred in exports)
    estimate_mean: float | None = None
    estimate_median: float | None = None
    estimate_sd: float | None = None
    interval_low: float | None = None
    interval_high: float | None = None
    # Bayesian-only fields (filled only when bayesian_backend_used)
    posterior_mean: float | None = None
    posterior_median: float | None = None
    posterior_sd: float | None = None
    credible_interval_low: float | None = None
    credible_interval_high: float | None = None
    bayesian_backend_used: bool = False
    log_ratio_mean: float | None = None
    log_ratio_sd: float | None = None
    technique_multiplier: float | None = None
    alpha_t: float | None = None
    alpha_origin: str | None = None
    effect_kind: str | None = None
    qualitative_effect_vs_ordinary: str | None = None
    attenuation_db_power: float | None = None
    credible_interval_probability: float | None = None
    interval_kind: str | None = None
    interval_type: str | None = None
    interval_formula: str | None = None
    sigma_origin: str | None = None
    sigma_value: float | None = None
    sigma_estimated_from_data: bool | None = None
    unit: str | None = None
    baseline_value: float | None = None
    baseline_record_ids: list[str] = Field(default_factory=list)
    baseline_n_observations: int | None = None
    baseline_midi_min: float | None = None
    baseline_midi_max: float | None = None
    baseline_penalty_lambda: float | None = None
    baseline_spline_degree: int | None = None
    baseline_n_knots: int | None = None
    data_status: Literal[
        "measured_real",
        "measured_research_data",
        "manual_register_entry",
        "synthetic",
        "synthetic_integration_test",
        "mixed",
        "unknown",
    ] = "unknown"
    scientific_use: str | None = None
    source_workbook_path: str | None = None
    source_workbook_hash: str | None = None
    source_sheet: str | None = None
    import_run_id: str | None = None
    source_row_ids: list[str] = Field(default_factory=list)
    model_id: str
    submodel_id: str | None = None
    model_version: str = "1.0.0"
    register_shape_identified: bool | None = False
    shape_source: str = "constant_effect"
    target_technique_observations: int | None = 0
    g_t_active: bool | None = False
    model_family: str | None = None
    selected_model_id: str | None = None
    candidate_model_ids: list[str] = Field(default_factory=list)
    rejected_model_ids: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    selection_reason: str | None = None
    fallback_level: str | None = None
    complexity_level: str | None = None
    model_selection_status: str | None = None
    distinct_pitch_count: int | None = None
    pitch_span_semitones: float | None = None
    required_covariates: list[str] = Field(default_factory=list)
    available_covariates: list[str] = Field(default_factory=list)
    missing_covariates: list[str] = Field(default_factory=list)
    missing_model_components: list[str] = Field(default_factory=list)
    modal_metadata_status: str | None = None
    acoustic_calibration_status: str | None = None
    model_comparison_available: bool = False
    assumption_ids: list[str] = Field(default_factory=list)
    assumptions_trace: list[str] = Field(default_factory=list)
    mechanism: str | None = None
    prior_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_pages: list[str] = Field(default_factory=list)
    # Deprecated alias: exporters map this to assumption_ids (ASSUMP_* only)
    assumptions_used: list[str] = Field(default_factory=list)
    evidence_tier: EvidenceTier
    extrapolation_distance: float | None = None
    measured_or_extrapolated: Literal["measured", "extrapolated", "unavailable"]
    value_kind: ValueKind
    warnings: list[str] = Field(default_factory=list)
    diagnostics_status: ConvergenceStatus = ConvergenceStatus.NOT_APPLICABLE
    convergence_status: ConvergenceStatus = ConvergenceStatus.NOT_APPLICABLE
    calculation_trace: list[str] = Field(default_factory=list)
    probability_above_ordinary: float | None = None
    assumption_probability_above_ordinary: float | None = None
    prior_dominated: bool | None = False
    sensitivity_status: SensitivityStatus = SensitivityStatus.NOT_EVALUATED
    string_name: str | None = None
    na_reason: str | None = None
    model_status: str | None = None
    # Harmonic production / sounding geometry
    harmonic_type: str | None = None
    harmonic_order: int | None = None
    production_pitch: str | None = None
    stopped_pitch: str | None = None
    touched_pitch: str | None = None
    open_string_pitch: str | None = None
    sounding_pitch: str | None = None
    sounding_midi: int | None = None
    sounding_midi_float: float | None = None
    sounding_frequency_hz: float | None = None
    nearest_tempered_pitch: str | None = None
    cents_deviation: float | None = None
    target_range_min: str | None = None
    target_range_max: str | None = None
    within_harmonic_analysis_range: bool | None = None
    within_ordinary_baseline_range: bool | None = None
    outside_ordinary_baseline_range: bool | None = None
    baseline_extrapolation_semitones: float | None = None
    feasibility_status: str | None = None
    pitch_generation_method: str | None = None
    target_status: str | None = None
    baseline_support_policy: str | None = None
    physical_range_min: str | None = None
    physical_range_max: str | None = None
    analysis_range_min: str | None = None
    analysis_range_max: str | None = None
    included_by_physical_model: bool | None = None
    included_by_analysis_filter: bool | None = None
    excluded_reason: str | None = None
    selection_mode: str | None = None
    configuration_policy: str | None = None
    configured_order_min: int | None = None
    configured_order_max: int | None = None
    order_selection_reason: str | None = None

    def to_row(self) -> dict[str, Any]:
        # Sync neutral estimate fields from legacy posterior_* when needed
        if self.estimate_mean is None and self.posterior_mean is not None:
            self.estimate_mean = self.posterior_mean
        if self.estimate_median is None and self.posterior_median is not None:
            self.estimate_median = self.posterior_median
        if self.estimate_sd is None and self.posterior_sd is not None:
            self.estimate_sd = self.posterior_sd
        if self.interval_low is None and self.credible_interval_low is not None:
            self.interval_low = self.credible_interval_low
        if self.interval_high is None and self.credible_interval_high is not None:
            self.interval_high = self.credible_interval_high
        if self.assumption_probability_above_ordinary is None and self.prior_dominated:
            self.assumption_probability_above_ordinary = self.probability_above_ordinary

        # assumption_ids = ASSUMP_* only; assumptions_trace = detailed prose
        ids = [a for a in (self.assumption_ids or []) if str(a).startswith("ASSUMP_")]
        if not ids:
            ids = [a for a in (self.assumptions_used or []) if str(a).startswith("ASSUMP_")]
        trace = list(self.assumptions_trace or [])
        if not trace:
            trace = [a for a in (self.assumptions_used or []) if not str(a).startswith("ASSUMP_")]
        self.assumption_ids = ids
        self.assumptions_trace = trace
        self.assumptions_used = list(ids)  # cleaned alias for older readers

        d = self.model_dump()
        for key in (
            "baseline_record_ids",
            "prior_ids",
            "source_ids",
            "source_pages",
            "assumptions_used",
            "assumptions_trace",
            "warnings",
            "calculation_trace",
            "candidate_model_ids",
            "rejected_model_ids",
            "rejection_reasons",
            "required_covariates",
            "available_covariates",
            "missing_covariates",
            "missing_model_components",
            "assumption_ids",
            "source_row_ids",
        ):
            if isinstance(d.get(key), list):
                d[key] = ";".join(str(x) for x in d[key])
        # Excel-friendly N/A for unavailable-before-shape models
        for key in (
            "register_shape_identified",
            "g_t_active",
            "prior_dominated",
            "sigma_estimated_from_data",
        ):
            if d.get(key) is None:
                d[key] = "not_applicable"
        if d.get("shape_source") in {None, ""}:
            d["shape_source"] = "not_applicable"
        d["evidence_tier"] = self.evidence_tier.value
        d["value_kind"] = self.value_kind.value
        d["diagnostics_status"] = self.diagnostics_status.value
        d["convergence_status"] = self.convergence_status.value
        d["sensitivity_status"] = self.sensitivity_status.value
        d["extrapolation_method"] = self.selected_model_id or self.model_id
        # Hide Bayesian column values unless backend actually ran
        if not self.bayesian_backend_used:
            d["posterior_mean"] = None
            d["posterior_median"] = None
            d["posterior_sd"] = None
            d["credible_interval_low"] = None
            d["credible_interval_high"] = None
            if self.prior_dominated:
                d["probability_above_ordinary"] = None
        return d


class ModelComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str
    instrument: str
    technique: str
    dynamic: str
    target_quantity: str
    status: Literal["completed", "insufficient_for_comparison", "skipped"]
    m0_model_id: str = "M0_constant_legacy"
    m1_model_id: str = "M1_hierarchical_spline"
    n_holdout: int = 0
    rmse_m0: float | None = None
    rmse_m1: float | None = None
    mae_m0: float | None = None
    mae_m1: float | None = None
    coverage_m0: float | None = None
    coverage_m1: float | None = None
    preferred_model: str | None = None
    warnings: list[str] = Field(default_factory=list)
