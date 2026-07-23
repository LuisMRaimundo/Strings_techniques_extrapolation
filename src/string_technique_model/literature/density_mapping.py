"""Literature acoustic-variable → project density metric mappings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

FORBIDDEN_AUTO_EQUIVALENCES = {
    "sound_pressure_level",
    "sound_power_level",
    "spectral_centroid",
    "brightness",
    "spectral_slope",
    "number_of_harmonics",
}


def load_density_mappings(path: Path | str | None = None) -> list[dict[str, Any]]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_density_mappings.yaml")
    data = load_yaml(path)
    return list(data.get("mappings") or [])


def mapping_matrix_rows(mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in mappings:
        rows.append(
            {
                "source_variable": item.get("source_variable"),
                "canonical_variable_name": item.get("canonical_variable_name"),
                "mapping_status": item.get("mapping_status"),
                "notes": item.get("notes"),
                "auto_equivalent_to_density": False,
            }
        )
    return rows


def mapping_markdown(mappings: list[dict[str, Any]]) -> str:
    lines = [
        "# Literature → density metric mapping",
        "",
        "Project metric: EWSD acoustic-balanced scalar (`configs/density_metric.yaml`).",
        "",
        "Sound level, centroid, brightness, spectral slope, and harmonic count are "
        "**not** automatically treated as density.",
        "",
        "| source_variable | mapping_status | notes |",
        "|---|---|---|",
    ]
    for item in mappings:
        notes = str(item.get("notes") or "").replace("\n", " ").strip()
        lines.append(
            f"| {item.get('source_variable')} | {item.get('mapping_status')} | {notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def forbids_auto_density_equivalence(source_variable: str) -> bool:
    return str(source_variable).lower() in FORBIDDEN_AUTO_EQUIVALENCES
