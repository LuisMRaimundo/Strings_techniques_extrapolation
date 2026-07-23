"""
Technique-recognition result models.

Recognition outputs (confidence, rank, candidate lists) describe classifier behaviour.
They are **not** converted to EWSD density coefficients and must not be treated as
activated numerical density mappings without separate validated evidence.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

_EWSD_FORBIDDEN_FIELDS = frozenset({"ewsd", "ewsd_coefficient", "density_coefficient"})


class TechniqueRecognitionResult(BaseModel):
    """Single technique-recognition prediction from an external or internal classifier."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    predicted_technique: str | None = None
    confidence: float | None = None
    rank: int | None = None
    candidate_techniques: list[str] = Field(default_factory=list)
    source_taxonomy_label: str | None = None
    internal_ontology_mapping: str | None = None
    feature_backend: str | None = None
    model_version: str | None = None
    dataset: str | None = None
    uncertainty: dict[str, Any] | str | float | None = None

    @model_validator(mode="after")
    def _reject_ewsd_claims(self) -> TechniqueRecognitionResult:
        extra = getattr(self, "model_extra", None) or {}
        for key in extra:
            if key in _EWSD_FORBIDDEN_FIELDS or key.startswith("ewsd_"):
                raise ValueError(
                    "TechniqueRecognitionResult must not carry EWSD or density-coefficient fields"
                )
        return self

    @property
    def claims_ewsd(self) -> bool:
        """Always False — recognition confidence is not an EWSD mapping."""
        return False


class RecognitionLabelMapping(BaseModel):
    """Maps an external taxonomy label to an internal ontology id (or unresolved)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    source_label: str
    ontology_id: str | None = None
    unresolved: bool = False
    notes: str | None = None


class RecognitionLabelMappingRegistry(BaseModel):
    """Stub registry for Lostanlen-style external labels → internal ontology."""

    model_config = ConfigDict(extra="allow")

    version: str | None = None
    schema_version: str | None = None
    source_taxonomy: str | None = None
    mappings: list[RecognitionLabelMapping] = Field(default_factory=list)
