"""Conflicting-evidence register."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.stable_seed import stable_hex


def load_conflicts(path: Path | str | None = None) -> list[dict[str, Any]]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_conflicts.yaml")
    data = load_yaml(path)
    rows = list(data.get("conflicts") or [])
    for row in rows:
        if not row.get("conflict_id"):
            row["conflict_id"] = f"CONFLICT_{stable_hex(row.get('instrument'), row.get('technique'), row.get('acoustic_variable'), n_chars=10)}"
    return rows


def conflict_rows(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in conflicts:
        out.append(
            {
                "conflict_id": c.get("conflict_id"),
                "instrument": c.get("instrument"),
                "technique": c.get("technique"),
                "acoustic_variable": c.get("acoustic_variable"),
                "source_ids": ";".join(c.get("source_ids") or []),
                "evidence_ids": ";".join(c.get("evidence_ids") or []),
                "nature_of_conflict": c.get("nature_of_conflict"),
                "possible_explanations": c.get("possible_explanations"),
                "recording_condition_differences": c.get("recording_condition_differences"),
                "register_differences": c.get("register_differences"),
                "dynamic_differences": c.get("dynamic_differences"),
                "instrument_differences": c.get("instrument_differences"),
                "proposed_resolution_status": c.get("proposed_resolution_status") or "unresolved",
            }
        )
    return out
