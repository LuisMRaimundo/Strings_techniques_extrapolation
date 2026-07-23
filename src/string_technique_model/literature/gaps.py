"""Literature search gaps for unsupported cells and parameters."""

from __future__ import annotations

from typing import Any

from string_technique_model.literature.domain import all_instrument_technique_cells

SEARCH_TERMS = {
    "artificial_harmonic": [
        "{instrument_name} artificial harmonics spectrum",
        "{instrument_name} artificial harmonic acoustics",
    ],
    "sul_ponticello": [
        "{instrument_name} sul ponticello spectral analysis",
        "bowed string bow position spectral envelope",
    ],
    "sul_tasto": [
        "{instrument_name} sul tasto spectrum",
        "{instrument_name} sul tasto vs flautando",
    ],
    "con_sordino": [
        "{instrument_name} mute bridge mobility",
        "{instrument_name} orchestral mute attenuation",
        "{instrument_name} con sordino acoustics",
    ],
}

INSTRUMENT_NAMES = {
    "vln": "violin",
    "vla": "viola",
    "vlc": "cello",
    "cb": "double bass",
}


def build_gap_rows(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for row in matrix_rows:
        if row.get("estimation_status") not in {
            "not_estimable_from_current_local_evidence",
            "not_estimable_from_current_evidence",
            "qualitative_constraints_only",
        }:
            if row.get("evidence_grade") not in {"NA", "D"}:
                continue
        instrument = row["instrument"]
        technique = row["technique"]
        name = INSTRUMENT_NAMES[instrument]
        terms = [
            t.format(instrument_name=name) for t in SEARCH_TERMS.get(technique, [])
        ]
        gaps.append(
            {
                "instrument": instrument,
                "technique": technique,
                "missing_model_component": "technique_to_ordinary_density_effect",
                "missing_acoustic_variable": "EWSD_or_mappable_spectrum",
                "required_source_type": "peer-reviewed same-instrument technique measurement",
                "recommended_search_terms": "; ".join(terms),
                "current_best_indirect_source": row.get("source_ids") or None,
                "scientific_consequence": (
                    "No defensible numerical special-technique density prediction "
                    "for this cell from the current literature layer."
                ),
                "blocks_prediction": True,
                "priority": "critical",
            }
        )
    # Ensure coverage for all 16 if matrix somehow omitted
    present = {(g["instrument"], g["technique"]) for g in gaps}
    for instrument, technique in all_instrument_technique_cells():
        if (instrument, technique) not in present:
            name = INSTRUMENT_NAMES[instrument]
            terms = [t.format(instrument_name=name) for t in SEARCH_TERMS.get(technique, [])]
            gaps.append(
                {
                    "instrument": instrument,
                    "technique": technique,
                    "missing_model_component": "technique_to_ordinary_density_effect",
                    "missing_acoustic_variable": "EWSD_or_mappable_spectrum",
                    "required_source_type": "peer-reviewed same-instrument technique measurement",
                    "recommended_search_terms": "; ".join(terms),
                    "current_best_indirect_source": None,
                    "scientific_consequence": "Cell not estimable.",
                    "blocks_prediction": True,
                    "priority": "critical",
                }
            )
    return gaps


def gaps_markdown(gaps: list[dict[str, Any]], *, search_completed: bool) -> str:
    lines = [
        "# Literature gaps",
        "",
        f"- gap rows: {len(gaps)}",
        f"- literature search completed: {search_completed}",
        "",
        "No claim is made that an exhaustive database search was performed "
        "unless `corpus_search_completed` is true.",
        "",
        "| instrument | technique | priority | blocks_prediction | search terms |",
        "|---|---|---|---|---|",
    ]
    for g in gaps:
        lines.append(
            f"| {g['instrument']} | {g['technique']} | {g['priority']} | "
            f"{g['blocks_prediction']} | {g['recommended_search_terms']} |"
        )
    lines.append("")
    return "\n".join(lines)
