"""Harmonic interval/order validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from string_technique_model.ontology.loader import interval_to_order, normalize_touched_interval


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    inferred_order: int | None = None
    errors: list[str] = []
    warnings: list[str] = []


_NATURAL_REGIMES = frozenset({"natural_harmonic", "natural_harmonic_glissando"})
_ARTIFICIAL_REGIMES = frozenset({"artificial_harmonic", "artificial_harmonic_glissando"})
_HALF_REGIMES = frozenset({"half_harmonic"})
_MULTIPHONIC_REGIMES = frozenset({"multiphonic"})


def _check_regime_vs_harmonic_type(
    left_hand_regime: str | None,
    harmonic_type: str | None,
) -> list[str]:
    errors: list[str] = []
    if left_hand_regime is None or harmonic_type is None:
        return errors

    if harmonic_type == "natural" and left_hand_regime not in _NATURAL_REGIMES:
        errors.append(
            f"harmonic_type 'natural' is inconsistent with left_hand_regime '{left_hand_regime}'"
        )
    elif harmonic_type == "artificial" and left_hand_regime not in _ARTIFICIAL_REGIMES:
        errors.append(
            f"harmonic_type 'artificial' is inconsistent with left_hand_regime '{left_hand_regime}'"
        )
    elif harmonic_type == "half" and left_hand_regime not in _HALF_REGIMES:
        errors.append(
            f"harmonic_type 'half' is inconsistent with left_hand_regime '{left_hand_regime}'"
        )
    elif harmonic_type == "multiphonic" and left_hand_regime not in _MULTIPHONIC_REGIMES:
        errors.append(
            f"harmonic_type 'multiphonic' is inconsistent with left_hand_regime '{left_hand_regime}'"
        )
    return errors


def validate_harmonic_interval_order(
    touched_interval: str | None,
    harmonic_order: int | None,
    *,
    allow_inference: bool = False,
    left_hand_regime: str | None = None,
    harmonic_type: str | None = None,
) -> ValidationResult:
    """
    Validate consistency between touched interval and harmonic order.

    Relations (from ontology): P4→4, M3→5, m3→6, P5→3.
    """
    errors: list[str] = []
    warnings: list[str] = []
    inferred_order: int | None = None

    errors.extend(_check_regime_vs_harmonic_type(left_hand_regime, harmonic_type))

    canonical = normalize_touched_interval(touched_interval) if touched_interval else None
    if touched_interval and canonical is None:
        errors.append(f"unknown touched_interval alias: {touched_interval!r}")

    expected_order = interval_to_order(touched_interval) if touched_interval else None

    if harmonic_order is not None and expected_order is not None:
        if harmonic_order != expected_order:
            errors.append(
                f"inconsistent interval/order: {canonical or touched_interval} "
                f"implies order {expected_order}, got {harmonic_order}"
            )
    elif harmonic_order is None and expected_order is not None:
        if allow_inference:
            inferred_order = expected_order
            warnings.append(
                f"inferred harmonic_order {expected_order} from interval {canonical}"
            )
        else:
            warnings.append(
                f"interval {canonical} implies order {expected_order}; "
                "inference disabled (allow_inference=False)"
            )
    elif harmonic_order is not None and expected_order is None and touched_interval:
        warnings.append(
            f"harmonic_order {harmonic_order} supplied without a recognized interval"
        )

    ok = len(errors) == 0
    return ValidationResult(
        ok=ok,
        inferred_order=inferred_order,
        errors=errors,
        warnings=warnings,
    )
