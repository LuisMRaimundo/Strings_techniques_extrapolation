"""Strict parameter activation gate for density prediction.

Bibliographically valid ≠ active for density prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from string_technique_model.applicability import (
    ApplicabilityStatus,
    applicability_present,
    from_literature_query,
)
from string_technique_model.applicability import (
    resolve_applicability as _resolve_applicability,
)
from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.scales import is_decibel_scale, refuse_db_as_density_multiplier
from string_technique_model.literature.source_registry import SourceRegistry
from string_technique_model.provenance import (
    normalize_evidence_ids,
    normalize_source_ids,
    resolve_parameter_provenance,
)

DENSITY_ACTIVATING_MAPPINGS = frozenset(
    {
        "direct_same_metric",
        "directly_computable_from_reported_spectrum",
    }
)

INACTIVE_MAPPING_REASONS = {
    "indirect_proxy": "indirect_density_proxy",
    "qualitative_constraint_only": "qualitative_only",
    "incompatible_variable": "incompatible_metric",
    "insufficient_information": "incompatible_metric",
    "computable_from_reported_partial_data": "incompatible_metric",
    "computable_from_digitised_figure": "incompatible_metric",
}

@dataclass
class ActivationDecision:
    parameter_id: str
    active: bool
    reasons: list[str] = field(default_factory=list)
    applicability_status: str | None = None
    density_mapping_status: str | None = None
    parameter_status: str | None = None
    active_for_density_prediction: bool = False

    def to_row(self) -> dict[str, Any]:
        return {
            "parameter_id": self.parameter_id,
            "active": self.active,
            "active_for_density_prediction": self.active_for_density_prediction,
            "failure_reasons": ";".join(self.reasons),
            "applicability_status": self.applicability_status,
            "density_mapping_status": self.density_mapping_status,
            "parameter_status": self.parameter_status,
        }


@dataclass
class ApplicabilityQuery:
    instrument: str
    technique: str
    pitch: float | None = None
    frequency_hz: float | None = None
    register: str | None = None
    dynamic: str | None = None
    string_name: str | None = None
    harmonic_type: str | None = None
    harmonic_order: int | None = None
    mute_type: str | None = None
    mute_mass: str | float | None = None
    bow_position: str | None = None
    temporal_region: str | None = None
    metric_definition: str | None = None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x).strip()]
    if isinstance(value, str):
        return [x for x in value.split(";") if x.strip()]
    return [str(value)]


def _map_applicability_status(result_status: ApplicabilityStatus, reasons: list[str]) -> str:
    if result_status == ApplicabilityStatus.matched:
        return "matched"
    if result_status == ApplicabilityStatus.insufficient_metadata:
        if reasons == ["insufficient_metadata"]:
            return "insufficiently_specified"
        return reasons[0] if reasons else "insufficiently_specified"
    if result_status == ApplicabilityStatus.applicable_only_by_explicit_transfer:
        return "applicable_only_by_explicit_transfer"
    if result_status == ApplicabilityStatus.contradictory_metadata:
        return "contradictory_metadata"
    return reasons[0] if reasons else "not_applicable"


def match_applicability(param: dict[str, Any], query: ApplicabilityQuery | None) -> tuple[bool, str]:
    """Match parameter applicability. Absent applicability → insufficiently_specified."""
    if not applicability_present(param):
        return False, "insufficiently_specified"
    if query is None:
        return False, "insufficiently_specified"

    unified = from_literature_query(query)
    result = _resolve_applicability(param, unified)
    status_str = _map_applicability_status(result.status, result.reasons)
    return result.status == ApplicabilityStatus.matched, status_str


def evaluate_parameter_activation(
    param: dict[str, Any],
    *,
    registry: SourceRegistry,
    extracts_by_id: dict[str, EvidenceExtract],
    target: ApplicabilityQuery | None = None,
) -> ActivationDecision:
    """Activate only when all density-prediction gate conditions hold."""
    pid = str(param.get("parameter_id") or "")
    reasons: list[str] = []
    mapping = param.get("density_mapping_status")
    status = param.get("parameter_status")
    flagged_active = bool(param.get("active_for_density_prediction"))

    decision = ActivationDecision(
        parameter_id=pid,
        active=False,
        density_mapping_status=mapping,
        parameter_status=status,
        active_for_density_prediction=False,
    )

    if status == "prohibited":
        reasons.append("prohibited_parameter")
    if status == "unresolved":
        reasons.append("unresolved_parameter")
    if status == "qualitative_only":
        reasons.append("qualitative_only")

    if not param.get("operation_type"):
        reasons.append("missing_operation_type")
    if not param.get("numerical_scale"):
        reasons.append("missing_numerical_scale")
    if not param.get("unit"):
        reasons.append("missing_units")

    if refuse_db_as_density_multiplier(param.get("numerical_scale"), param.get("operation_type")):
        reasons.append("indirect_density_proxy")

    if mapping in INACTIVE_MAPPING_REASONS:
        reason = INACTIVE_MAPPING_REASONS[mapping]
        if reason not in reasons:
            reasons.append(reason)
    elif mapping not in DENSITY_ACTIVATING_MAPPINGS:
        if mapping is None:
            reasons.append("missing_density_mapping")
        else:
            reasons.append("incompatible_metric")

    source_ids = normalize_source_ids(param) or _as_list(param.get("source_ids"))
    evidence_ids = normalize_evidence_ids(param) or _as_list(param.get("evidence_ids"))
    if not source_ids:
        reasons.append("unresolved_scientific_provenance")
        reasons.append("source_not_verified")
    if not evidence_ids:
        reasons.append("unresolved_scientific_provenance")
        reasons.append("evidence_not_verified")

    resolved = resolve_parameter_provenance(param, registry, list(extracts_by_id.values()))
    if not resolved.ok:
        reasons.append("unresolved_scientific_provenance")
    for sid in source_ids:
        src = registry.sources.get(sid)
        if src is None or src.evidence_status != "verified_local_source":
            reasons.append("source_not_verified")
            break
        if not src.may_support_parameters():
            reasons.append("source_not_verified")
            break

    for eid in evidence_ids:
        ext = extracts_by_id.get(eid)
        if ext is None or not ext.is_validated() or not ext.has_location():
            reasons.append("evidence_not_verified")
            break

    if target is not None:
        if param.get("instrument") and param["instrument"] != target.instrument:
            reasons.append("instrument_mismatch")
        if param.get("technique") and param["technique"] != target.technique:
            reasons.append("technique_mismatch")
        if (
            target.technique == "artificial_harmonic"
            and param.get("applicable_harmonic_type") == "natural"
        ):
            reasons.append("harmonic_type_mismatch")
        if param.get("technique") == "artificial_harmonic" and target.harmonic_type == "natural":
            reasons.append("harmonic_type_mismatch")

    matched, app_status = match_applicability(param, target)
    decision.applicability_status = app_status
    if app_status == "insufficiently_specified":
        reasons.append("missing_applicability")
    elif not matched:
        reasons.append(app_status)

    if param.get("direct_or_transferred") == "transferred" and not param.get("transfer_equation"):
        reasons.append("cross_instrument_transfer_inactive")

    if not flagged_active:
        reasons.append("curated_inactive_for_density")

    inst = param.get("instrument")
    tech = param.get("technique")
    if inst and inst not in ALLOWED_INSTRUMENTS:
        reasons.append("instrument_mismatch")
    if tech and tech not in ALLOWED_TECHNIQUES:
        reasons.append("technique_mismatch")

    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    decision.reasons = uniq

    can_activate = (
        not uniq
        and mapping in DENSITY_ACTIVATING_MAPPINGS
        and flagged_active
        and status not in {"prohibited", "unresolved", "qualitative_only"}
    )
    decision.active = can_activate
    decision.active_for_density_prediction = can_activate
    if not can_activate and not decision.reasons:
        decision.reasons = ["unresolved_parameter"]
    return decision


def evaluate_all_parameters(
    parameters: list[dict[str, Any]],
    *,
    registry: SourceRegistry,
    extracts: list[EvidenceExtract],
    target: ApplicabilityQuery | None = None,
) -> list[ActivationDecision]:
    by_id = {str(e.evidence_id): e for e in extracts if e.evidence_id}
    return [
        evaluate_parameter_activation(p, registry=registry, extracts_by_id=by_id, target=target)
        for p in parameters
    ]


def db_value_is_not_density(param: dict[str, Any]) -> bool:
    """Helper for tests: confirm dB/level parameters cannot activate density."""
    if is_decibel_scale(param.get("numerical_scale")):
        return True
    if param.get("density_mapping_status") == "indirect_proxy":
        return True
    return False
