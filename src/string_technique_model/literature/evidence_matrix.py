"""Sixteen-cell instrument–technique evidence matrix.

Grades change only from curator-validated extracts linked to usable bibliography.
Citation registration or PDF presence alone must not populate evidence fields.
Density activation is handled separately by the activation gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from string_technique_model.literature.activation import ActivationDecision
from string_technique_model.literature.domain import (
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
    DEFAULT_EVIDENCE_STATE,
    DEFAULT_LOCAL_ESTIMATION_STATUS,
    all_instrument_technique_cells,
)
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.source_registry import SourceRegistry

USABLE_BIBLIOGRAPHY_STATUSES = frozenset(
    {
        "verified_local_source",
        "pending_local_source",
        "bibliographically_verified_but_not_locally_available",
    }
)


def _matrix_eligible_extracts(
    extracts: list[EvidenceExtract],
    registry: SourceRegistry,
    *,
    mode: str,
) -> list[EvidenceExtract]:
    """Extracts that may alter matrix grades.

    - verified_local mode (legacy Phase-3 strict): verified_local_source only
    - curated_package mode: curator-validated extracts from usable bibliography
    """
    out: list[EvidenceExtract] = []
    for e in extracts:
        if str(e.curator_verification_status or "").lower() != "validated":
            continue
        src = registry.sources.get(e.source_id)
        if src is None:
            continue
        if src.evidence_status in {"excluded", "incomplete_reference"}:
            continue
        if mode == "curated_package":
            if src.evidence_status in USABLE_BIBLIOGRAPHY_STATUSES:
                out.append(e)
        else:
            if src.evidence_status == "verified_local_source":
                out.append(e)
    return out


def _cell_extracts(
    extracts: list[EvidenceExtract],
    instrument: str,
    technique: str,
) -> list[EvidenceExtract]:
    """Instrument-specific extracts plus generic (null-instrument) same-technique extracts."""
    return [
        e
        for e in extracts
        if e.technique == technique and (e.instrument == instrument or e.instrument is None)
    ]


def _cell_evidence_state(
    *,
    registry: SourceRegistry,
    instrument: str,
    technique: str,
    validated: list[EvidenceExtract],
) -> str:
    if not validated:
        related = [
            s
            for s in registry.list_sources()
            if technique in (s.techniques_covered or [])
            and instrument in _norm_instruments(s.instruments_covered)
            and s.evidence_status not in {"excluded", "incomplete_reference"}
        ]
        if not related:
            return DEFAULT_EVIDENCE_STATE
        if any(s.evidence_status == "verified_local_source" for s in related):
            return "source_verified_without_relevant_extract"
        return "source_registered_but_not_verified"

    if any(e.is_quantitative() for e in validated):
        return "relevant_quantitative_extract_available"
    return "relevant_qualitative_extract_only"


def _grade_cell(validated: list[EvidenceExtract]) -> tuple[str, str, str]:
    """Return evidence_grade, estimation_status, evidence_state."""
    direct_same = [
        e for e in validated if e.directness == "direct_same_instrument_same_technique"
    ]
    # Only count direct_same when extract instrument is not generic
    direct_same_specific = [e for e in direct_same if e.instrument is not None]
    generic = [e for e in validated if e.directness == "generic_bowed_string_physics"]
    cross = [e for e in validated if e.directness == "same_technique_other_instrument"]
    qualitative = [
        e
        for e in validated
        if e.directness == "qualitative_performance_description" or not e.is_quantitative()
    ]
    has_direct_quant = any(e.is_quantitative() for e in direct_same_specific)
    has_direct_density = any(
        (e.canonical_variable_name or "").lower() in {"density_value", "ewsd", "cdm"}
        or getattr(e, "density_mapping_status", None) == "direct_same_metric"
        for e in direct_same_specific
    )
    has_generic_or_cross = bool(cross or generic)
    only_generic = bool(generic) and not direct_same_specific and not cross
    has_qual_direct = any(not e.is_quantitative() for e in direct_same_specific)

    if has_direct_quant and has_direct_density:
        return "A", "directly_parameterisable", "parameterisable"
    if has_direct_quant:
        return "B", "parameterisable_with_metric_mapping", "relevant_quantitative_extract_available"
    if has_generic_or_cross and (has_qual_direct or cross or generic):
        # Instrument-specific qualitative + generic physics → C; generic-only → C/D band as C
        if only_generic and not has_qual_direct:
            return "C", "transferable_with_uncertainty", "relevant_qualitative_extract_only"
        if has_qual_direct and has_generic_or_cross:
            return "C", "transferable_with_uncertainty", "relevant_qualitative_extract_only"
        return "C", "transferable_with_uncertainty", (
            "relevant_quantitative_extract_available"
            if any(e.is_quantitative() for e in validated)
            else "relevant_qualitative_extract_only"
        )
    if has_qual_direct:
        # Direct qualitative mechanism without quantitative → C if mechanism-rich else D
        if len(direct_same_specific) >= 1:
            return "C", "qualitative_constraints_only", "relevant_qualitative_extract_only"
        return "D", "qualitative_constraints_only", "relevant_qualitative_extract_only"
    if qualitative:
        return "D", "qualitative_constraints_only", "relevant_qualitative_extract_only"
    return "NA", DEFAULT_LOCAL_ESTIMATION_STATUS, "not_estimable_from_current_local_evidence"


def build_evidence_matrix(
    registry: SourceRegistry,
    extracts: list[EvidenceExtract],
    *,
    evaluated_at_utc: str | None = None,
    parameter_decisions: list[ActivationDecision] | None = None,
    mechanisms: list[dict[str, Any]] | None = None,
    mode: str = "verified_local",
) -> list[dict[str, Any]]:
    """Build exactly sixteen primary rows.

    mode:
      - verified_local: only verified_local_source + validated extracts (legacy tests)
      - curated_package: curator-validated extracts from usable bibliography
    """
    evaluated = evaluated_at_utc or datetime.now(timezone.utc).isoformat()
    eligible = _matrix_eligible_extracts(extracts, registry, mode=mode)
    decisions = parameter_decisions or []
    mechanisms = mechanisms or []

    rows: list[dict[str, Any]] = []
    for instrument, technique in all_instrument_technique_cells():
        validated = _cell_extracts(eligible, instrument, technique)

        cell_mechs = [
            m
            for m in mechanisms
            if m.get("instrument") == instrument and m.get("technique") == technique
        ]
        supported = [
            m["mechanism_name"]
            for m in cell_mechs
            if m.get("supported") in {True, "true", "partially_supported"}
            or str(m.get("status") or "").startswith("support")
            or m.get("status") == "partially_supported"
        ]
        unsupported = [
            m["mechanism_name"]
            for m in cell_mechs
            if m.get("supported") in {False, "false"}
            or m.get("status") in {"unsupported", "contradicted"}
        ]

        active_count = 0
        inactive_count = 0
        _ = decisions

        if not validated:
            state = _cell_evidence_state(
                registry=registry,
                instrument=instrument,
                technique=technique,
                validated=[],
            )
            # Mechanism-only support (no extract for this instrument) → provisional D/C.
            if supported and mode == "curated_package":
                partial = any(
                    m.get("status") == "partially_supported"
                    for m in cell_mechs
                    if m["mechanism_name"] in supported
                )
                grade = "C" if partial else "D"
                rows.append(
                    {
                        "instrument": instrument,
                        "technique": technique,
                        "direct_experimental_evidence": False,
                        "direct_physical_model": True,
                        "direct_spectral_evidence": False,
                        "direct_level_evidence": False,
                        "direct_temporal_evidence": False,
                        "direct_dynamic_evidence": False,
                        "direct_register_evidence": False,
                        "direct_string_evidence": False,
                        "direct_density_metric_evidence": False,
                        "generic_physical_evidence": True,
                        "cross_instrument_evidence": True,
                        "qualitative_evidence": True,
                        "source_ids": [],
                        "evidence_ids": [],
                        "source_count": 0,
                        "evidence_extract_count": 0,
                        "quantitative_extract_count": 0,
                        "qualitative_extract_count": 0,
                        "direct_same_instrument_count": 0,
                        "cross_instrument_count": 0,
                        "active_parameter_count": 0,
                        "inactive_parameter_count": 0,
                        "supported_model_components": supported,
                        "unsupported_model_components": unsupported,
                        "supported_mechanisms": supported,
                        "unsupported_components": unsupported,
                        "transfer_required": True,
                        "possible_transfer_source_instruments": ["vln"],
                        "density_mapping_status": "qualitative_constraint_only",
                        "evidence_grade": grade,
                        "estimation_status": (
                            "transferable_with_uncertainty"
                            if grade == "C"
                            else "qualitative_constraints_only"
                        ),
                        "evidence_state": "relevant_qualitative_extract_only",
                        "evidence_last_evaluated_utc": evaluated,
                        "notes": (
                            "Provisional grade from curated physical-mechanism support "
                            "without instrument-specific extract."
                        ),
                    }
                )
                continue
            rows.append(
                _empty_cell(
                    instrument=instrument,
                    technique=technique,
                    state=state,
                    evaluated=evaluated,
                    supported=supported,
                    unsupported=unsupported
                    or ["all_model_components_pending_source_review"],
                )
            )
            continue

        grade, estimation, state = _grade_cell(validated)
        direct_same = [
            e
            for e in validated
            if e.directness == "direct_same_instrument_same_technique" and e.instrument is not None
        ]
        generic = [e for e in validated if e.directness == "generic_bowed_string_physics"]
        cross = [e for e in validated if e.directness == "same_technique_other_instrument"]
        qualitative = [e for e in validated if not e.is_quantitative()]
        quantitative = [e for e in validated if e.is_quantitative()]
        has_direct_density = any(
            (e.canonical_variable_name or "").lower() in {"density_value", "ewsd", "cdm"}
            or getattr(e, "density_mapping_status", None) == "direct_same_metric"
            for e in direct_same
        )

        mapping_statuses = [
            getattr(e, "density_mapping_status", None)
            for e in validated
            if getattr(e, "density_mapping_status", None)
        ]
        density_mapping_status = (
            "direct_same_metric"
            if has_direct_density
            else (mapping_statuses[0] if mapping_statuses else "insufficient_information")
        )

        source_ids = sorted({e.source_id for e in validated})
        evidence_ids = sorted(e.evidence_id or "" for e in validated if e.evidence_id)

        rows.append(
            {
                "instrument": instrument,
                "technique": technique,
                "direct_experimental_evidence": bool(direct_same),
                "direct_physical_model": bool(supported),
                "direct_spectral_evidence": False,
                "direct_level_evidence": any(
                    (e.canonical_variable_name or "")
                    in {
                        "dynamic_range",
                        "global_sound_power_change",
                        "harmonic_level_lower_bound",
                        "harmonic_radiation_offset_vs_violin",
                    }
                    for e in quantitative
                ),
                "direct_temporal_evidence": False,
                "direct_dynamic_evidence": any(
                    (e.canonical_variable_name or "") == "dynamic_range" for e in quantitative
                ),
                "direct_register_evidence": False,
                "direct_string_evidence": False,
                "direct_density_metric_evidence": bool(has_direct_density),
                "generic_physical_evidence": bool(generic),
                "cross_instrument_evidence": bool(cross),
                "qualitative_evidence": bool(qualitative) and not quantitative,
                "source_ids": source_ids,
                "evidence_ids": evidence_ids,
                "source_count": len(source_ids),
                "evidence_extract_count": len(validated),
                "quantitative_extract_count": len(quantitative),
                "qualitative_extract_count": len(qualitative),
                "direct_same_instrument_count": len(direct_same),
                "cross_instrument_count": len(cross),
                "active_parameter_count": active_count,
                "inactive_parameter_count": inactive_count,
                "supported_model_components": supported,
                "unsupported_model_components": unsupported,
                "supported_mechanisms": supported,
                "unsupported_components": unsupported,
                "transfer_required": grade == "C",
                "possible_transfer_source_instruments": (
                    ["vln"] if instrument != "vln" and grade == "C" else []
                ),
                "density_mapping_status": density_mapping_status,
                "evidence_grade": grade,
                "estimation_status": estimation,
                "evidence_state": state,
                "evidence_last_evaluated_utc": evaluated,
                "notes": (
                    "Cell updated from curator-validated package extracts."
                    if mode == "curated_package"
                    else "Cell updated from validated local extracts only."
                ),
            }
        )

    from string_technique_model.literature.domain import legacy_evidence_matrix_cell_count

    assert len(rows) == legacy_evidence_matrix_cell_count()
    assert {r["instrument"] for r in rows} <= ALLOWED_INSTRUMENTS
    assert {r["technique"] for r in rows} <= ALLOWED_TECHNIQUES
    _ = parameter_decisions
    return rows


def enrich_matrix_parameter_counts(
    rows: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    decisions: list[ActivationDecision],
) -> list[dict[str, Any]]:
    by_id = {d.parameter_id: d for d in decisions}
    for r in rows:
        active = 0
        inactive = 0
        for p in parameters:
            if p.get("instrument") != r["instrument"] or p.get("technique") != r["technique"]:
                continue
            d = by_id.get(str(p.get("parameter_id")))
            if d is None:
                continue
            if d.active:
                active += 1
            else:
                inactive += 1
        r["active_parameter_count"] = active
        r["inactive_parameter_count"] = inactive
    return rows


def _empty_cell(
    *,
    instrument: str,
    technique: str,
    state: str,
    evaluated: str,
    supported: list[str],
    unsupported: list[str],
) -> dict[str, Any]:
    return {
        "instrument": instrument,
        "technique": technique,
        "direct_experimental_evidence": False,
        "direct_physical_model": False,
        "direct_spectral_evidence": False,
        "direct_level_evidence": False,
        "direct_temporal_evidence": False,
        "direct_dynamic_evidence": False,
        "direct_register_evidence": False,
        "direct_string_evidence": False,
        "direct_density_metric_evidence": False,
        "generic_physical_evidence": False,
        "cross_instrument_evidence": False,
        "qualitative_evidence": False,
        "source_ids": [],
        "evidence_ids": [],
        "source_count": 0,
        "evidence_extract_count": 0,
        "quantitative_extract_count": 0,
        "qualitative_extract_count": 0,
        "direct_same_instrument_count": 0,
        "cross_instrument_count": 0,
        "active_parameter_count": 0,
        "inactive_parameter_count": 0,
        "supported_model_components": supported,
        "unsupported_model_components": unsupported,
        "supported_mechanisms": supported,
        "unsupported_components": unsupported,
        "transfer_required": False,
        "possible_transfer_source_instruments": [],
        "density_mapping_status": None,
        "evidence_grade": "NA",
        "estimation_status": DEFAULT_LOCAL_ESTIMATION_STATUS,
        "evidence_state": state if state != DEFAULT_EVIDENCE_STATE else DEFAULT_EVIDENCE_STATE,
        "evidence_last_evaluated_utc": evaluated,
        "notes": (
            "Structurally complete cell; evidentially empty pending verified "
            "local extracts. Local-corpus absence is not evidence of absence "
            "in the specialised literature."
        ),
    }


def _norm_instruments(labels: list[str] | None) -> set[str]:
    mapping = {
        "violin": "vln",
        "vln": "vln",
        "viola": "vla",
        "vla": "vla",
        "cello": "vlc",
        "violoncello": "vlc",
        "vlc": "vlc",
        "double_bass": "cb",
        "double bass": "cb",
        "contrabass": "cb",
        "cb": "cb",
    }
    out: set[str] = set()
    for label in labels or []:
        key = str(label).strip().lower()
        if key in mapping:
            out.add(mapping[key])
    return out


def matrix_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Instrument–technique evidence matrix",
        "",
        "This is an **auditable evidence framework**, not a completed literature review.",
        "Grades change only after curator-validated extracts exist.",
        "",
        "| instrument | technique | grade | estimation_status | evidence_state |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['instrument']} | {r['technique']} | {r['evidence_grade']} | "
            f"{r['estimation_status']} | {r.get('evidence_state')} |"
        )
    lines.append("")
    return "\n".join(lines)


def serialize_matrix_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten list fields for CSV export."""
    out = dict(row)
    for key in (
        "source_ids",
        "evidence_ids",
        "supported_model_components",
        "unsupported_model_components",
        "supported_mechanisms",
        "unsupported_components",
        "possible_transfer_source_instruments",
    ):
        val = out.get(key)
        if isinstance(val, list):
            out[key] = ";".join(str(x) for x in val)
    return out
