"""Pydantic models for qualitative acoustic constraints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductionCondition(BaseModel):
    """Production-side match conditions from YAML."""

    model_config = ConfigDict(extra="allow")

    bow_contact_category_any_of: list[str] | None = None
    mute_category: str | None = None
    left_hand_regime_any_of: list[str] | None = None
    left_hand_regime: str | None = None
    motion_regime: str | None = None


class QualitativeConstraint(BaseModel):
    """Single qualitative constraint entry."""

    model_config = ConfigDict(extra="allow")

    constraint_id: str
    production_condition: ProductionCondition
    instrument_scope: list[str] = Field(default_factory=list)
    descriptor: str
    tendency: str
    strength: str
    required_contextual_variables: list[str] = Field(default_factory=list)
    exceptions_or_limitations: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    curator_status: str | None = None
    numerical_prediction_allowed: bool = False
    numerical_status: str | None = None


class ConstraintMatch(BaseModel):
    """A constraint that matched the given production instruction."""

    constraint_id: str
    descriptor: str
    tendency: str
    strength: str
    required_contextual_variables: list[str] = Field(default_factory=list)
    exceptions_or_limitations: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    numerical_prediction_allowed: bool = False


class ConstraintEvaluationResult(BaseModel):
    """Structured qualitative evaluation — never contains EWSD numbers."""

    model_config = ConfigDict(extra="forbid")

    status: str
    instrument: str | None = None
    matches: list[ConstraintMatch] = Field(default_factory=list)
    tendencies: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
