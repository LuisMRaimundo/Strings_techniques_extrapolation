"""Orchestrate nonlinear technique register predictions."""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

import numpy as np
import pandas as pd

from string_technique_model.extrapolation.density_effects import estimate_technique_density
from string_technique_model.extrapolation.nonlinear.baseline import BaselineFitCollection, fit_ordinary_baseline
from string_technique_model.extrapolation.nonlinear.bayesian_backend import check_backend, fit_bayesian_log_ratio_spline
from string_technique_model.extrapolation.nonlinear.bow_contact_model import fit_bow_contact_effect
from string_technique_model.extrapolation.nonlinear.data_preparation import filter_ordinary, normalize_measured_rows
from string_technique_model.extrapolation.nonlinear.descriptor_model import (
    descriptor_spec,
    ewsd_mapping_status,
    ewsd_model_assumptions,
    mapping_allows_numeric_extrapolation,
)
from string_technique_model.extrapolation.nonlinear.diagnostics import from_frequentist_flags
from string_technique_model.extrapolation.nonlinear.domain import (
    ConvergenceStatus,
    EvidenceTier,
    ExtrapolationResult,
    SensitivityStatus,
    ValueKind,
)
from string_technique_model.extrapolation.nonlinear.harmonic_model import predict_harmonic_register
from string_technique_model.extrapolation.nonlinear.harmonic_register import (
    annotate_baseline_extrapolation,
    generate_harmonic_targets,
    load_harmonic_range_config,
)
from string_technique_model.extrapolation.nonlinear.model_selection import (
    ModelSelectionDecision,
    assess_data_availability,
    select_model,
)
from string_technique_model.extrapolation.nonlinear.mute_model import fit_mute_effect
from string_technique_model.extrapolation.nonlinear.posterior import (
    apply_posterior_to_result,
    summarize_frequentist,
    summarize_log_ratio_multiplicative,
)
from string_technique_model.extrapolation.nonlinear.provenance import trace_baseline_prediction, trace_constant_legacy
from string_technique_model.extrapolation.register_builder import resolve_note

MethodName = Literal["constant", "hierarchical_spline", "physical_informed_bayesian", "evidence_only"]

_HARMONIC_TECHNIQUES = frozenset({"artificial_harmonic", "natural_harmonic"})
_BOW_TECHNIQUES = frozenset({"sul_tasto", "sul_ponticello"})
_MUTE_TECHNIQUE = "con_sordino"


def _new_record_id() -> str:
    return str(uuid.uuid4())


def _extrapolation_distance(midi: float | None, midi_min: float, midi_max: float) -> float | None:
    if midi is None:
        return None
    if midi < midi_min:
        return float(midi_min - midi)
    if midi > midi_max:
        return float(midi - midi_max)
    return 0.0


def infer_data_status(
    rows: list[dict[str, Any]],
) -> Literal[
    "measured_real",
    "measured_research_data",
    "manual_register_entry",
    "synthetic",
    "synthetic_integration_test",
    "mixed",
    "unknown",
]:
    """Classify whether ordinary inputs look measured, synthetic, or mixed."""
    known = {
        "measured_real",
        "measured_research_data",
        "manual_register_entry",
        "synthetic",
        "synthetic_integration_test",
        "mixed",
        "unknown",
    }
    flags: set[str] = set()
    for r in rows:
        explicit = str(r.get("data_status") or "").strip().lower()
        if explicit in known:
            flags.add(explicit)
            continue
        blob = " ".join(
            str(r.get(k) or "")
            for k in ("source_path", "metadata", "note", "provenance", "data_status")
        ).lower()
        meta = r.get("metadata")
        if isinstance(meta, dict):
            blob += " " + " ".join(str(v) for v in meta.values()).lower()
            ds = str(meta.get("data_status") or "").lower()
            if ds in known:
                flags.add(ds)
                continue
        if "synthetic_integration_test" in blob or "integration_test" in blob:
            flags.add("synthetic_integration_test")
        elif "synthetic" in blob:
            flags.add("synthetic")
        elif "gui_manual_entry" in blob or "manual_register" in blob:
            flags.add("manual_register_entry")
        elif "measured_research" in blob or r.get("source_workbook_path"):
            flags.add("measured_research_data")
        elif r.get("value") is not None and (
            r.get("source_path") or (isinstance(meta, dict) and meta.get("source_path"))
        ):
            flags.add("measured_real")
        elif r.get("value") is not None:
            flags.add("unknown")
    if len(flags) == 1:
        return next(iter(flags))  # type: ignore[return-value]
    if "measured_research_data" in flags and not (flags & {"synthetic", "synthetic_integration_test"}):
        return "measured_research_data"
    if {"measured_real", "measured_research_data", "manual_register_entry"} & flags and {
        "synthetic",
        "synthetic_integration_test",
    } & flags:
        return "mixed"
    if flags <= {"synthetic", "synthetic_integration_test"}:
        return "synthetic_integration_test" if "synthetic_integration_test" in flags else "synthetic"
    if "manual_register_entry" in flags:
        return "manual_register_entry"
    if flags & {"measured_real", "measured_research_data"}:
        return "measured_research_data" if "measured_research_data" in flags else "measured_real"
    return "unknown"


