"""Explicit model selection engine.

selection = f(physical mechanism, target quantity, available data, evidence tier)

Stage 1: scientifically admissible candidates
Stage 2: choose the simplest admissible model that the data identify
         (never auto-pick the most complex)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

DEFAULT_SELECTION_CONFIG = PACKAGE_ROOT / "configs" / "extrapolation_model_selection.yaml"

PHYSICAL_COVARIATES = ("beta", "bow_force", "bow_velocity", "speaking_length")

# Family-specific audit covariates (not inherited from bow contact by default).
MUTE_COVARIATES = (
    "ordinary_spectrum_or_ltas",
    "muted_spectrum_or_ltas",
    "mute_category",
    "mute_material",
    "mute_mass_g",
    "instrument",
    "measurement_domain",
)
HARMONIC_COVARIATES = (
    "harmonic_type",
    "string",
    "harmonic_order",
    "stopped_pitch",
    "touched_pitch",
    "sounding_pitch",
    "baseline_semantics",
)

TECHNIQUE_TO_FAMILY = {
    "ordinary": "ordinary_baseline_model",
    "ordinario": "ordinary_baseline_model",
    "arco": "ordinary_baseline_model",
    "arco_normal": "ordinary_baseline_model",
    "sul_tasto": "bow_contact_model",
    "sul_ponticello": "bow_contact_model",
    "con_sordino": "mute_transfer_model",
    "natural_harmonic": "harmonic_modal_model",
    "artificial_harmonic": "harmonic_modal_model",
    "multiphonics": "multiphonic_component_model",
    "multiphonic": "multiphonic_component_model",
    "flautando": "execution_target_model",
}

FallbackLevel = Literal[
    "spectral_or_modal",
    "physical_informed",
    "hierarchical",
    "penalized_spline",
    "regularized_linear",
    "constant_assumption",
    "qualitative_or_na",
    "no_numeric_fallback",
]


@dataclass
class DataAvailability:
    """Observable state used by the selection engine."""

    technique: str
    instrument: str
    dynamic: str
    target_quantity: str
    n_target_observations: int = 0
    distinct_pitch_count: int = 0
    pitch_span_semitones: float = 0.0
    has_spectra_or_ltas: bool = False
    has_beta: bool = False
    has_bow_force: bool = False
    has_bow_velocity: bool = False
    has_harmonic_order: bool = False
    has_string: bool = False
    has_stopped_pitch: bool = False
    has_touched_pitch: bool = False
    has_sounding_pitch: bool = False
    baseline_semantics_resolved: bool = False
    has_calibrated_descriptor_model: bool = False
    n_instruments_in_pool: int = 1
    n_dynamics_in_pool: int = 1
    spline_design_is_identifiable: bool = False
    authorize_numeric_assumption: bool = True
    present_covariates: list[str] = field(default_factory=list)
    missing_covariates: list[str] = field(default_factory=list)
    missing_model_components: list[str] = field(default_factory=list)

    @property
    def harmonic_metadata_complete(self) -> bool:
        return bool(
            self.has_harmonic_order
            and self.has_string
            and self.baseline_semantics_resolved
            and (self.has_stopped_pitch or self.has_sounding_pitch)
        )


@dataclass
class ModelSelectionDecision:
    model_family: str
    selected_model_id: str
    candidate_model_ids: list[str]
    rejected_model_ids: list[str]
    rejection_reasons: dict[str, str]
    selection_reason: str
    fallback_level: FallbackLevel
    complexity_level: str
    model_selection_status: str
    target_technique_observations: int
    distinct_pitch_count: int
    pitch_span_semitones: float
    required_covariates: list[str]
    available_covariates: list[str]
    missing_covariates: list[str]
    register_shape_identified: bool | None
    model_comparison_available: bool
    evidence_tier_hint: str
    assumption_ids: list[str]
    value_kind_hint: str
    marks: list[str] = field(default_factory=list)
    admissible_model_ids: list[str] = field(default_factory=list)
    mechanism: str = ""
    target_quantity: str = ""
    missing_model_components: list[str] = field(default_factory=list)
    modal_metadata_status: str | None = None
    acoustic_calibration_status: str | None = None

    def rejection_reason_list(self) -> list[str]:
        return [f"{mid}:{why}" for mid, why in sorted(self.rejection_reasons.items())]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_family": self.model_family,
            "selected_model_id": self.selected_model_id,
            "candidate_model_ids": list(self.candidate_model_ids),
            "rejected_model_ids": list(self.rejected_model_ids),
            "rejection_reasons": dict(self.rejection_reasons),
            "selection_reason": self.selection_reason,
            "fallback_level": self.fallback_level,
            "complexity_level": self.complexity_level,
            "model_selection_status": self.model_selection_status,
            "target_technique_observations": self.target_technique_observations,
            "distinct_pitch_count": self.distinct_pitch_count,
            "pitch_span_semitones": self.pitch_span_semitones,
            "required_covariates": list(self.required_covariates),
            "available_covariates": list(self.available_covariates),
            "missing_covariates": list(self.missing_covariates),
            "missing_model_components": list(self.missing_model_components),
            "modal_metadata_status": self.modal_metadata_status,
            "acoustic_calibration_status": self.acoustic_calibration_status,
            "register_shape_identified": self.register_shape_identified,
            "model_comparison_available": self.model_comparison_available,
            "evidence_tier_hint": self.evidence_tier_hint,
            "assumption_ids": list(self.assumption_ids),
            "value_kind_hint": self.value_kind_hint,
            "marks": list(self.marks),
            "admissible_model_ids": list(self.admissible_model_ids),
            "mechanism": self.mechanism,
            "target_quantity": self.target_quantity,
        }


def load_selection_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(resolve_path(path or DEFAULT_SELECTION_CONFIG))


def family_for_technique(technique: str) -> str:
    tech = str(technique).strip().lower()
    return TECHNIQUE_TO_FAMILY.get(tech, "unsupported_technique_family")


def assess_data_availability(
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    target_quantity: str,
    technique_observations: pd.DataFrame | None,
    authorize_numeric_assumption: bool | None = None,
    config: dict[str, Any] | None = None,
    request_enrichment: pd.DataFrame | list[dict[str, Any]] | None = None,
) -> DataAvailability:
    """Summarize observations and physical covariates for selection.

    ``request_enrichment`` carries modal geometry filled *after* harmonic
    target generation (not measured technique observations).
    """
    cfg = config or load_selection_config()
    policy = cfg.get("policy") or {}
    thr = cfg.get("thresholds") or {}
    if authorize_numeric_assumption is None:
        authorize_numeric_assumption = bool(policy.get("authorize_numeric_assumption_when_zero_obs", True))

    tech = str(technique).strip().lower()
    inst = str(instrument).strip().lower()
    dyn = str(dynamic).strip().lower()

    obs = technique_observations
    if obs is not None and not obs.empty:
        mask = obs["technique"].astype(str).str.lower() == tech
        if "instrument" in obs.columns:
            mask = mask & (obs["instrument"].astype(str).str.lower() == inst)
        if "dynamic" in obs.columns:
            mask = mask & (obs["dynamic"].astype(str).str.lower() == dyn)
        obs = obs.loc[mask].copy()
    else:
        obs = pd.DataFrame()

    if isinstance(request_enrichment, list):
        enrich = pd.DataFrame(request_enrichment) if request_enrichment else pd.DataFrame()
    elif request_enrichment is not None and not getattr(request_enrichment, "empty", True):
        enrich = pd.DataFrame(request_enrichment)
    else:
        enrich = pd.DataFrame()

    n_obs = int(len(obs))
    midis: list[float] = []
    if n_obs and "midi" in obs.columns:
        midis = [float(x) for x in obs["midi"].dropna().tolist()]
    distinct = len(set(round(m, 3) for m in midis))
    span = float(max(midis) - min(midis)) if len(midis) >= 2 else 0.0

    present: list[str] = []
    for cov in PHYSICAL_COVARIATES:
        if n_obs and cov in obs.columns and obs[cov].notna().any():
            present.append(cov)

    has_spectra = False
    if n_obs:
        for col in ("has_ltas", "has_spectrum", "ltas_path", "spectrum_path", "measurement_domain"):
            if col in obs.columns:
                vals = obs[col].astype(str).str.lower()
                if vals.isin({"true", "1", "ltas", "spectrum", "spectral"}).any() or obs[col].notna().any():
                    if col == "measurement_domain":
                        has_spectra = any("ltas" in v or "spectrum" in v for v in vals)
                    else:
                        has_spectra = True

    family = family_for_technique(tech)
    fam_cfg = (cfg.get("families") or {}).get(family) or {}
    has_calibrated = False
    missing_model_components: list[str] = []

    def _col_present(frame: pd.DataFrame, col: str) -> bool:
        return bool(not frame.empty and col in frame.columns and frame[col].notna().any())

    # Family-specific covariate audit (do not inherit bow covariates onto mute/harmonics).
    if family == "bow_contact_model":
        required_audit = list(
            fam_cfg.get("required_physical_covariates_for_M4")
            or fam_cfg.get("required_covariates")
            or ["beta", "bow_force", "bow_velocity"]
        )
        for cov in required_audit:
            if cov in present:
                continue
            if cov in {"instrument", "dynamic", "pitch"} and (inst and dyn):
                present.append(cov)
        missing = [c for c in required_audit if c not in present]
    elif family == "mute_transfer_model":
        required_audit = list(fam_cfg.get("required_covariates") or MUTE_COVARIATES)
        if inst:
            present.append("instrument")
        if has_spectra:
            present.extend(["ordinary_spectrum_or_ltas", "measurement_domain"])
        for cov in ("mute_category", "mute_material", "mute_mass_g", "muted_spectrum_or_ltas"):
            if n_obs and cov in obs.columns and obs[cov].notna().any():
                present.append(cov)
        missing = [c for c in required_audit if c not in present]
    elif family == "harmonic_modal_model":
        required_audit = list(fam_cfg.get("required_covariates") or HARMONIC_COVARIATES)
        # Prefer enriched modal requests; fall back to measured technique rows
        cov_src = enrich if not enrich.empty else obs
        for cov in HARMONIC_COVARIATES:
            if _col_present(cov_src, cov) and cov not in present:
                present.append(cov)
        if _col_present(cov_src, "technique") or tech.endswith("harmonic"):
            if "harmonic_type" not in present:
                present.append("harmonic_type")
        if _col_present(cov_src, "stopped_pitch") and "stopped_pitch" not in present:
            present.append("stopped_pitch")
        if _col_present(cov_src, "touched_pitch") and "touched_pitch" not in present:
            present.append("touched_pitch")
        if _col_present(cov_src, "open_string_pitch") and "open_string_pitch" not in present:
            present.append("open_string_pitch")
        # Modal geometry = covariates; acoustic calibration = model component
        modal_missing = [c for c in required_audit if c not in present]
        model_comp_req = list(
            fam_cfg.get("required_model_components_for_numeric")
            or fam_cfg.get("required_for_numeric_prediction")
            or []
        )
        from string_technique_model.extrapolation.nonlinear.harmonic_calibration_table import (
            has_calibrated_harmonic_coverage,
        )

        has_calibrated = bool(
            _col_present(obs, "calibrated_harmonic_descriptor_model")
            or _col_present(enrich, "calibrated_harmonic_descriptor_model")
            or has_calibrated_harmonic_coverage(inst, tech)
        )
        missing = modal_missing  # never put model components into missing_covariates
        missing_model_components = [
            c for c in model_comp_req if not (c == "calibrated_harmonic_descriptor_model" and has_calibrated)
        ]
    else:
        required_audit = list(fam_cfg.get("required_covariates") or [])
        missing = [c for c in required_audit if c not in present]
        missing_model_components = []

    # Spline design identifiability heuristic
    min_pitches_spline = int(thr.get("min_distinct_pitches_for_spline", 6))
    n_basis_guess = max(4, min(8, distinct))
    rank_ratio = (distinct / n_basis_guess) if n_basis_guess else 0.0
    identifiable = (
        distinct >= min_pitches_spline
        and span >= float(thr.get("min_pitch_span_semitones_for_spline", 12))
        and rank_ratio >= float(thr.get("min_design_rank_ratio", 0.85))
    )

    cov_src_h = enrich if (family == "harmonic_modal_model" and not enrich.empty) else obs
    has_h_order = _col_present(cov_src_h, "harmonic_order")
    has_string = _col_present(cov_src_h, "string")
    has_stopped = _col_present(cov_src_h, "stopped_pitch")
    has_touched = _col_present(cov_src_h, "touched_pitch")
    has_sounding = _col_present(cov_src_h, "sounding_pitch")
    semantics = False
    if _col_present(cov_src_h, "baseline_semantics"):
        semantics = any(
            str(x).lower() not in {"", "unresolved", "none", "nan"}
            for x in cov_src_h["baseline_semantics"].tolist()
        )
    return DataAvailability(
        technique=tech,
        instrument=inst,
        dynamic=dyn,
        target_quantity=str(target_quantity),
        n_target_observations=n_obs,
        distinct_pitch_count=distinct,
        pitch_span_semitones=span,
        has_spectra_or_ltas=has_spectra,
        has_beta="beta" in present,
        has_bow_force="bow_force" in present,
        has_bow_velocity="bow_velocity" in present,
        has_harmonic_order=has_h_order,
        has_string=has_string,
        has_stopped_pitch=has_stopped,
        has_touched_pitch=has_touched,
        has_sounding_pitch=has_sounding,
        baseline_semantics_resolved=semantics,
        has_calibrated_descriptor_model=has_calibrated,
        spline_design_is_identifiable=identifiable,
        authorize_numeric_assumption=bool(authorize_numeric_assumption),
        present_covariates=list(dict.fromkeys(present)),
        missing_covariates=list(dict.fromkeys(missing)),
        missing_model_components=list(dict.fromkeys(missing_model_components))
        if family == "harmonic_modal_model"
        else [],
    )


def _requires_ok(requires: dict[str, Any], data: DataAvailability) -> tuple[bool, str | None]:
    if not requires:
        return True, None
    checks = {
        "min_observations": data.n_target_observations >= int(requires.get("min_observations", 0)),
        "min_distinct_pitches": data.distinct_pitch_count >= int(requires.get("min_distinct_pitches", 0)),
        "min_pitch_span_semitones": data.pitch_span_semitones
        >= float(requires.get("min_pitch_span_semitones", 0)),
        "spline_design_identifiable": (
            data.spline_design_is_identifiable
            if "spline_design_identifiable" in requires
            else True
        ),
        "has_spectra_or_ltas": (
            data.has_spectra_or_ltas == bool(requires["has_spectra_or_ltas"])
            if "has_spectra_or_ltas" in requires
            else True
        ),
        "authorize_numeric_assumption": (
            data.authorize_numeric_assumption == bool(requires["authorize_numeric_assumption"])
            if "authorize_numeric_assumption" in requires
            else True
        ),
        "harmonic_metadata_complete": (
            data.harmonic_metadata_complete == bool(requires["harmonic_metadata_complete"])
            if "harmonic_metadata_complete" in requires
            else True
        ),
        "has_calibrated_descriptor_model": (
            data.has_calibrated_descriptor_model == bool(requires["has_calibrated_descriptor_model"])
            if "has_calibrated_descriptor_model" in requires
            else True
        ),
        "min_instruments": data.n_instruments_in_pool >= int(requires.get("min_instruments", 0)),
        "min_dynamics": data.n_dynamics_in_pool >= int(requires.get("min_dynamics", 0)),
    }
    # Only evaluate keys present in requires
    for key in requires:
        mapped = {
            "min_observations": "min_observations",
            "min_distinct_pitches": "min_distinct_pitches",
            "min_pitch_span_semitones": "min_pitch_span_semitones",
            "spline_design_identifiable": "spline_design_identifiable",
            "has_spectra_or_ltas": "has_spectra_or_ltas",
            "authorize_numeric_assumption": "authorize_numeric_assumption",
            "harmonic_metadata_complete": "harmonic_metadata_complete",
            "has_calibrated_descriptor_model": "has_calibrated_descriptor_model",
            "min_instruments": "min_instruments",
            "min_dynamics": "min_dynamics",
        }.get(key)
        if mapped is None:
            continue
        if not checks[mapped]:
            return False, f"failed_requirement:{key}"
    return True, None


def _complexity_to_fallback(complexity: str, *, explicit: str | None = None) -> FallbackLevel:
    if explicit:
        return explicit  # type: ignore[return-value]
    mapping: dict[str, FallbackLevel] = {
        "M5_spectral_or_modal_specific": "spectral_or_modal",
        "M4_physical_informed": "physical_informed",
        "M3_hierarchical_instrument_dynamic": "hierarchical",
        "M2_penalized_register_spline": "penalized_spline",
        "M1_regularized_linear_trend": "regularized_linear",
        "M0_constant_effect": "constant_assumption",
        "not_applicable": "no_numeric_fallback",
    }
    return mapping.get(complexity, "qualitative_or_na")


def _family_required_covariates(fam: dict[str, Any], family: str) -> list[str]:
    if family == "mute_transfer_model":
        return list(fam.get("required_covariates") or MUTE_COVARIATES)
    if family == "harmonic_modal_model":
        return list(fam.get("required_covariates") or HARMONIC_COVARIATES)
    if family == "bow_contact_model":
        return list(
            fam.get("required_physical_covariates_for_M4")
            or fam.get("required_covariates")
            or ["beta", "bow_force", "bow_velocity"]
        )
    return list(fam.get("required_covariates") or [])


def _register_shape_identified(model_id: str, complexity: str) -> bool:
    return complexity in {
        "M1_regularized_linear_trend",
        "M2_penalized_register_spline",
        "M3_hierarchical_instrument_dynamic",
        "M4_physical_informed",
        "M5_spectral_or_modal_specific",
    } and model_id not in {
        "constant_technique_effect_over_smoothed_baseline",
        "constant_assumption_fallback",
        "qualitative_or_na_mute",
        "harmonic_modal_metadata_gate",
        "harmonic_modal_acoustic_model_unavailable",
        "multiphonic_qualitative_only",
        "flautando_qualitative_or_na",
    }


def _harmonic_audit_fields(data: DataAvailability, family: str) -> dict[str, Any]:
    """Separate modal metadata completeness from acoustic calibration availability."""
    if family != "harmonic_modal_model":
        return {
            "missing_model_components": [],
            "modal_metadata_status": None,
            "acoustic_calibration_status": None,
        }
    return {
        "missing_model_components": list(data.missing_model_components),
        "modal_metadata_status": (
            "complete" if data.harmonic_metadata_complete else "incomplete"
        ),
        "acoustic_calibration_status": (
            "available" if data.has_calibrated_descriptor_model else "unavailable"
        ),
    }


def select_model(
    data: DataAvailability,
    *,
    config: dict[str, Any] | None = None,
) -> ModelSelectionDecision:
    """Two-stage selection: admissible set → simplest identifiable model."""
    cfg = config or load_selection_config()
    family = family_for_technique(data.technique)
    fam = (cfg.get("families") or {}).get(family)
    policy = cfg.get("policy") or {}

    if fam is None:
        return ModelSelectionDecision(
            model_family="unsupported_technique_family",
            selected_model_id="unsupported_technique",
            candidate_model_ids=[],
            rejected_model_ids=[],
            rejection_reasons={},
            selection_reason="technique_not_mapped_to_model_family",
            fallback_level="qualitative_or_na",
            complexity_level="M0_constant_effect",
            model_selection_status="failed_unsupported_technique",
            target_technique_observations=data.n_target_observations,
            distinct_pitch_count=data.distinct_pitch_count,
            pitch_span_semitones=data.pitch_span_semitones,
            required_covariates=[],
            available_covariates=list(data.present_covariates),
            missing_covariates=list(data.missing_covariates),
            register_shape_identified=None,
            model_comparison_available=False,
            evidence_tier_hint="LEVEL_0_UNSUPPORTED",
            assumption_ids=[],
            value_kind_hint="unavailable",
            mechanism="unknown",
            target_quantity=data.target_quantity,
            **_harmonic_audit_fields(data, family),
        )

    ladder: list[dict[str, Any]] = list(fam.get("ladder") or [])
    candidate_ids = [str(step["model_id"]) for step in ladder if step.get("enabled", True) is not False]
    admissible: list[dict[str, Any]] = []
    rejected: dict[str, str] = {}

    for step in ladder:
        mid = str(step["model_id"])
        if step.get("enabled", True) is False:
            rejected[mid] = "disabled_in_config"
            continue

        # Covariate gate for physical-informed
        req_cov = list(step.get("requires_covariates") or [])
        if req_cov:
            missing = [c for c in req_cov if c not in data.present_covariates]
            if missing and policy.get("refuse_physical_informed_without_covariates", True):
                rejected[mid] = f"missing_covariates:{','.join(missing)}"
                continue

        ok, why = _requires_ok(dict(step.get("requires") or {}), data)
        if not ok:
            # Metadata gate requires incomplete metadata; when complete it is
            # not applicable — not a failed requirement.
            if mid == "harmonic_modal_metadata_gate" and data.harmonic_metadata_complete:
                rejected[mid] = "gate_not_applicable_modal_metadata_complete"
            else:
                rejected[mid] = why or "requirements_not_met"
            continue

        # Mute: spectral preferred when available — keep admissible
        # Harmonics: refuse constant factor path always
        if family == "harmonic_modal_model" and mid.startswith("constant") and policy.get(
            "refuse_constant_factor_for_harmonics", True
        ):
            rejected[mid] = "constant_factor_refused_for_harmonics"
            continue

        admissible.append(step)

    # Special mute policy: if spectra exist, prefer spectral among admissible
    # Otherwise drop qualitative if numeric assumption authorized and constant_assumption admissible
    if family == "mute_transfer_model":
        if data.has_spectra_or_ltas:
            spectral = [s for s in admissible if s["model_id"] == "spectral_transfer_model"]
            if spectral:
                for s in list(admissible):
                    if s["model_id"] != "spectral_transfer_model":
                        rejected[str(s["model_id"])] = "dominated_by_spectral_transfer_when_ltas_present"
                        admissible.remove(s)
        elif data.authorize_numeric_assumption:
            for s in list(admissible):
                if s["model_id"] == "qualitative_or_na_mute":
                    rejected[str(s["model_id"])] = "numeric_assumption_authorized_prefer_constant_or_scalar"
                    admissible.remove(s)
        else:
            for s in list(admissible):
                if s["model_id"] != "qualitative_or_na_mute":
                    rejected[str(s["model_id"])] = "numeric_assumption_not_authorized"
                    admissible.remove(s)

    # Bow: with zero observations only constant (or qualitative if not authorized)
    if family == "bow_contact_model" and data.n_target_observations == 0:
        kept = []
        for s in admissible:
            if s["model_id"] == "constant_technique_effect_over_smoothed_baseline":
                if data.authorize_numeric_assumption:
                    kept.append(s)
                else:
                    rejected[str(s["model_id"])] = "numeric_assumption_not_authorized"
            else:
                rejected[str(s["model_id"])] = "no_target_technique_observations"
        admissible = kept

    if not admissible:
        # Ultimate fallback
        selected_id = "qualitative_or_na"
        reason = "no_admissible_numeric_model"
        complexity = "M0_constant_effect"
        fallback: FallbackLevel = "qualitative_or_na"
        value_kind = "qualitative_only" if family != "harmonic_modal_model" else "unavailable"
        marks: list[str] = []
        assumption_ids: list[str] = []
        if family == "harmonic_modal_model":
            if data.harmonic_metadata_complete:
                selected_id = "harmonic_modal_acoustic_model_unavailable"
                reason = "no_harmonic_acoustic_calibration_data"
                assumption_ids = ["ASSUMP_HARMONIC_DESCRIPTOR_MODEL_NOT_IMPLEMENTED"]
                marks = ["modal_frequencies_generated_acoustic_values_unavailable"]
            else:
                selected_id = "harmonic_modal_metadata_gate"
                reason = "insufficient_harmonic_metadata"
                assumption_ids = ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"]
            value_kind = "unavailable"
            complexity = "not_applicable"
            fallback = "no_numeric_fallback"
        return ModelSelectionDecision(
            model_family=family,
            selected_model_id=selected_id,
            candidate_model_ids=candidate_ids,
            rejected_model_ids=sorted(rejected),
            rejection_reasons=rejected,
            selection_reason=reason,
            fallback_level=fallback,
            complexity_level=complexity,
            model_selection_status="completed_unavailable_or_qualitative",
            target_technique_observations=data.n_target_observations,
            distinct_pitch_count=data.distinct_pitch_count,
            pitch_span_semitones=data.pitch_span_semitones,
            required_covariates=_family_required_covariates(fam, family),
            available_covariates=list(dict.fromkeys(data.present_covariates)),
            missing_covariates=list(data.missing_covariates),
            register_shape_identified=None,
            model_comparison_available=False,
            evidence_tier_hint="LEVEL_0_UNSUPPORTED",
            assumption_ids=assumption_ids,
            value_kind_hint=value_kind,
            marks=marks,
            admissible_model_ids=[],
            mechanism=str(fam.get("mechanism") or ""),
            target_quantity=data.target_quantity,
            **_harmonic_audit_fields(data, family),
        )

    # Stage 2: among admissible, pick highest complexity that is still justified —
    # but policy says never pick most complex by default: pick the *maximum admissible*
    # that data support, walking ladder ascending and taking the best supported.
    # "Best" = highest rung that is admissible (data-driven ceiling), not speculative M4/M5.
    # For mute with spectra, spectral is the only remaining admissible.
    # Order ladder by complexity index.
    ladder_order = list(cfg.get("complexity_ladder") or [])
    def c_index(step: dict[str, Any]) -> int:
        c = str(step.get("complexity") or "M0_constant_effect")
        try:
            return ladder_order.index(c)
        except ValueError:
            return 0

    admissible_sorted = sorted(admissible, key=c_index)
    # Choose the most complex *admissible* model (data ceiling), not beyond.
    chosen = admissible_sorted[-1]
    # Downgrade reason documentation for rejected higher rungs already in rejected

    # Explicit selection reasons
    mid = str(chosen["model_id"])
    complexity = str(chosen.get("complexity") or "M0_constant_effect")
    if data.n_target_observations == 0 and mid == "constant_technique_effect_over_smoothed_baseline":
        reason = str(chosen.get("selection_reason_if_chosen_with_zero_obs") or "no_target_technique_observations")
    elif mid == "constant_assumption_fallback":
        reason = (
            "no_frequency_domain_input_and_no_target_technique_measurements;"
            "numeric_assumption_authorized"
        )
    elif mid == "spectral_transfer_model":
        reason = "spectra_or_ltas_available"
    elif mid == "regularized_linear_register_trend" or mid.endswith("_linear"):
        reason = (
            f"partial_register_coverage:distinct_pitches={data.distinct_pitch_count}"
            f"<spline_min_or_design_not_identifiable"
        )
    elif "spline" in mid:
        reason = (
            f"register_coverage_supports_spline:distinct_pitches={data.distinct_pitch_count},"
            f"span={data.pitch_span_semitones:.1f}"
        )
    elif mid == "physical_informed_bow_contact":
        reason = "physical_covariates_present"
    elif mid == "harmonic_modal_metadata_gate":
        reason = str(chosen.get("selection_reason_if_chosen") or "insufficient_harmonic_metadata")
    elif mid == "harmonic_modal_acoustic_model_unavailable":
        reason = str(
            chosen.get("selection_reason_if_chosen") or "no_harmonic_acoustic_calibration_data"
        )
    elif chosen.get("selection_reason_if_chosen"):
        reason = str(chosen.get("selection_reason_if_chosen"))
    else:
        reason = f"highest_admissible_under_data_ceiling:{mid}"

    marks = list(chosen.get("marks") or [])
    value_kind = str(chosen.get("value_kind") or "assumption_based_extrapolation")
    if mid in {
        "harmonic_modal_metadata_gate",
        "harmonic_modal_acoustic_model_unavailable",
    }:
        evidence = "LEVEL_0_UNSUPPORTED"
        value_kind = "unavailable"
    elif data.n_target_observations >= 6 and "spline" in mid:
        value_kind = "extrapolated"
        evidence = "LEVEL_4_MATCHED_EMPIRICAL"
    elif data.n_target_observations >= 3:
        value_kind = "extrapolated"
        evidence = "LEVEL_3_PARTIAL_EMPIRICAL"
    elif data.n_target_observations == 0:
        # Numeric scalars without verified bibliographic IDs are assumption-only.
        evidence = "LEVEL_1_ASSUMPTION_ONLY"
        if family == "mute_transfer_model":
            evidence = "LEVEL_1_ASSUMPTION_ONLY"
        value_kind = str(chosen.get("value_kind") or "assumption_based_extrapolation")
    else:
        evidence = "LEVEL_2_METADATA_CONSTRAINED"

    assumption_ids_out: list[str] = []
    if data.n_target_observations == 0 and data.technique == "sul_tasto":
        assumption_ids_out.append("ASSUMP_SUL_TASTO_ALPHA_MINUS_012")
    if data.n_target_observations == 0 and data.technique == "sul_ponticello":
        assumption_ids_out.append("ASSUMP_SUL_PONTICELLO_ALPHA_PLUS_020")
    if "scalar_descriptor_approximation" in marks:
        assumption_ids_out.append("ASSUMP_EWSD_OR_DESCRIPTOR_SCALAR_PROXY")
    if mid == "constant_assumption_fallback":
        if data.instrument == "vln":
            assumption_ids_out.extend(
                ["ASSUMP_MUTE_ATTENUATION_6DB", "ASSUMP_EWSD_PROPORTIONAL_TO_POWER"]
            )
        elif data.instrument == "vla":
            assumption_ids_out.extend(
                ["ASSUMP_MUTE_ATTENUATION_4DB", "ASSUMP_EWSD_PROPORTIONAL_TO_POWER"]
            )
        else:
            assumption_ids_out.append("ASSUMP_MUTE_GENERIC_ALPHA")
    if mid == "harmonic_modal_metadata_gate":
        assumption_ids_out.append("ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA")
    if mid == "harmonic_modal_acoustic_model_unavailable":
        assumption_ids_out.append("ASSUMP_HARMONIC_DESCRIPTOR_MODEL_NOT_IMPLEMENTED")

    # Mark higher disabled candidates as rejected if not already
    for step in ladder:
        sid = str(step["model_id"])
        if sid not in rejected and sid != mid and step not in admissible_sorted:
            if sid not in {str(s["model_id"]) for s in admissible}:
                rejected.setdefault(sid, "not_admissible_under_current_data")

    # Reject more complex than chosen for audit trail
    for step in admissible_sorted:
        sid = str(step["model_id"])
        if c_index(step) > c_index(chosen):
            rejected[sid] = "not_selected_simpler_or_equal_preferred"
        elif sid != mid and c_index(step) < c_index(chosen):
            rejected[sid] = "dominated_by_higher_admissible_data_ceiling"

    shape_id: bool | None = _register_shape_identified(mid, complexity)
    status = "completed_selected"
    explicit_fallback = chosen.get("fallback_level")
    if mid in {
        "harmonic_modal_metadata_gate",
        "harmonic_modal_acoustic_model_unavailable",
        "qualitative_or_na_mute",
        "multiphonic_qualitative_only",
        "flautando_qualitative_or_na",
        "qualitative_or_na",
    }:
        status = "completed_unavailable_or_qualitative"
        shape_id = None
        complexity = "not_applicable"
        explicit_fallback = "no_numeric_fallback"
    elif data.n_target_observations == 0:
        status = "completed_assumption_fallback"

    return ModelSelectionDecision(
        model_family=family,
        selected_model_id=mid,
        candidate_model_ids=candidate_ids,
        rejected_model_ids=sorted(rejected),
        rejection_reasons=rejected,
        selection_reason=reason,
        fallback_level=_complexity_to_fallback(complexity, explicit=explicit_fallback),
        complexity_level=complexity,
        model_selection_status=status,
        target_technique_observations=data.n_target_observations,
        distinct_pitch_count=data.distinct_pitch_count,
        pitch_span_semitones=data.pitch_span_semitones,
        required_covariates=_family_required_covariates(fam, family),
        available_covariates=list(dict.fromkeys(data.present_covariates)),
        missing_covariates=list(data.missing_covariates),
        register_shape_identified=shape_id,
        model_comparison_available=len(admissible) > 1,
        evidence_tier_hint=evidence,
        assumption_ids=assumption_ids_out,
        value_kind_hint=value_kind,
        marks=marks,
        admissible_model_ids=[str(s["model_id"]) for s in admissible_sorted],
        mechanism=str(fam.get("mechanism") or ""),
        target_quantity=data.target_quantity,
        **_harmonic_audit_fields(data, family),
    )


def select_register_model(data: DataAvailability, *, config: dict[str, Any] | None = None) -> str:
    """Convenience API matching the user's sketch for register-shape choice."""
    decision = select_model(data, config=config)
    mid = decision.selected_model_id
    if "spline" in mid:
        return "penalized_register_spline"
    if "linear" in mid:
        return "regularized_linear_trend"
    if "constant" in mid or mid.endswith("fallback"):
        return "constant_effect"
    if "spectral" in mid:
        return "spectral_transfer_model"
    if "physical" in mid:
        return "physical_informed"
    if "qualitative" in mid or "insufficient" in mid or "na" in mid:
        return "qualitative_or_na"
    return mid
