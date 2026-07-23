"""Pydantic models for the user numerical-assumption registry."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES
from string_technique_model.prediction.operations import OPERATION_SPECS, is_density_transform_operation

OperationType = Literal[
    "multiplicative_ratio",
    "additive_difference",
    "additive_log_difference",
]


class UserAssumption(BaseModel):
    """One user-supplied numerical assumption — never literature evidence."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    assumption_id: str
    name: str | None = None
    instrument: str
    technique: str
    operation_type: str
    reported_value: float | None = None
    unit: str
    numerical_scale: str
    compatible_links: list[str] = Field(default_factory=list)
    source_space: str
    target_space: str
    uncertainty_sd: float | None = None
    uncertainty_distribution: dict[str, Any] | str | None = None
    distribution_parameters: dict[str, Any] | None = None
    applicable_dynamic: str | None = None
    applicable_register: str | None = None
    applicable_pitch_min: float | None = None
    applicable_pitch_max: float | None = None
    applicable_frequency_min_hz: float | None = None
    applicable_frequency_max_hz: float | None = None
    applicable_string: str | None = None
    applicable_mute_type: str | None = None
    applicable_mute_material: str | None = None
    applicable_harmonic_type: str | None = None
    applicable_harmonic_order: int | None = None
    applicable_metric_definition_id: str | None = "ewsd_v1"
    scope_note: str | None = None
    operationalisation: str
    provenance: str
    citation_or_rationale: str | None = None
    active_for_density_prediction: bool = False
    curator_status: str = "draft"
    literature_validated: bool = False  # always treated as False for this registry

    @field_validator("instrument")
    @classmethod
    def _instrument(cls, v: str) -> str:
        if v not in ALLOWED_INSTRUMENTS:
            raise ValueError(f"Unsupported instrument: {v}")
        return v

    @field_validator("technique")
    @classmethod
    def _technique(cls, v: str) -> str:
        if v not in ALLOWED_TECHNIQUES:
            raise ValueError(f"Unsupported technique: {v}")
        return v

    @field_validator("literature_validated")
    @classmethod
    def _never_literature(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "User assumptions cannot set literature_validated=true; "
                "they are never literature evidence."
            )
        return False

    @model_validator(mode="after")
    def _check_operation_and_value(self) -> UserAssumption:
        if not is_density_transform_operation(self.operation_type):
            raise ValueError(
                f"operation_type {self.operation_type!r} is not a density transform; "
                "user assumptions for EWSD must use multiplicative_ratio, "
                "additive_difference, or additive_log_difference"
            )
        if not self.operationalisation or not str(self.operationalisation).strip():
            raise ValueError("operationalisation text is required for every user assumption")
        if not self.provenance or not str(self.provenance).strip():
            raise ValueError("provenance is required for every user assumption")
        if not self.unit or not str(self.unit).strip():
            raise ValueError("unit is required")
        if not self.compatible_links:
            raise ValueError("compatible_links must list at least one link (e.g. log, identity)")
        spec = OPERATION_SPECS.get(self.operation_type)
        if spec is not None:
            if self.source_space != spec.source_space:
                raise ValueError(
                    f"source_space {self.source_space!r} incompatible with "
                    f"{self.operation_type} (expected {spec.source_space})"
                )
            if self.target_space != spec.target_space:
                raise ValueError(
                    f"target_space {self.target_space!r} incompatible with "
                    f"{self.operation_type} (expected {spec.target_space})"
                )
            bad = set(self.compatible_links) - set(spec.compatible_links)
            if bad:
                raise ValueError(
                    f"compatible_links {sorted(bad)} not allowed for {self.operation_type}; "
                    f"allowed={sorted(spec.compatible_links)}"
                )
        if self.active_for_density_prediction and self.reported_value is None:
            raise ValueError(
                f"{self.assumption_id}: active_for_density_prediction requires reported_value"
            )
        if self.uncertainty_sd is not None and self.uncertainty_sd < 0:
            raise ValueError("uncertainty_sd must be non-negative when provided")
        return self

    def to_parameter_dict(self) -> dict[str, Any]:
        """Map to the prediction parameter shape used by Monte Carlo ops."""
        dist = self.uncertainty_distribution
        dist_params = dict(self.distribution_parameters or {})
        if dist is None and self.uncertainty_sd is not None and self.reported_value is not None:
            dist = "normal"
            dist_params = {"mean": float(self.reported_value), "sd": float(self.uncertainty_sd)}
        return {
            "parameter_id": self.assumption_id,
            "parameter_name": self.name or self.assumption_id,
            "instrument": self.instrument,
            "technique": self.technique,
            "operation_type": self.operation_type,
            "reported_value": self.reported_value,
            "unit": self.unit,
            "numerical_scale": self.numerical_scale,
            "compatible_links": list(self.compatible_links),
            "source_space": self.source_space,
            "target_space": self.target_space,
            "proposed_distribution": dist,
            "distribution_parameters": dist_params,
            "applicable_dynamic": self.applicable_dynamic,
            "applicable_register": self.applicable_register,
            "applicable_pitch_min": self.applicable_pitch_min,
            "applicable_pitch_max": self.applicable_pitch_max,
            "applicable_frequency_min_hz": self.applicable_frequency_min_hz,
            "applicable_frequency_max_hz": self.applicable_frequency_max_hz,
            "applicable_string": self.applicable_string,
            "applicable_mute_type": self.applicable_mute_type,
            "applicable_mute_material": self.applicable_mute_material,
            "applicable_harmonic_type": self.applicable_harmonic_type,
            "applicable_harmonic_order": self.applicable_harmonic_order,
            "applicable_metric_definition_id": self.applicable_metric_definition_id,
            "scope_note": self.scope_note,
            "operationalisation": self.operationalisation,
            "provenance": self.provenance,
            "citation_or_rationale": self.citation_or_rationale,
            "active_for_density_prediction": self.active_for_density_prediction,
            "parameter_status": "placeholder_user_input",
            "density_mapping_status": "user_assumption_explicit",
            "direct_or_transferred": "direct",
            "source_ids": [f"USER_ASSUMPTION:{self.assumption_id}"],
            "evidence_ids": [],
            "result_basis": "user_assumption",
            "literature_validated": False,
            "evidence_grade": "D",
        }


class UserAssumptionRegistry(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str | None = None
    schema_version: str = "user_assumption_v1"
    registry_kind: str = "user_numerical_assumptions"
    literature_validated: bool = False
    default_active_for_density_prediction: bool = False
    assumptions: list[UserAssumption] = Field(default_factory=list)

    def by_id(self, assumption_id: str) -> UserAssumption:
        for assumption in self.assumptions:
            if assumption.assumption_id == assumption_id:
                return assumption
        raise KeyError(assumption_id)