def _provenance_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract shared workbook provenance from measured ordinary rows."""
    path = next((r.get("source_workbook_path") for r in rows if r.get("source_workbook_path")), None)
    sheet = next((r.get("source_sheet") for r in rows if r.get("source_sheet")), None)
    hsh = next((r.get("source_workbook_hash") for r in rows if r.get("source_workbook_hash")), None)
    run_id = next((r.get("import_run_id") for r in rows if r.get("import_run_id")), None)
    row_ids = [str(r.get("source_path") or r.get("source_row_id") or "") for r in rows]
    row_ids = [x for x in row_ids if x]
    scientific_use = next((r.get("scientific_use") for r in rows if r.get("scientific_use")), None)
    return {
        "source_workbook_path": path,
        "source_sheet": sheet,
        "source_workbook_hash": hsh,
        "import_run_id": run_id,
        "source_row_ids": row_ids,
        "scientific_use": scientific_use,
    }


def fit_technique_effect(
    baseline: BaselineFitCollection,
    technique_observations: pd.DataFrame | None,
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    selected_model_id: str | None = None,
    marks: list[str] | None = None,
) -> Any:
    """Dispatch technique submodel fitting using the selected model id."""
    tech = str(technique).strip().lower()
    if tech in _BOW_TECHNIQUES:
        return fit_bow_contact_effect(
            baseline,
            technique_observations,
            technique=tech,
            instrument=instrument,
            dynamic=dynamic,
            selected_model_id=selected_model_id
            or "constant_technique_effect_over_smoothed_baseline",
        )
    if tech == _MUTE_TECHNIQUE:
        return fit_mute_effect(
            baseline,
            technique_observations,
            instrument=instrument,
            dynamic=dynamic,
            selected_model_id=selected_model_id or "constant_assumption_fallback",
            marks=marks,
        )
    if tech in _HARMONIC_TECHNIQUES:
        return {"stub": True, "technique": tech, "selected_model_id": selected_model_id}
    return None


def _attach_selection_fields(
    result: ExtrapolationResult,
    decision: ModelSelectionDecision,
) -> ExtrapolationResult:
    result.model_family = decision.model_family
    result.selected_model_id = decision.selected_model_id
    result.candidate_model_ids = list(decision.candidate_model_ids)
    result.rejected_model_ids = list(decision.rejected_model_ids)
    result.rejection_reasons = decision.rejection_reason_list()
    result.selection_reason = decision.selection_reason
    result.fallback_level = decision.fallback_level
    result.complexity_level = decision.complexity_level
    result.model_selection_status = decision.model_selection_status
    result.distinct_pitch_count = decision.distinct_pitch_count
    result.pitch_span_semitones = decision.pitch_span_semitones
    result.required_covariates = list(decision.required_covariates)
    result.available_covariates = list(decision.available_covariates)
    result.missing_covariates = list(decision.missing_covariates)
    result.missing_model_components = list(decision.missing_model_components)
    result.modal_metadata_status = decision.modal_metadata_status
    result.acoustic_calibration_status = decision.acoustic_calibration_status
    result.model_comparison_available = decision.model_comparison_available
    result.assumption_ids = list(
        dict.fromkeys(list(result.assumption_ids or []) + list(decision.assumption_ids))
    )
    result.mechanism = decision.mechanism
    result.target_technique_observations = decision.target_technique_observations
    result.register_shape_identified = decision.register_shape_identified
    # assumption_ids = ASSUMP_* only; assumptions_trace = explanatory detail
    merged = [
        a
        for a in list(result.assumptions_used or []) + list(result.assumptions_trace or [])
        if not str(a).startswith("selection_reason=")
        and not str(a).startswith("fallback_level=")
    ]
    for aid in decision.assumption_ids:
        if aid not in merged:
            merged.append(aid)
    for aid in result.assumption_ids or []:
        if aid not in merged:
            merged.append(aid)
    assumps = [a for a in merged if str(a).startswith("ASSUMP_")]
    other = [a for a in merged if not str(a).startswith("ASSUMP_")]
    result.assumption_ids = list(dict.fromkeys(assumps))
    result.assumptions_trace = list(dict.fromkeys(other))
    result.assumptions_used = list(result.assumption_ids)
    if decision.evidence_tier_hint:
        try:
            result.evidence_tier = EvidenceTier(decision.evidence_tier_hint)
        except ValueError:
            pass
    if result.model_status is None:
        status = decision.model_selection_status or ""
        if result.model_family == "harmonic_modal_model" or (
            result.technique or ""
        ).endswith("harmonic"):
            if result.selected_model_id == "harmonic_modal_acoustic_model_unavailable":
                result.model_status = "modal_frequencies_generated_acoustic_values_unavailable"
            elif result.selected_model_id == "harmonic_modal_metadata_gate":
                result.model_status = "unavailable_before_modal_estimation"
            else:
                result.model_status = "modal_frequencies_generated_acoustic_values_unavailable"
        elif "unavailable" in status or result.value_kind == ValueKind.UNAVAILABLE:
            result.model_status = "unavailable_before_shape_estimation"
        elif "assumption" in status or result.prior_dominated is True:
            result.model_status = "assumption_fallback_applied"
        elif decision.register_shape_identified:
            result.model_status = "register_shape_identified"
        else:
            result.model_status = "selected"
    return result


def _rows_to_frame(measured_ordinary_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return normalize_measured_rows(measured_ordinary_rows)


def _result_from_prediction(
    *,
    pitch: str,
    midi: int | None,
    instrument: str,
    technique: str,
    dynamic: str,
    target_quantity: str,
    prediction: dict[str, Any],
    model_id: str,
    submodel_id: str | None,
    baseline_fit: BaselineFitCollection | None = None,
    data_status: Literal["measured_real", "synthetic", "mixed", "unknown"] = "unknown",
    decision: ModelSelectionDecision | None = None,
) -> ExtrapolationResult:
    # Unavailable / qualitative paths from submodels
    if prediction.get("mean") is None and prediction.get("na_reason"):
        vk = prediction.get("value_kind", ValueKind.UNAVAILABLE)
        if isinstance(vk, str):
            vk = ValueKind(vk)
        result = ExtrapolationResult(
            record_id=_new_record_id(),
            instrument=instrument,
            technique=technique,
            dynamic=dynamic,
            pitch=pitch,
            midi=midi,
            target_quantity=target_quantity,
            model_id=str(prediction.get("model_id") or model_id),
            submodel_id=submodel_id,
            evidence_tier=prediction.get("evidence_tier", EvidenceTier.LEVEL_0_UNSUPPORTED),
            measured_or_extrapolated="unavailable",
            value_kind=vk,
            warnings=list(prediction.get("warnings") or []),
            assumptions_used=list(prediction.get("assumptions_used") or []),
            na_reason=str(prediction.get("na_reason")),
            data_status=data_status,
            register_shape_identified=bool(prediction.get("register_shape_identified", False)),
            shape_source=str(prediction.get("shape_source") or "constant_effect"),
            target_technique_observations=int(prediction.get("target_technique_observations") or 0),
            g_t_active=bool(prediction.get("g_t_active", False)),
            prior_dominated=bool(prediction.get("prior_dominated", True)),
        )
        if decision is not None:
            result = _attach_selection_fields(result, decision)
        return result

    baseline_mean = prediction.get("baseline_mean")
    if isinstance(baseline_mean, np.ndarray):
        baseline_mean = float(baseline_mean.ravel()[0])

    log_r = prediction.get("log_ratio_mean")
    if isinstance(log_r, np.ndarray):
        log_r_val = float(log_r.ravel()[0])
    elif log_r is not None:
        log_r_val = float(log_r)
    else:
        log_r_val = None

    log_ratio_sd = prediction.get("log_ratio_sd")
    if isinstance(log_ratio_sd, np.ndarray):
        log_ratio_sd = float(log_ratio_sd.ravel()[0])

    prior_dom = bool(prediction.get("prior_dominated"))
    if (
        prediction.get("uncertainty_scale") == "logR"
        and baseline_mean is not None
        and log_r_val is not None
    ):
        posterior = summarize_log_ratio_multiplicative(
            baseline=float(baseline_mean),
            log_ratio_mean=log_r_val,
            log_ratio_sd=float(log_ratio_sd) if log_ratio_sd is not None else None,
            prior_dominated=prior_dom,
            sigma_origin=prediction.get("sigma_origin"),
        )
    else:
        mean_arr = prediction.get("mean")
        if isinstance(mean_arr, np.ndarray):
            mean_val = float(mean_arr.ravel()[0])
            sd_arr = prediction.get("sd")
            sd_val = float(sd_arr.ravel()[0]) if isinstance(sd_arr, np.ndarray) else None
        else:
            mean_raw = prediction.get("mean")
            mean_val = float(mean_raw) if mean_raw is not None else float("nan")
            sd_raw = prediction.get("sd")
            sd_val = float(sd_raw) if sd_raw is not None else None
        posterior = summarize_frequentist(
            float(mean_val),
            float(sd_val) if sd_val is not None else None,
            baseline_mean=float(baseline_mean) if baseline_mean is not None else None,
        )
    post_fields = apply_posterior_to_result(
        posterior,
        prior_dominated=prior_dom,
        sigma_origin=prediction.get("sigma_origin"),
        sigma_value=float(log_ratio_sd) if log_ratio_sd is not None else prediction.get("sigma_value"),
        sigma_estimated_from_data=prediction.get("sigma_estimated_from_data"),
    )

    outside = prediction.get("outside_range")
    outside_flag = bool(np.any(outside)) if isinstance(outside, np.ndarray) else bool(outside)

    midi_min = prediction.get("baseline_midi_min")
    midi_max = prediction.get("baseline_midi_max")
    if baseline_fit is not None:
        fit = baseline_fit.get(instrument, dynamic)
        if fit is not None:
            midi_min, midi_max = fit.midi_min, fit.midi_max

    extrap_dist = None
    if midi is not None and midi_min is not None and midi_max is not None:
        extrap_dist = _extrapolation_distance(float(midi), float(midi_min), float(midi_max))

    spec = descriptor_spec(target_quantity)
    unit = spec.get("unit") if spec else None

    resolved_model_id = str(prediction.get("model_id") or model_id)
    resolved_submodel = prediction.get("submodel_id") or submodel_id

    result = ExtrapolationResult(
        record_id=_new_record_id(),
        instrument=instrument,
        technique=technique,
        dynamic=dynamic,
        pitch=pitch,
        midi=midi,
        target_quantity=target_quantity,
        unit=unit,
        baseline_value=float(baseline_mean) if baseline_mean is not None else None,
        baseline_record_ids=list(prediction.get("baseline_record_ids") or []),
        baseline_n_observations=prediction.get("baseline_n_observations"),
        baseline_midi_min=float(midi_min) if midi_min is not None else None,
        baseline_midi_max=float(midi_max) if midi_max is not None else None,
        baseline_penalty_lambda=prediction.get("baseline_penalty_lambda"),
        baseline_spline_degree=prediction.get("baseline_spline_degree"),
        baseline_n_knots=prediction.get("baseline_n_knots"),
        data_status=data_status,
        model_id=resolved_model_id,
        submodel_id=resolved_submodel,
        prior_ids=list(prediction.get("prior_ids") or []),
        source_ids=list(prediction.get("source_ids") or []),
        source_pages=list(prediction.get("source_pages") or []),
        evidence_tier=prediction.get("evidence_tier", EvidenceTier.LEVEL_1_ASSUMPTION_ONLY),
        extrapolation_distance=extrap_dist,
        measured_or_extrapolated="extrapolated",
        value_kind=prediction.get("value_kind", ValueKind.EXTRAPOLATED),
        warnings=list(prediction.get("warnings") or []),
        diagnostics_status=from_frequentist_flags(
            outside_range=outside_flag,
            prior_dominated=bool(prediction.get("prior_dominated")),
        ),
        convergence_status=from_frequentist_flags(
            outside_range=outside_flag,
            prior_dominated=bool(prediction.get("prior_dominated")),
        ),
        calculation_trace=list(prediction.get("calculation_trace") or []),
        prior_dominated=bool(prediction.get("prior_dominated")),
        sensitivity_status=prediction.get("sensitivity_status", SensitivityStatus.NOT_EVALUATED),
        na_reason=prediction.get("na_reason"),
        estimate_mean=post_fields.get("posterior_mean"),
        estimate_median=post_fields.get("posterior_median"),
        estimate_sd=post_fields.get("posterior_sd"),
        interval_low=post_fields.get("credible_interval_low"),
        interval_high=post_fields.get("credible_interval_high"),
        # Keep posterior_* empty unless a Bayesian backend filled them later.
        posterior_mean=None,
        posterior_median=None,
        posterior_sd=None,
        credible_interval_low=None,
        credible_interval_high=None,
        bayesian_backend_used=bool(prediction.get("bayesian_backend_used", False)),
        log_ratio_mean=post_fields.get("log_ratio_mean"),
        log_ratio_sd=post_fields.get("log_ratio_sd"),
        technique_multiplier=prediction.get("technique_multiplier"),
        alpha_t=prediction.get("alpha_t"),
        alpha_origin=prediction.get("alpha_origin"),
        effect_kind=prediction.get("effect_kind"),
        qualitative_effect_vs_ordinary=prediction.get("qualitative_effect_vs_ordinary"),
        attenuation_db_power=prediction.get("attenuation_db_power"),
        credible_interval_probability=post_fields.get("credible_interval_probability"),
        interval_kind=post_fields.get("interval_kind"),
        interval_type=post_fields.get("interval_type"),
        interval_formula=post_fields.get("interval_formula"),
        sigma_origin=post_fields.get("sigma_origin"),
        sigma_value=post_fields.get("sigma_value"),
        sigma_estimated_from_data=post_fields.get("sigma_estimated_from_data"),
        register_shape_identified=prediction.get("register_shape_identified"),
        shape_source=str(prediction.get("shape_source") or "constant_effect"),
        target_technique_observations=prediction.get("target_technique_observations"),
        g_t_active=prediction.get("g_t_active"),
        probability_above_ordinary=None,
        assumption_probability_above_ordinary=(
            post_fields.get("probability_above_ordinary") if prior_dom else None
        ),
        assumption_ids=list(prediction.get("assumption_ids") or []),
        assumptions_trace=[
            a
            for a in (prediction.get("assumptions_used") or [])
            if not str(a).startswith("ASSUMP_")
        ]
        + list(prediction.get("assumptions_trace") or []),
        assumptions_used=[
            a for a in (prediction.get("assumptions_used") or []) if str(a).startswith("ASSUMP_")
        ]
        or list(prediction.get("assumption_ids") or []),
    )
    if decision is not None:
        result = _attach_selection_fields(result, decision)
        # Prefer selection value_kind hint when assumption-based
        if decision.value_kind_hint == "assumption_based_extrapolation" and result.value_kind == ValueKind.EXTRAPOLATED:
            result.value_kind = ValueKind.ASSUMPTION_BASED_EXTRAPOLATION
    return result


def predict_register(
    measured_ordinary_rows: list[dict[str, Any]],
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    pitches: list[str] | None = None,
    target_quantity: str = "EWSD_score_acoustic_balanced",
    method: MethodName = "hierarchical_spline",
    technique_observations: list[dict[str, Any]] | None = None,
    harmonic_sounding_min: str | None = None,
    harmonic_sounding_max: str | None = None,
    include_low_harmonics: bool = True,
    harmonic_targets: list[dict[str, Any]] | None = None,
    harmonic_selection_mode: str | None = None,
) -> list[ExtrapolationResult]:
    """Predict technique values across a register (one result per pitch).

    Harmonic techniques use modal sounding targets (not a copy of the ordinary
    chromatic register) unless ``harmonic_targets`` / ``pitches`` are supplied.
    """
    tech = str(technique).strip().lower()
    inst = str(instrument).strip().lower()
    dyn = str(dynamic).strip().lower()

    if not mapping_allows_numeric_extrapolation(target_quantity) and method != "evidence_only":
        status = ewsd_mapping_status(target_quantity)
        return [
            ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=p or "unknown",
                midi=(rn[1] if (rn := resolve_note(str(p))) else None),
                target_quantity=target_quantity,
                model_id="mapping_guard",
                evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.UNAVAILABLE,
                warnings=[f"Quantity mapping status: {status}"],
                na_reason=status,
                assumptions_used=[f"mapping_status={status}"],
            )
            for p in (pitches or ["unknown"])
        ]

    _ewsd_assumptions = ewsd_model_assumptions(target_quantity)

    all_rows = list(measured_ordinary_rows) + list(technique_observations or [])
    df = _rows_to_frame(all_rows)
    ordinary_df = filter_ordinary(df)
    tech_df = df[df["technique"].astype(str).str.lower() == tech] if not df.empty else df

    is_harmonic = tech in _HARMONIC_TECHNIQUES
    harm_cfg = load_harmonic_range_config() if is_harmonic else {}
    harm_defaults = (harm_cfg.get("defaults") or {}) if harm_cfg else {}
    limited_st = float(harm_defaults.get("limited_extrapolation_semitones", 3))
    physical_st = float(harm_defaults.get("physical_or_assumption_semitones", 12))

    # Harmonics: generate modal sounding targets; do not copy ordinary register.
    target_rows: list[dict[str, Any]]
    if is_harmonic:
        if harmonic_targets is not None:
            target_rows = list(harmonic_targets)
        elif pitches is not None:
            # Explicit pitch list treated as sounding pitches (tempered), still NA without metadata
            target_rows = [
                {
                    "note": str(p),
                    "sounding_pitch": str(p),
                    "midi": (rn[1] if (rn := resolve_note(str(p))) else None),
                    "pitch_generation_method": "user_supplied_sounding_pitch_list",
                    "baseline_semantics": "unresolved",
                }
                for p in pitches
            ]
        else:
            target_rows = generate_harmonic_targets(
                inst,
                tech,
                dynamic=dyn,
                sounding_min=harmonic_sounding_min,
                sounding_max=harmonic_sounding_max,
                include_low_harmonics=include_low_harmonics,
                quantity=target_quantity,
                config=harm_cfg,
                selection_mode=harmonic_selection_mode,  # type: ignore[arg-type]
            )
    else:
        if pitches is None:
            if not ordinary_df.empty:
                pitches = sorted(ordinary_df["note"].astype(str).unique().tolist())
            else:
                pitches = ["A4"]
        target_rows = [{"note": str(p)} for p in pitches]

    if method == "evidence_only":
        return [
            ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=str(t.get("note") or t.get("sounding_pitch") or "unknown"),
                midi=t.get("midi") if t.get("midi") is not None else (
                    rn[1] if (rn := resolve_note(str(t.get("note") or ""))) else None
                ),
                target_quantity=target_quantity,
                model_id="evidence_only",
                evidence_tier=EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE,
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.QUALITATIVE_ONLY,
                warnings=["Numeric values withheld in evidence_only mode."],
                assumptions_used=[],
                assumptions_trace=["evidence_only_mode"],
            )
            for t in target_rows
        ]

    baseline = fit_ordinary_baseline(ordinary_df)
    baseline_fit = baseline.get(inst, dyn)
    data_status = infer_data_status(list(measured_ordinary_rows))
    provenance = _provenance_from_rows(list(measured_ordinary_rows))
    if data_status in {"synthetic", "synthetic_integration_test"} and not provenance.get("scientific_use"):
        provenance["scientific_use"] = "prohibited_for_doctoral_evidence"

    # Selection AFTER modal enrichment for harmonics:
    # initial request → generate modal targets → assess enriched covariates → select
    data_avail = assess_data_availability(
        technique=tech,
        instrument=inst,
        dynamic=dyn,
        target_quantity=target_quantity,
        technique_observations=tech_df if not tech_df.empty else None,
        request_enrichment=target_rows if is_harmonic else None,
    )
    decision = select_model(data_avail)

    results: list[ExtrapolationResult] = []
    for target in target_rows:
        note = str(target.get("sounding_pitch") or target.get("note") or "unknown")
        resolved = resolve_note(note)
        if resolved:
            note, midi = resolved[0], resolved[1]
        else:
            midi = target.get("midi") if target.get("midi") is not None else target.get("sounding_midi")
            if midi is not None:
                midi = int(midi)

        if decision.model_family in {
            "multiphonic_component_model",
            "execution_target_model",
        }:
            na = ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=note,
                midi=midi,
                target_quantity=target_quantity,
                model_id=decision.selected_model_id,
                evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.QUALITATIVE_ONLY,
                warnings=[f"selection_reason={decision.selection_reason}"],
                assumptions_used=list(decision.assumption_ids),
                na_reason=decision.selection_reason,
                data_status=data_status,
                shape_source="not_applicable",
                register_shape_identified=None,
                g_t_active=None,
                prior_dominated=None,
                model_status="unavailable_before_shape_estimation",
                interval_type="not_applicable",
                source_workbook_path=provenance.get("source_workbook_path"),
                source_workbook_hash=provenance.get("source_workbook_hash"),
                source_sheet=provenance.get("source_sheet"),
                import_run_id=provenance.get("import_run_id"),
                scientific_use=provenance.get("scientific_use"),
                source_row_ids=list(provenance.get("source_row_ids") or []),
            )
            results.append(_attach_selection_fields(na, decision))
            continue

        if is_harmonic or decision.model_family == "harmonic_modal_model":
            annotated = annotate_baseline_extrapolation(
                target,
                baseline_midi_min=baseline_fit.midi_min if baseline_fit else None,
                baseline_midi_max=baseline_fit.midi_max if baseline_fit else None,
                limited_semitones=limited_st,
                physical_semitones=physical_st,
            )
            stub = predict_harmonic_register(
                technique=tech,
                instrument=inst,
                dynamic=dyn,
                pitch=note,
                midi=midi,
                baseline_semantics=str(annotated.get("baseline_semantics") or "unresolved"),
                target_quantity=target_quantity,
            )
            na_reason = decision.selection_reason or stub.get("na_reason")
            if annotated.get("target_status") in {
                "excluded_by_analysis_range",
                "excluded_by_analysis_scope",
            }:
                na_reason = "excluded_by_analysis_scope"
            elif decision.selected_model_id == "harmonic_modal_acoustic_model_unavailable":
                na_reason = "no_harmonic_acoustic_calibration_data"
            elif decision.selected_model_id == "harmonic_modal_metadata_gate":
                na_reason = "insufficient_harmonic_metadata"

            if decision.selected_model_id == "harmonic_modal_acoustic_model_unavailable":
                model_status = "modal_frequencies_generated_acoustic_values_unavailable"
            elif decision.selected_model_id == "harmonic_modal_metadata_gate":
                model_status = "unavailable_before_modal_estimation"
            else:
                model_status = "modal_frequencies_generated_acoustic_values_unavailable"

            na = ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=note,
                midi=midi,
                target_quantity=target_quantity,
                model_id=decision.selected_model_id,
                submodel_id=stub.get("submodel_id"),
                evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.UNAVAILABLE
                if decision.value_kind_hint == "unavailable"
                else ValueKind.QUALITATIVE_ONLY,
                warnings=list(stub.get("warnings") or [])
                + [
                    f"selection_reason={decision.selection_reason}",
                    f"pitch_generation_method={annotated.get('pitch_generation_method')}",
                    f"baseline_support_policy={annotated.get('baseline_support_policy')}",
                    "modal_frequencies_known_but_descriptor_amplitudes_unavailable",
                ],
                assumption_ids=list(decision.assumption_ids or stub.get("assumption_ids") or []),
                assumptions_used=list(decision.assumption_ids or stub.get("assumption_ids") or []),
                assumptions_trace=list(stub.get("assumptions_trace") or [])
                + ["harmonic_descriptor_model_not_implemented"],
                na_reason=str(na_reason),
                convergence_status=ConvergenceStatus.NOT_APPLICABLE,
                diagnostics_status=ConvergenceStatus.NOT_APPLICABLE,
                data_status=data_status,
                shape_source="not_applicable",
                register_shape_identified=None,
                g_t_active=None,
                prior_dominated=None,
                target_technique_observations=decision.target_technique_observations,
                model_status=model_status,
                interval_type="not_applicable",
                sigma_estimated_from_data=None,
                string_name=annotated.get("string"),
                harmonic_type=annotated.get("harmonic_type") or tech,
                harmonic_order=annotated.get("harmonic_order"),
                production_pitch=annotated.get("production_pitch"),
                stopped_pitch=annotated.get("stopped_pitch"),
                touched_pitch=annotated.get("touched_pitch"),
                open_string_pitch=annotated.get("open_string_pitch"),
                sounding_pitch=annotated.get("sounding_pitch") or note,
                sounding_midi=annotated.get("sounding_midi") or midi,
                sounding_midi_float=annotated.get("sounding_midi_float"),
                sounding_frequency_hz=annotated.get("sounding_frequency_hz"),
                nearest_tempered_pitch=annotated.get("nearest_tempered_pitch"),
                cents_deviation=annotated.get("cents_deviation"),
                target_range_min=annotated.get("target_range_min"),
                target_range_max=annotated.get("target_range_max"),
                within_harmonic_analysis_range=annotated.get("within_harmonic_analysis_range"),
                within_ordinary_baseline_range=annotated.get("within_ordinary_baseline_range"),
                outside_ordinary_baseline_range=annotated.get("outside_ordinary_baseline_range"),
                baseline_extrapolation_semitones=annotated.get("baseline_extrapolation_semitones"),
                feasibility_status=annotated.get("feasibility_status"),
                pitch_generation_method=annotated.get("pitch_generation_method"),
                target_status=annotated.get("target_status"),
                baseline_support_policy=annotated.get("baseline_support_policy"),
                physical_range_min=annotated.get("physical_range_min"),
                physical_range_max=annotated.get("physical_range_max"),
                analysis_range_min=annotated.get("analysis_range_min"),
                analysis_range_max=annotated.get("analysis_range_max"),
                included_by_physical_model=annotated.get("included_by_physical_model"),
                included_by_analysis_filter=annotated.get("included_by_analysis_filter"),
                excluded_reason=annotated.get("excluded_reason"),
                selection_mode=annotated.get("selection_mode"),
                configuration_policy=annotated.get("configuration_policy"),
                configured_order_min=annotated.get("configured_order_min"),
                configured_order_max=annotated.get("configured_order_max"),
                order_selection_reason=annotated.get("order_selection_reason"),
                source_workbook_path=provenance.get("source_workbook_path"),
                source_workbook_hash=provenance.get("source_workbook_hash"),
                source_sheet=provenance.get("source_sheet"),
                import_run_id=provenance.get("import_run_id"),
                scientific_use=provenance.get("scientific_use"),
                source_row_ids=list(provenance.get("source_row_ids") or []),
            )
            attached = _attach_selection_fields(na, decision)
            attached.model_status = model_status
            results.append(attached)
            continue

        if method == "constant":
            if baseline_fit is None or midi is None:
                results.append(
                    ExtrapolationResult(
                        record_id=_new_record_id(),
                        instrument=inst,
                        technique=tech,
                        dynamic=dyn,
                        pitch=note,
                        midi=midi,
                        target_quantity=target_quantity,
                        model_id="M0_constant_legacy",
                        evidence_tier=EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE,
                        measured_or_extrapolated="unavailable",
                        value_kind=ValueKind.UNAVAILABLE,
                        warnings=["Missing ordinary baseline for constant legacy method."],
                        na_reason="missing_baseline",
                    )
                )
                continue
            b_mean, outside = baseline_fit.predict(midi)
            est = estimate_technique_density(
                baseline=float(b_mean),
                technique=tech,
                instrument=inst,
            )
            if est is None:
                results.append(
                    ExtrapolationResult(
                        record_id=_new_record_id(),
                        instrument=inst,
                        technique=tech,
                        dynamic=dyn,
                        pitch=note,
                        midi=midi,
                        target_quantity=target_quantity,
                        baseline_value=float(b_mean),
                        model_id="M0_constant_legacy",
                        evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                        measured_or_extrapolated="unavailable",
                        value_kind=ValueKind.UNAVAILABLE,
                        warnings=["No provisional density effect configured."],
                        na_reason="m0_unconfigured",
                    )
                )
                continue
            posterior = summarize_frequentist(float(est["value"]), None, baseline_mean=float(b_mean))
            post_fields = apply_posterior_to_result(posterior)
            results.append(
                ExtrapolationResult(
                    record_id=_new_record_id(),
                    instrument=inst,
                    technique=tech,
                    dynamic=dyn,
                    pitch=note,
                    midi=midi,
                    target_quantity=target_quantity,
                    baseline_value=float(b_mean),
                    baseline_record_ids=baseline_fit.record_ids,
                    model_id="M0_constant_legacy",
                    evidence_tier=EvidenceTier.LEVEL_2_METADATA_CONSTRAINED,
                    measured_or_extrapolated="extrapolated",
                    value_kind=ValueKind.EXTRAPOLATED,
                    warnings=list(est.get("warnings") or []),
                    assumptions_used=list(est.get("assumptions") or []),
                    calculation_trace=trace_constant_legacy(technique=tech, method=str(est.get("method"))),
                    prior_dominated=True,
                    sensitivity_status=(
                        SensitivityStatus.OUTSIDE_BASELINE_RANGE if bool(np.any(outside)) else SensitivityStatus.PRIOR_SENSITIVE
                    ),
                    credible_interval_low=est.get("lower_bound") or post_fields.get("credible_interval_low"),
                    credible_interval_high=est.get("upper_bound") or post_fields.get("credible_interval_high"),
                    posterior_mean=post_fields.get("posterior_mean"),
                    posterior_median=post_fields.get("posterior_median"),
                    posterior_sd=post_fields.get("posterior_sd"),
                    probability_above_ordinary=post_fields.get("probability_above_ordinary"),
                )
            )
            continue

        if method == "physical_informed_bayesian":
            backend = check_backend()
            if not backend.available or baseline_fit is None or midi is None:
                results.append(
                    ExtrapolationResult(
                        record_id=_new_record_id(),
                        instrument=inst,
                        technique=tech,
                        dynamic=dyn,
                        pitch=note,
                        midi=midi,
                        target_quantity=target_quantity,
                        model_id="M1_bayesian",
                        evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                        measured_or_extrapolated="unavailable",
                        value_kind=ValueKind.UNAVAILABLE,
                        warnings=[backend.status],
                        na_reason="bayesian_backend_unavailable",
                        convergence_status=ConvergenceStatus.BACKEND_UNAVAILABLE,
                        diagnostics_status=ConvergenceStatus.BACKEND_UNAVAILABLE,
                    )
                )
                continue
            if tech_df.empty or len(tech_df) < 3:
                results.append(
                    ExtrapolationResult(
                        record_id=_new_record_id(),
                        instrument=inst,
                        technique=tech,
                        dynamic=dyn,
                        pitch=note,
                        midi=midi,
                        target_quantity=target_quantity,
                        model_id="M1_bayesian",
                        evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                        measured_or_extrapolated="unavailable",
                        value_kind=ValueKind.UNAVAILABLE,
                        warnings=["Insufficient technique observations for Bayesian fit."],
                        na_reason="insufficient_technique_observations",
                    )
                )
                continue
            ratios = []
            xs = []
            for _, row in tech_df.dropna(subset=["midi", "value"]).iterrows():
                b, _ = baseline_fit.predict(float(row["midi"]))
                ratios.append(math.log(float(row["value"]) / b))
                xs.append(float(row["midi"]))
            fit_out = fit_bayesian_log_ratio_spline(np.asarray(xs), np.asarray(ratios))
            if not fit_out.get("available"):
                results.append(
                    ExtrapolationResult(
                        record_id=_new_record_id(),
                        instrument=inst,
                        technique=tech,
                        dynamic=dyn,
                        pitch=note,
                        midi=midi,
                        target_quantity=target_quantity,
                        model_id="M1_bayesian",
                        evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                        measured_or_extrapolated="unavailable",
                        value_kind=ValueKind.UNAVAILABLE,
                        warnings=[str(fit_out.get("status"))],
                        na_reason="bayesian_fit_failed",
                        convergence_status=ConvergenceStatus.BACKEND_UNAVAILABLE,
                    )
                )
                continue
            # Fall back to hierarchical point prediction for register value
            method = "hierarchical_spline"

        # Default path: log-ratio over smoothed baseline (constant α when g unidentified)
        if baseline_fit is None or midi is None:
            results.append(
                ExtrapolationResult(
                    record_id=_new_record_id(),
                    instrument=inst,
                    technique=tech,
                    dynamic=dyn,
                    pitch=note,
                    midi=midi,
                    target_quantity=target_quantity,
                    model_id="constant_technique_effect_over_smoothed_baseline",
                    evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                    measured_or_extrapolated="unavailable",
                    value_kind=ValueKind.UNAVAILABLE,
                    warnings=["Missing baseline or unresolved pitch."],
                    na_reason="missing_baseline_or_pitch",
                    data_status=data_status,
                    register_shape_identified=False,
                    shape_source="constant_effect",
                    target_technique_observations=0,
                    g_t_active=False,
                )
            )
            continue

        submodel = fit_technique_effect(
            baseline,
            tech_df,
            technique=tech,
            instrument=inst,
            dynamic=dyn,
            selected_model_id=decision.selected_model_id,
            marks=decision.marks,
        )
        if isinstance(submodel, dict) and submodel.get("refused"):
            refused = ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=note,
                midi=midi,
                target_quantity=target_quantity,
                model_id=decision.selected_model_id,
                evidence_tier=submodel.get("evidence_tier", EvidenceTier.LEVEL_0_UNSUPPORTED),
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.UNAVAILABLE,
                warnings=[str(submodel.get("reason")), f"selection_reason={decision.selection_reason}"],
                na_reason=str(submodel.get("reason")),
                data_status=data_status,
            )
            results.append(_attach_selection_fields(refused, decision))
            continue
        if submodel is None or isinstance(submodel, dict):
            unsup = ExtrapolationResult(
                record_id=_new_record_id(),
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                pitch=note,
                midi=midi,
                target_quantity=target_quantity,
                model_id=decision.selected_model_id,
                evidence_tier=EvidenceTier.LEVEL_0_UNSUPPORTED,
                measured_or_extrapolated="unavailable",
                value_kind=ValueKind.UNAVAILABLE,
                warnings=["Unsupported technique for selected model family."],
                na_reason="unsupported_technique",
                data_status=data_status,
            )
            results.append(_attach_selection_fields(unsup, decision))
            continue

        pred = submodel.predict(baseline_fit, midi)
        trace = list(pred.get("calculation_trace") or [])
        if pred.get("mean") is not None:
            trace = trace_baseline_prediction(
                instrument=inst,
                dynamic=dyn,
                midi=float(midi),
                n_obs=baseline_fit.n_observations,
            ) + trace
        pred["calculation_trace"] = trace
        pred["data_status"] = data_status
        results.append(
            _result_from_prediction(
                pitch=note,
                midi=midi,
                instrument=inst,
                technique=tech,
                dynamic=dyn,
                target_quantity=target_quantity,
                prediction=pred,
                model_id=decision.selected_model_id,
                submodel_id=getattr(submodel, "submodel_id", None),
                baseline_fit=baseline,
                data_status=data_status,
                decision=decision,
            )
        )

    if _ewsd_assumptions:
        for r in results:
            for a in _ewsd_assumptions:
                if str(a).startswith("ASSUMP_"):
                    if a not in (r.assumption_ids or []):
                        r.assumption_ids = list(r.assumption_ids or []) + [a]
                else:
                    if a not in (r.assumptions_trace or []):
                        r.assumptions_trace = list(r.assumptions_trace or []) + [a]
            r.assumptions_used = list(r.assumption_ids or [])
            r.warnings = list(r.warnings or []) + [
                f"quantity_mapping_status={ewsd_mapping_status(target_quantity)}"
            ]
    # Stamp provenance on non-harmonic numeric rows
    for r in results:
        if r.source_workbook_path is None and provenance.get("source_workbook_path"):
            r.source_workbook_path = provenance.get("source_workbook_path")
        if r.source_workbook_hash is None and provenance.get("source_workbook_hash"):
            r.source_workbook_hash = provenance.get("source_workbook_hash")
        if r.source_sheet is None and provenance.get("source_sheet"):
            r.source_sheet = provenance.get("source_sheet")
        if r.import_run_id is None and provenance.get("import_run_id"):
            r.import_run_id = provenance.get("import_run_id")
        if r.scientific_use is None and provenance.get("scientific_use"):
            r.scientific_use = provenance.get("scientific_use")
        if not r.source_row_ids and provenance.get("source_row_ids"):
            r.source_row_ids = list(provenance["source_row_ids"])
        if r.data_status in {"synthetic", "synthetic_integration_test"} and not r.scientific_use:
            r.scientific_use = "prohibited_for_doctoral_evidence"
    return results


def predict_technique_register(
    measured_ordinary_rows: list[dict[str, Any]],
    technique: str,
    instrument: str,
    dynamic: str,
    **kwargs: Any,
) -> list[ExtrapolationResult]:
    """Backward-compatible alias."""
    return predict_register(
        measured_ordinary_rows,
        technique=technique,
        instrument=instrument,
        dynamic=dynamic,
        **kwargs,
    )
