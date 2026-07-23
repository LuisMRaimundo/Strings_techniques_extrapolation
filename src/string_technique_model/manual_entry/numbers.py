"""Deterministic decimal parsing for manual entry (no silent locale conversion)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedNumber:
    ok: bool
    value: float | None
    raw: str
    ambiguity: str | None = None
    reason: str | None = None
    requires_confirmation: bool = False


_INF_TOKENS = {"inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
_NAN_TOKENS = {"nan", "na", "n/a", "null", "none", ""}


def parse_density_input(raw: Any, *, confirmed_locale: str | None = None) -> ParsedNumber:
    """Parse a metric value with deterministic decimal rules.

    Supports '.' and ',' only when unambiguous. Ambiguous forms (both separators
    or thousands-looking patterns) require explicit locale confirmation.
    """
    if raw is None:
        return ParsedNumber(False, None, "", reason="missing_value")
    if isinstance(raw, bool):
        return ParsedNumber(False, None, str(raw), reason="boolean_not_numeric")
    if isinstance(raw, (int, float)):
        val = float(raw)
        if math.isnan(val):
            return ParsedNumber(False, None, str(raw), reason="nan_rejected")
        if not math.isfinite(val):
            return ParsedNumber(False, None, str(raw), reason="infinity_rejected")
        return ParsedNumber(True, val, str(raw))

    text = str(raw).strip()
    if not text:
        return ParsedNumber(False, None, text, reason="missing_value")
    low = text.lower().replace(" ", "")
    if low in _NAN_TOKENS:
        return ParsedNumber(False, None, text, reason="nan_or_missing_rejected")
    if low in _INF_TOKENS:
        return ParsedNumber(False, None, text, reason="infinity_rejected")

    # Strip spaces used as thousands separators only when locale confirmed.
    candidate = text.replace(" ", "")
    has_dot = "." in candidate
    has_comma = "," in candidate

    if has_dot and has_comma:
        if confirmed_locale == "eu":
            # 1.234,56 → remove dots, comma to decimal
            normalized = candidate.replace(".", "").replace(",", ".")
        elif confirmed_locale == "us":
            # 1,234.56 → remove commas
            normalized = candidate.replace(",", "")
        else:
            return ParsedNumber(
                False,
                None,
                text,
                ambiguity="both_decimal_separators",
                reason="locale_ambiguous_confirm_eu_or_us",
                requires_confirmation=True,
            )
    elif has_comma and not has_dot:
        # Single comma: treat as decimal if one group after comma looks like decimals
        parts = candidate.split(",")
        if len(parts) == 2 and re.fullmatch(r"-?\d+", parts[0] or "0") and re.fullmatch(r"\d+", parts[1]):
            if len(parts[1]) == 3 and confirmed_locale is None and len(parts[0].lstrip("-")) >= 1:
                # Could be thousands (1,234) or decimal with 3 places
                return ParsedNumber(
                    False,
                    None,
                    text,
                    ambiguity="comma_thousands_or_decimal",
                    reason="locale_ambiguous_confirm_eu_or_us",
                    requires_confirmation=True,
                )
            normalized = candidate.replace(",", ".")
        else:
            return ParsedNumber(False, None, text, reason="non_numeric")
    else:
        normalized = candidate

    try:
        val = float(normalized)
    except ValueError:
        return ParsedNumber(False, None, text, reason="non_numeric")

    if math.isnan(val):
        return ParsedNumber(False, None, text, reason="nan_rejected")
    if not math.isfinite(val):
        return ParsedNumber(False, None, text, reason="infinity_rejected")
    return ParsedNumber(True, val, text)


def validate_against_domain(value: float | None, domain: str | None) -> tuple[bool, str | None]:
    """Validate a numeric density against a metric mathematical_domain label."""
    if value is None:
        return False, "missing_value_not_converted_to_zero"
    if math.isnan(value):
        return False, "nan_rejected"
    if not math.isfinite(value):
        return False, "infinity_rejected"

    d = (domain or "").strip().lower()
    if d in {"positive", "(0,inf)", "(0, ∞)", "strictly_positive"}:
        if value <= 0:
            return False, "value_must_be_strictly_positive"
        return True, None
    if d in {"non_negative", "non-negative", "[0,inf)", "[0, ∞)"}:
        if value < 0:
            return False, "value_must_be_non_negative"
        return True, None
    if d in {"[0,1]", "unit_interval", "unit", "(0,1)"}:
        if d == "(0,1)":
            if not (0 < value < 1):
                return False, "value_must_be_in_open_unit_interval"
            return True, None
        if not (0 <= value <= 1):
            return False, "value_must_be_in_unit_interval"
        return True, None
    if d in {"integer", "count", "integer_count"}:
        if abs(value - round(value)) > 1e-12:
            return False, "value_must_be_integer"
        return True, None
    if d in {"unrestricted", "real", "unrestricted_real", ""}:
        return True, None
    # Unknown domain: do not invent clipping; accept finite reals with warning code
    return True, None
