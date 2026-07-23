"""Strict instrument–technique domain for the literature evidence layer.

The scientifically authoritative ontology lives in
``configs/technique_ontology.yaml``. The frozensets below retain the legacy
specialised-technique labels used by the explicitly labeled 4×4 evidence matrix.
"""

from __future__ import annotations

ALLOWED_INSTRUMENTS: frozenset[str] = frozenset({"vln", "vla", "vlc", "cb"})
# Legacy specialised technique labels (compatibility). Full ontology is broader.
ALLOWED_TECHNIQUES: frozenset[str] = frozenset(
    {
        "artificial_harmonic",
        "sul_ponticello",
        "sul_tasto",
        "con_sordino",
    }
)
LEGACY_EVIDENCE_MATRIX_LABEL = "legacy_four_by_four_specialised_techniques"

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {
        "verified_local_source",
        "bibliographically_verified_but_not_locally_available",
        "pending_local_source",
        "incomplete_reference",
        "excluded",
        "pending_verification",
    }
)

# Cell-level verification state (local corpus), not a claim about global literature.
EVIDENCE_STATES: frozenset[str] = frozenset(
    {
        "no_local_source_available",
        "source_registered_but_not_verified",
        "source_verified_without_relevant_extract",
        "relevant_qualitative_extract_only",
        "relevant_quantitative_extract_available",
        "parameterisable",
        "not_estimable_from_current_local_evidence",
    }
)

DIRECTNESS_VALUES: frozenset[str] = frozenset(
    {
        "direct_same_instrument_same_technique",
        "direct_same_instrument_related_variable",
        "generic_bowed_string_physics",
        "same_technique_other_instrument",
        "same_instrument_related_technique",
        "qualitative_performance_description",
        "unsupported_for_current_model",
    }
)

PARAMETER_STATUSES: frozenset[str] = frozenset(
    {
        "directly_extracted",
        "derived_from_reported_statistics",
        "interval_constrained",
        "qualitative_only",
        "transfer_candidate",
        "unresolved",
        "prohibited",
        "placeholder_user_input",
    }
)

ACTIVE_PARAMETER_STATUSES: frozenset[str] = frozenset(
    {
        "directly_extracted",
        "derived_from_reported_statistics",
        "interval_constrained",
    }
)

ESTIMATION_STATUSES: frozenset[str] = frozenset(
    {
        "directly_parameterisable",
        "parameterisable_with_metric_mapping",
        "transferable_with_uncertainty",
        "qualitative_constraints_only",
        "not_estimable_from_current_local_evidence",
        # Legacy alias retained only for estimate-module compatibility checks.
        "not_estimable_from_current_evidence",
    }
)

EXTRACT_VERIFICATION_STATUSES: frozenset[str] = frozenset(
    {
        "pending",
        "unverified",
        "validated",
        "rejected",
    }
)

EVIDENCE_GRADES: frozenset[str] = frozenset({"A", "B", "C", "D", "NA"})

DEFAULT_LOCAL_ESTIMATION_STATUS = "not_estimable_from_current_local_evidence"
DEFAULT_EVIDENCE_STATE = "no_local_source_available"


def all_instrument_technique_cells() -> list[tuple[str, str]]:
    """Legacy 4×4 specialised-technique cells (compatibility view)."""
    cells: list[tuple[str, str]] = []
    for instrument in sorted(ALLOWED_INSTRUMENTS):
        for technique in sorted(ALLOWED_TECHNIQUES):
            cells.append((instrument, technique))
    return cells


def legacy_evidence_matrix_cell_count() -> int:
    from string_technique_model.ontology import legacy_cell_count

    return legacy_cell_count()
