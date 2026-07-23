"""Literature inventory tables and reports."""

from __future__ import annotations

from typing import Any

from string_technique_model.literature.source_registry import SourceRegistry


def build_inventory_rows(registry: SourceRegistry) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in registry.list_sources():
        rows.append(
            {
                "source_id": s.source_id,
                "full_bibliographic_reference": s.full_citation,
                "source_type": s.source_type,
                "local_path": s.local_file_path,
                "instruments_studied": ";".join(s.instruments_covered or []),
                "techniques_studied": ";".join(s.techniques_covered or []),
                "distinction_natural_vs_artificial_harmonics": None,
                "distinction_sul_tasto_vs_flautando": None,
                "mute_type_or_mass": None,
                "acoustic_variables_measured": ";".join(s.acoustic_variables_covered or []),
                "experimental_design": None,
                "number_of_performers": None,
                "number_of_instruments": None,
                "notes_or_registers": None,
                "dynamics": None,
                "strings": None,
                "bow_positions": None,
                "microphone_conditions": None,
                "room_conditions": None,
                "analysis_method": None,
                "reported_uncertainty": None,
                "relevance_to_project": s.verification_notes,
                "limitations": (
                    "Methodological fields null unless explicitly curated; "
                    f"evidence_status={s.evidence_status}"
                ),
                "evidence_status": s.evidence_status,
                "peer_reviewed": s.peer_reviewed,
                "DOI": s.DOI,
                "year": s.year,
            }
        )
    return rows


def inventory_markdown(rows: list[dict[str, Any]], *, corpus_search_completed: bool) -> str:
    lines = [
        "# Literature inventory",
        "",
        f"- sources inventoried: {len(rows)}",
        f"- corpus search completed: {corpus_search_completed}",
        "",
        "Methodological fields that were not curated remain **null** "
        "(not inferred).",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['source_id']}")
        lines.append("")
        lines.append(f"- citation: {row['full_bibliographic_reference']}")
        lines.append(f"- type: {row['source_type']}")
        lines.append(f"- local path: {row['local_path']}")
        lines.append(f"- evidence_status: {row['evidence_status']}")
        lines.append(f"- instruments: {row['instruments_studied'] or 'null'}")
        lines.append(f"- techniques: {row['techniques_studied'] or 'null'}")
        lines.append(f"- acoustic variables: {row['acoustic_variables_measured'] or 'null'}")
        lines.append(f"- limitations: {row['limitations']}")
        lines.append("")
    return "\n".join(lines)
