"""Activation gate for user assumptions — inactive unless explicitly enabled."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from string_technique_model.applicability import resolve_applicability
from string_technique_model.applicability.resolver import from_prediction_context
from string_technique_model.assumptions.registry import get_user_assumption_registry


class AssumptionConflictError(ValueError):
    """Raised when two active user assumptions can govern the same operation."""


@dataclass
class AssumptionActivationRecord:
    assumption_id: str
    status: str  # active | inactive
    reasons: list[str] = field(default_factory=list)
    assumption: dict[str, Any] = field(default_factory=dict)

    def to_row(self, prediction_id: str) -> dict[str, Any]:
        return {
            "prediction_id": prediction_id,
            "parameter_id": self.assumption_id,
            "parameter_status": "placeholder_user_input",
            "used_or_not_used": "used" if self.status == "active" else "not_used",
            "exclusion_reason": ";".join(self.reasons),
            "operation_type": self.assumption.get("operation_type"),
            "numerical_scale": self.assumption.get("numerical_scale"),
            "applicability_result": self.status,
            "source_ids": ";".join(self.assumption.get("source_ids") or []),
            "evidence_ids": "",
            "transfer_status": "direct",
            "effective_model_role": "user_assumption",
            "sampled_distribution": self.assumption.get("proposed_distribution"),
            "sampled_parameter_summary": None,
            "result_basis": "user_assumption",
            "literature_validated": False,
        }


def _scopes_overlap(left: Any, right: Any) -> bool:
    """Whether two assumptions' declared applicability scopes overlap."""
    scalar_fields = (
        "applicable_dynamic",
        "applicable_register",
        "applicable_string",
        "applicable_mute_type",
        "applicable_mute_material",
        "applicable_harmonic_type",
        "applicable_harmonic_order",
        "applicable_metric_definition_id",
    )
    for scope_field in scalar_fields:
        a, b = getattr(left, scope_field), getattr(right, scope_field)
        if a is not None and b is not None and a != b:
            return False
    for lower, upper in (
        ("applicable_pitch_min", "applicable_pitch_max"),
        ("applicable_frequency_min_hz", "applicable_frequency_max_hz"),
    ):
        a_low, a_high = getattr(left, lower), getattr(left, upper)
        b_low, b_high = getattr(right, lower), getattr(right, upper)
        if a_high is not None and b_low is not None and a_high < b_low:
            return False
        if b_high is not None and a_low is not None and b_high < a_low:
            return False
    return True


def resolve_user_assumptions(
    *,
    context: dict[str, Any],
    link: str,
    activation_enabled: bool,
    path: str | None = None,
) -> list[AssumptionActivationRecord]:
    """Resolve user assumptions for a prediction cell.

    Activation requires:
    - ``activation_enabled`` True for this run (explicit CLI/config)
    - assumption.active_for_density_prediction True
    - reported_value present
    - link in compatible_links
    - applicability match
    """
    registry = get_user_assumption_registry(path)
    instrument = str(context.get("instrument") or "")
    technique = str(context.get("technique") or "")
    records: list[AssumptionActivationRecord] = []

    for assumption in registry.assumptions:
        if assumption.instrument != instrument or assumption.technique != technique:
            continue
        param = assumption.to_parameter_dict()
        reasons: list[str] = []

        if not activation_enabled:
            reasons.append("user_assumption_activation_disabled_for_run")
        if not assumption.active_for_density_prediction:
            reasons.append("assumption_flagged_inactive")
        if registry.default_active_for_density_prediction is False and not assumption.active_for_density_prediction:
            # reinforce; already covered
            pass
        if assumption.reported_value is None:
            reasons.append("missing_reported_value")
        if link not in assumption.compatible_links:
            reasons.append(f"link_incompatible:{link}")
        if assumption.literature_validated:
            reasons.append("invalid_literature_validated_flag")

        app = resolve_applicability(param, from_prediction_context(context))
        app_status = getattr(app.status, "value", app.status)
        if app_status == "insufficient_metadata":
            # User assumptions may declare no applicability dimensions → treat as matched
            # only when no applicability fields present; otherwise insufficient.
            from string_technique_model.applicability import applicability_present

            if applicability_present(param):
                reasons.append("insufficient_metadata")
                reasons.extend(app.reasons)
        elif app_status == "not_applicable":
            reasons.extend(app.reasons or ["not_applicable"])
        elif app_status == "contradictory_metadata":
            reasons.extend(app.reasons or ["contradictory_metadata"])

        status = "active" if not reasons else "inactive"
        records.append(
            AssumptionActivationRecord(
                assumption_id=assumption.assumption_id,
                status=status,
                reasons=reasons,
                assumption=param,
            )
        )
    active = [record for record in records if record.status == "active"]
    for index, record in enumerate(active):
        left = registry.by_id(record.assumption_id)
        for other in active[index + 1 :]:
            right = registry.by_id(other.assumption_id)
            if (
                left.operation_type == right.operation_type
                and _scopes_overlap(left, right)
            ):
                raise AssumptionConflictError(
                    "Conflicting active user assumptions for "
                    f"{instrument}/{technique}/{left.operation_type}: "
                    f"{left.assumption_id}, {right.assumption_id}"
                )
    return records


def assumption_label_fields(active_ids: list[str]) -> dict[str, Any]:
    """Fields that must appear on any assumption-based numerical result."""
    return {
        "result_basis": "user_assumption",
        "literature_validated": False,
        "evidence_based": False,
        "assumption_ids_used": ";".join(active_ids),
        "prediction_status": "predicted_from_user_assumption",
        "evidence_grade": "D",
        "metric_mapping_status": "user_assumption_explicit",
        "measured_or_estimated": "modelled_assumption_based",
        "provenance": (
            "ASSUMPTION-BASED (not literature-validated; not evidence-based). "
            f"Assumptions used: {';'.join(active_ids)}. "
            "See configs/user_assumptions.yaml for units, scope, uncertainty, "
            "operationalisation, and operation/link compatibility."
        ),
    }
