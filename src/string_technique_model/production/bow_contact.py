"""Bow contact beta computation and validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from string_technique_model.ontology.loader import load_ontology
from string_technique_model.production.models import BowContactInstruction


class BowContactValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    relative_bow_bridge_distance_beta: float | None = None
    errors: list[str] = []
    warnings: list[str] = []


_CONTINUUM_CATEGORIES = frozenset(
    {
        "molto_sul_tasto",
        "sul_tasto",
        "poco_sul_tasto",
        "ordinario",
        "poco_sul_ponticello",
        "sul_ponticello",
        "molto_sul_ponticello",
    }
)
_OUTSIDE_CONTINUUM_REGIONS = frozenset(
    {"directly_on_bridge", "afterlength_behind_bridge"}
)


def compute_beta(bow_bridge_distance_m: float, speaking_length_m: float) -> float:
    """Compute relative bow-bridge distance β = bow_bridge_distance_m / speaking_length_m."""
    if speaking_length_m <= 0:
        raise ValueError("speaking_length_m must be positive")
    if bow_bridge_distance_m < 0:
        raise ValueError("bow_bridge_distance_m must be non-negative")
    return bow_bridge_distance_m / speaking_length_m


def _apply_deprecated_bow_ratio(instruction: BowContactInstruction) -> tuple[BowContactInstruction, list[str]]:
    warnings: list[str] = []
    if instruction.relative_bow_bridge_distance_beta is not None:
        return instruction, warnings
    if instruction.bow_position_ratio_deprecated is None:
        return instruction, warnings

    updated = instruction.model_copy(
        update={
            "relative_bow_bridge_distance_beta": instruction.bow_position_ratio_deprecated,
        }
    )
    warnings.append(
        "copied bow_position_ratio_deprecated to relative_bow_bridge_distance_beta; "
        "legacy field semantics were ambiguous (numerator/denominator undocumented)"
    )
    return updated, warnings


def validate_bow_contact(instruction: BowContactInstruction) -> BowContactValidationResult:
    """
    Validate bow contact instruction.

    Never derives force/velocity from category or timbre from beta alone.
    """
    errors: list[str] = []
    warnings: list[str] = []

    instruction, deprec_warnings = _apply_deprecated_bow_ratio(instruction)
    warnings.extend(deprec_warnings)

    ontology = load_ontology()
    tolerance = ontology.contradiction_tolerance

    beta = instruction.relative_bow_bridge_distance_beta
    bow_m = instruction.bow_bridge_distance_m
    speaking_m = instruction.speaking_length_m

    computed_beta: float | None = None
    if bow_m is not None and speaking_m is not None:
        try:
            computed_beta = compute_beta(bow_m, speaking_m)
        except ValueError as exc:
            errors.append(str(exc))

        if beta is not None and computed_beta is not None:
            if abs(beta - computed_beta) > tolerance:
                errors.append(
                    f"beta contradiction: relative_bow_bridge_distance_beta={beta} "
                    f"vs computed {computed_beta} from lengths (tolerance={tolerance})"
                )

    excitation = instruction.excitation_region
    category = instruction.category

    if excitation in _OUTSIDE_CONTINUUM_REGIONS:
        if category in _CONTINUUM_CATEGORIES:
            warnings.append(
                f"excitation_region '{excitation}' is outside the tasto–ponticello continuum; "
                f"bow category '{category}' should not be treated as sul_ponticello/sul_tasto "
                "without explicit justification"
            )

    if excitation == "speaking_string" and beta is not None and not (0 < beta < 1):
        warnings.append(
            f"relative_bow_bridge_distance_beta={beta} outside expected domain (0, 1) "
            "for speaking_string excitation"
        )

    resolved_beta = beta if beta is not None else computed_beta
    ok = len(errors) == 0
    return BowContactValidationResult(
        ok=ok,
        relative_bow_bridge_distance_beta=resolved_beta,
        errors=errors,
        warnings=warnings,
    )
