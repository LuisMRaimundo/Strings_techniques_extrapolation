"""Prediction-time parameter activation gate.

Wraps the literature activation gate and adds metric-backend mapping checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from string_technique_model.literature.activation import (
    DENSITY_ACTIVATING_MAPPINGS,
    ActivationDecision,
    ApplicabilityQuery,
    evaluate_parameter_activation,
)
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.source_registry import SourceRegistry
from string_technique_model.prediction.applicability import resolve_applicability
from string_technique_model.prediction.operations import is_density_transform_operation

# Phase-4 metric-only also accepts an explicitly approved mapping name.
METRIC_ONLY_MAPPINGS = frozenset(
    set(DENSITY_ACTIVATING_MAPPINGS) | {"approved_explicit_metric_mapping"}
)


@dataclass
class PredictionActivationRecord:
    parameter_id: str
    status: str  # active | inactive | conditionally_active | not_applicable
    reasons: list[str] = field(default_factory=list)
    parameter: dict[str, Any] = field(default_factory=dict)

    def to_row(self, prediction_id: str) -> dict[str, Any]:
        return {
            "prediction_id": prediction_id,
            "parameter_id": self.parameter_id,
            "parameter_status": self.parameter.get("parameter_status"),
            "used_or_not_used": "used" if self.status == "active" else "not_used",
            "exclusion_reason": ";".join(self.reasons),
            "operation_type": self.parameter.get("operation_type"),
            "numerical_scale": self.parameter.get("numerical_scale"),
            "applicability_result": self.status,
            "source_ids": ";".join(self.parameter.get("source_ids") or [])
            if isinstance(self.parameter.get("source_ids"), list)
            else self.parameter.get("source_ids"),
            "evidence_ids": ";".join(self.parameter.get("evidence_ids") or [])
            if isinstance(self.parameter.get("evidence_ids"), list)
            else self.parameter.get("evidence_ids"),
            "transfer_status": self.parameter.get("direct_or_transferred"),
            "effective_model_role": self.parameter.get("model_component"),
            "sampled_distribution": self.parameter.get("proposed_distribution"),
            "sampled_parameter_summary": None,
        }


def resolve_prediction_parameters(
    candidates: list[dict[str, Any]],
    *,
    registry: SourceRegistry,
    extracts: list[EvidenceExtract],
    context: dict[str, Any],
    backend: str,
    transfers_enabled: bool = False,
    allow_wider_without_metadata: bool = False,
) -> list[PredictionActivationRecord]:
    extracts_by_id = {str(e.evidence_id): e for e in extracts if e.evidence_id}
    query = ApplicabilityQuery(
        instrument=str(context["instrument"]),
        technique=str(context["technique"]),
        pitch=context.get("pitch_midi_sounding"),
        frequency_hz=context.get("frequency_hz"),
        register=context.get("register"),
        dynamic=context.get("dynamic"),
        string_name=context.get("string_name"),
        harmonic_type=context.get("harmonic_type"),
        harmonic_order=context.get("harmonic_order"),
        mute_type=context.get("mute_type"),
        mute_mass=context.get("mute_mass"),
        bow_position=context.get("bow_position_ratio"),
        temporal_region=context.get("temporal_region"),
        metric_definition=context.get("target_metric_definition_id"),
    )

    records: list[PredictionActivationRecord] = []
    for param in candidates:
        lit: ActivationDecision = evaluate_parameter_activation(
            param,
            registry=registry,
            extracts_by_id=extracts_by_id,
            target=query,
        )
        reasons = list(lit.reasons)
        mapping = param.get("density_mapping_status")

        if backend == "metric-only" and mapping not in METRIC_ONLY_MAPPINGS:
            reasons.append("incompatible_metric_mapping_for_backend")

        app = resolve_applicability(
            param,
            context,
            allow_wider_without_metadata=allow_wider_without_metadata,
        )
        app_status = getattr(app.status, "value", app.status)
        if app_status == "insufficient_metadata":
            reasons.append("insufficient_metadata")
        elif app_status == "not_applicable":
            reasons.extend(app.reasons)
        elif app_status == "contradictory_metadata":
            reasons.extend(app.reasons or ["contradictory_metadata"])
        elif app_status == "applicable_only_by_explicit_transfer":
            reasons.append("applicable_only_by_explicit_transfer")

        if param.get("direct_or_transferred") == "transferred":
            if not transfers_enabled:
                reasons.append("cross_instrument_transfer_inactive")
            elif not param.get("transfer_equation"):
                reasons.append("transfer_equation_missing")

        if not is_density_transform_operation(str(param.get("operation_type") or "")):
            if lit.active:
                reasons.append("operation_not_density_transform")

        # Deduplicate
        uniq: list[str] = []
        seen: set[str] = set()
        for r in reasons:
            if r not in seen:
                seen.add(r)
                uniq.append(r)

        if app_status == "not_applicable":
            status = "not_applicable"
        elif uniq:
            # Conditionally active only if sole issue is missing optional metadata widen flag
            if uniq == ["insufficient_metadata"] and allow_wider_without_metadata:
                status = "conditionally_active"
            else:
                status = "inactive"
        elif lit.active and mapping in METRIC_ONLY_MAPPINGS:
            status = "active"
        else:
            status = "inactive"
            if not uniq:
                uniq = ["not_activated_by_literature_gate"]

        records.append(
            PredictionActivationRecord(
                parameter_id=str(param.get("parameter_id")),
                status=status,
                reasons=uniq,
                parameter=param,
            )
        )
    return records
