"""Production instruction models and migration helpers."""

from __future__ import annotations

from string_technique_model.production.bow_contact import (
    BowContactValidationResult,
    compute_beta,
    validate_bow_contact,
)
from string_technique_model.production.harmonics import ValidationResult, validate_harmonic_interval_order
from string_technique_model.production.migration import migrate_legacy_technique_record, production_to_tabular
from string_technique_model.production.models import (
    BowContactCategory,
    BowContactInstruction,
    BowingConditions,
    DoubleBassPitchConvention,
    ExcitationRegion,
    HarmonicInstruction,
    HarmonicType,
    LeftHandRegime,
    MotionRegime,
    MultiphonicInstruction,
    MuteCategory,
    MuteInstruction,
    MuteState,
    NotationRepresents,
    PerformanceContext,
    ProductionInstruction,
    TimbreExecutionTarget,
)
from string_technique_model.production.multiphonics import assert_distinct_from_harmonics
from string_technique_model.production.mute import normalize_mute_mass

__all__ = [
    "BowContactCategory",
    "BowContactInstruction",
    "BowContactValidationResult",
    "BowingConditions",
    "DoubleBassPitchConvention",
    "ExcitationRegion",
    "HarmonicInstruction",
    "HarmonicType",
    "LeftHandRegime",
    "MotionRegime",
    "MultiphonicInstruction",
    "MuteCategory",
    "MuteInstruction",
    "MuteState",
    "NotationRepresents",
    "PerformanceContext",
    "ProductionInstruction",
    "TimbreExecutionTarget",
    "ValidationResult",
    "assert_distinct_from_harmonics",
    "compute_beta",
    "migrate_legacy_technique_record",
    "normalize_mute_mass",
    "production_to_tabular",
    "validate_bow_contact",
    "validate_harmonic_interval_order",
]
