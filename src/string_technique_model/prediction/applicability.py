"""Applicability resolution beyond instrument + technique.

Re-exports the unified applicability resolver with prediction-context adapter.
"""

from __future__ import annotations

from typing import Any

from string_technique_model.applicability import (
    APPLICABILITY_FIELDS,
    ApplicabilityQuery,
    ApplicabilityResult,
    ApplicabilityStatus,
    applicability_present,
    from_literature_query,
    from_prediction_context,
)
from string_technique_model.applicability import (
    resolve_applicability as _resolve_applicability,
)

__all__ = [
    "APPLICABILITY_FIELDS",
    "ApplicabilityQuery",
    "ApplicabilityResult",
    "ApplicabilityStatus",
    "applicability_present",
    "from_literature_query",
    "from_prediction_context",
    "resolve_applicability",
]


def resolve_applicability(
    param: dict[str, Any],
    context: dict[str, Any] | ApplicabilityQuery,
    *,
    allow_wider_without_metadata: bool = False,
) -> ApplicabilityResult:
    """Resolve applicability using the unified resolver."""
    query = context if isinstance(context, ApplicabilityQuery) else from_prediction_context(context)
    return _resolve_applicability(
        param,
        query,
        allow_wider_without_metadata=allow_wider_without_metadata,
    )
