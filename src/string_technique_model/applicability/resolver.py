"""Unified applicability resolution for literature and prediction layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from string_technique_model.production.mute import normalize_mute_mass

APPLICABILITY_FIELDS = (
    "applicable_pitch_min",
    "applicable_pitch_max",
    "applicable_frequency_min_hz",
    "applicable_frequency_max_hz",
    "applicable_register",
    "applicable_dynamic",
    "applicable_string",
    "applicable_temporal_region",
    "applicable_mute_type",
    "applicable_mute_material",
    "applicable_mute_mass_min_g",
    "applicable_mute_mass_max_g",
    "applicable_harmonic_type",
    "applicable_harmonic_order",
    "applicable_bow_position_min",
    "applicable_bow_position_max",
    "applicable_relative_bow_bridge_distance_beta_min",
    "applicable_relative_bow_bridge_distance_beta_max",
    "applicable_metric_definition_id",
)


class ApplicabilityStatus(str, Enum):
    matched = "matched"
    not_applicable = "not_applicable"
    insufficient_metadata = "insufficient_metadata"
    applicable_only_by_explicit_transfer = "applicable_only_by_explicit_transfer"
    contradictory_metadata = "contradictory_metadata"


@dataclass
class ApplicabilityQuery:
    instrument: str | None = None
    technique: str | None = None
    technique_components: dict[str, Any] | None = None
    pitch_midi: float | None = None
    frequency_hz: float | None = None
    register: str | None = None
    dynamic: str | None = None
    string_name: str | None = None
    temporal_region: str | None = None
    mute_type: str | None = None
    mute_material: str | None = None
    mute_mass_g: float | None = None
    mute_mass_min: float | None = None
    mute_mass_max: float | None = None
    harmonic_type: str | None = None
    harmonic_order: int | None = None
    relative_bow_bridge_distance_beta: float | None = None
    beta_min: float | None = None
    beta_max: float | None = None
    target_metric_definition_id: str | None = None


@dataclass
class ApplicabilityResult:
    status: ApplicabilityStatus
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == ApplicabilityStatus.matched


def _is_present(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "null", "None"}


def applicability_present(param: dict[str, Any]) -> bool:
    """True when at least one declared applicability dimension is set on the parameter."""
    for key in APPLICABILITY_FIELDS:
        if _is_present(param.get(key)):
            return True
    return False


def _resolve_mute_mass_g(query: ApplicabilityQuery) -> float | None:
    if query.mute_mass_g is not None:
        return float(query.mute_mass_g)
    return None


def from_literature_query(old_query: Any) -> ApplicabilityQuery:
    """Adapt literature ``ApplicabilityQuery`` to the unified query type."""
    mute_mass_g: float | None = None
    raw_mass = getattr(old_query, "mute_mass", None)
    if raw_mass is not None:
        grams, _, _ = normalize_mute_mass(raw_mass)
        mute_mass_g = grams

    bow_beta = getattr(old_query, "bow_position", None)
    beta: float | None = None
    if bow_beta is not None:
        try:
            beta = float(bow_beta)
        except (TypeError, ValueError):
            beta = None

    return ApplicabilityQuery(
        instrument=getattr(old_query, "instrument", None),
        technique=getattr(old_query, "technique", None),
        pitch_midi=getattr(old_query, "pitch", None),
        frequency_hz=getattr(old_query, "frequency_hz", None),
        register=getattr(old_query, "register", None),
        dynamic=getattr(old_query, "dynamic", None),
        string_name=getattr(old_query, "string_name", None),
        temporal_region=getattr(old_query, "temporal_region", None),
        mute_type=getattr(old_query, "mute_type", None),
        mute_mass_g=mute_mass_g,
        harmonic_type=getattr(old_query, "harmonic_type", None),
        harmonic_order=getattr(old_query, "harmonic_order", None),
        relative_bow_bridge_distance_beta=beta,
        target_metric_definition_id=getattr(old_query, "metric_definition", None),
    )


def from_prediction_context(context: dict[str, Any]) -> ApplicabilityQuery:
    """Build unified query from prediction context dict."""
    mute_mass_g: float | None = None
    raw_mass = context.get("mute_mass_g")
    if raw_mass is None:
        raw_mass = context.get("mute_mass")
    if raw_mass is not None:
        if isinstance(raw_mass, (int, float)):
            mute_mass_g = float(raw_mass)
        else:
            grams, _, _ = normalize_mute_mass(raw_mass)
            mute_mass_g = grams

    beta = context.get("relative_bow_bridge_distance_beta")
    if beta is None and context.get("bow_position_ratio") is not None:
        try:
            beta = float(context["bow_position_ratio"])
        except (TypeError, ValueError):
            beta = None

    pitch = context.get("pitch_midi_sounding")
    if pitch is None:
        pitch = context.get("pitch_midi")

    harmonic_type = context.get("harmonic_type")
    if harmonic_type is None and context.get("technique") == "artificial_harmonic":
        harmonic_type = "artificial"

    return ApplicabilityQuery(
        instrument=context.get("instrument"),
        technique=context.get("technique"),
        technique_components=context.get("technique_components"),
        pitch_midi=pitch,
        frequency_hz=context.get("frequency_hz"),
        register=context.get("register"),
        dynamic=context.get("dynamic"),
        string_name=context.get("string_name"),
        temporal_region=context.get("temporal_region"),
        mute_type=context.get("mute_type"),
        mute_material=context.get("mute_material"),
        mute_mass_g=mute_mass_g,
        mute_mass_min=context.get("mute_mass_min"),
        mute_mass_max=context.get("mute_mass_max"),
        harmonic_type=harmonic_type,
        harmonic_order=context.get("harmonic_order"),
        relative_bow_bridge_distance_beta=beta,
        beta_min=context.get("beta_min"),
        beta_max=context.get("beta_max"),
        target_metric_definition_id=context.get("target_metric_definition_id"),
    )


def _float_param(param: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        val = param.get(key)
        if _is_present(val):
            try:
                return float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
    return None


def resolve_applicability(
    param: dict[str, Any],
    query: ApplicabilityQuery,
    *,
    allow_wider_without_metadata: bool = False,
) -> ApplicabilityResult:
    """Evaluate all declared applicability dimensions against the query."""
    if param.get("direct_or_transferred") == "transferred" and not param.get("transfer_equation"):
        if applicability_present(param):
            return ApplicabilityResult(
                ApplicabilityStatus.applicable_only_by_explicit_transfer,
                ["explicit_transfer_required"],
            )

    if not applicability_present(param):
        if allow_wider_without_metadata:
            return ApplicabilityResult(ApplicabilityStatus.matched, ["wider_conditional_allowed"])
        return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["insufficient_metadata"])

    if param.get("instrument") and query.instrument:
        if param["instrument"] != query.instrument:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["instrument_mismatch"])

    if param.get("technique") and query.technique:
        if param["technique"] != query.technique:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["technique_mismatch"])

    metric = param.get("applicable_metric_definition_id") or param.get("target_metric_definition_id")
    if metric and query.target_metric_definition_id:
        if str(metric) != str(query.target_metric_definition_id):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["metric_definition_mismatch"])

    if _is_present(param.get("applicable_dynamic")):
        if not query.dynamic:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["dynamic_required"])
        if str(param["applicable_dynamic"]) != str(query.dynamic):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["dynamic_mismatch"])

    if _is_present(param.get("applicable_register")):
        if not query.register:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["register_required"])
        if str(param["applicable_register"]) != str(query.register):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["register_mismatch"])

    if _is_present(param.get("applicable_string")):
        if not query.string_name:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["string_required"])
        if str(param["applicable_string"]) != str(query.string_name):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["string_mismatch"])

    if _is_present(param.get("applicable_temporal_region")):
        if not query.temporal_region:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["temporal_region_required"],
            )
        if str(param["applicable_temporal_region"]) != str(query.temporal_region):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["temporal_region_mismatch"])

    if _is_present(param.get("applicable_mute_type")):
        if not query.mute_type:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["mute_type_required"])
        if str(param["applicable_mute_type"]) != str(query.mute_type):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["mute_type_mismatch"])

    if _is_present(param.get("applicable_mute_material")):
        if not query.mute_material:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["mute_material_required"],
            )
        if str(param["applicable_mute_material"]).lower() != str(query.mute_material).lower():
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["mute_material_mismatch"])

    mute_mass_min = _float_param(param, "applicable_mute_mass_min_g")
    mute_mass_max = _float_param(param, "applicable_mute_mass_max_g")
    if mute_mass_min is not None or mute_mass_max is not None:
        mass_g = _resolve_mute_mass_g(query)
        if mass_g is None:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["mute_mass_required"])
        if mute_mass_min is not None and mass_g < mute_mass_min:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["mute_mass_out_of_range"])
        if mute_mass_max is not None and mass_g > mute_mass_max:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["mute_mass_out_of_range"])

    if _is_present(param.get("applicable_harmonic_type")):
        ctx_harm = query.harmonic_type
        if not ctx_harm and query.technique == "artificial_harmonic":
            ctx_harm = "artificial"
        if not ctx_harm:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["harmonic_type_required"],
            )
        if str(param["applicable_harmonic_type"]) != str(ctx_harm):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["harmonic_type_mismatch"])

    if _is_present(param.get("applicable_harmonic_order")):
        if query.harmonic_order is None:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["harmonic_order_required"],
            )
        if int(param["applicable_harmonic_order"]) != int(query.harmonic_order):
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["harmonic_order_mismatch"])

    pmin = _float_param(param, "applicable_pitch_min")
    pmax = _float_param(param, "applicable_pitch_max")
    if pmin is not None or pmax is not None:
        if query.pitch_midi is None:
            return ApplicabilityResult(ApplicabilityStatus.insufficient_metadata, ["pitch_required_for_range"])
        if pmin is not None and query.pitch_midi < pmin:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["pitch_out_of_range"])
        if pmax is not None and query.pitch_midi > pmax:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["pitch_out_of_range"])

    fmin = _float_param(param, "applicable_frequency_min_hz")
    fmax = _float_param(param, "applicable_frequency_max_hz")
    if fmin is not None or fmax is not None:
        if query.frequency_hz is None:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["frequency_required_for_range"],
            )
        if fmin is not None and query.frequency_hz < fmin:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["frequency_out_of_range"])
        if fmax is not None and query.frequency_hz > fmax:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["frequency_out_of_range"])

    beta_min = _float_param(
        param,
        "applicable_relative_bow_bridge_distance_beta_min",
        "applicable_bow_position_min",
    )
    beta_max = _float_param(
        param,
        "applicable_relative_bow_bridge_distance_beta_max",
        "applicable_bow_position_max",
    )
    if beta_min is not None or beta_max is not None:
        beta = query.relative_bow_bridge_distance_beta
        if beta is None:
            return ApplicabilityResult(
                ApplicabilityStatus.insufficient_metadata,
                ["bow_beta_required_for_range"],
            )
        if beta_min is not None and beta < beta_min:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["bow_beta_out_of_range"])
        if beta_max is not None and beta > beta_max:
            return ApplicabilityResult(ApplicabilityStatus.not_applicable, ["bow_beta_out_of_range"])

    if query.mute_mass_min is not None and query.mute_mass_max is not None:
        if query.mute_mass_min > query.mute_mass_max:
            return ApplicabilityResult(
                ApplicabilityStatus.contradictory_metadata,
                ["contradictory_mute_mass_range_in_query"],
            )

    if query.beta_min is not None and query.beta_max is not None:
        if query.beta_min > query.beta_max:
            return ApplicabilityResult(
                ApplicabilityStatus.contradictory_metadata,
                ["contradictory_beta_range_in_query"],
            )

    return ApplicabilityResult(ApplicabilityStatus.matched, [])
