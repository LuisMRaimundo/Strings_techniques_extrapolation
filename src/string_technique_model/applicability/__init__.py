"""Unified applicability resolution."""

from string_technique_model.applicability.resolver import (
    APPLICABILITY_FIELDS,
    ApplicabilityQuery,
    ApplicabilityResult,
    ApplicabilityStatus,
    applicability_present,
    from_literature_query,
    from_prediction_context,
    resolve_applicability,
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
