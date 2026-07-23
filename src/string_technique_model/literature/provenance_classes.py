"""Distinct provenance classes — never conflate user assumptions with literature."""

from __future__ import annotations

from typing import Literal

ProvenanceClass = Literal[
    "primary_experimental_evidence",
    "secondary_synthesis",
    "performance_practice_source",
    "historical_source",
    "user_assumption",
    "derived_measurement",
    "transferred_parameter",
    "unresolved",
    "rejected_source",
]

PROVENANCE_CLASSES: frozenset[str] = frozenset(
    {
        "primary_experimental_evidence",
        "secondary_synthesis",
        "performance_practice_source",
        "historical_source",
        "user_assumption",
        "derived_measurement",
        "transferred_parameter",
        "unresolved",
        "rejected_source",
    }
)

VALIDATION_STATUSES: frozenset[str] = frozenset(
    {
        "verified_identity",
        "partial_identity_match",
        "duplicate_file",
        "rejected_file_identity_mismatch",
        "insufficient_metadata",
    }
)


def is_user_assumption(provenance: str | None) -> bool:
    return provenance == "user_assumption"


def may_label_literature_validated(provenance: str | None) -> bool:
    """User assumptions and rejected sources never count as literature-validated."""
    return provenance in {
        "primary_experimental_evidence",
        "secondary_synthesis",
        "performance_practice_source",
        "historical_source",
        "derived_measurement",
        "transferred_parameter",
    }
