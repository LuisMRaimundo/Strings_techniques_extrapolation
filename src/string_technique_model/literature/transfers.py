"""Cross-instrument transfer candidates (inactive in Phase 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

ALLOWED_TRANSFER_STATUS = {
    "physically_justified_candidate",
    "requires_additional_parameters",
    "weakly_supported",
    "rejected",
    "unresolved",
}


def load_transfer_candidates(path: Path | str | None = None) -> list[dict[str, Any]]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_transfers.yaml")
    data = load_yaml(path)
    rows = list(data.get("transfer_candidates") or [])
    for row in rows:
        status = row.get("transfer_status")
        if status not in ALLOWED_TRANSFER_STATUS:
            raise ValueError(f"Invalid transfer_status: {status}")
        # Identity / arbitrary constant without justification → must be rejected
        eq = str(row.get("proposed_equation") or "")
        if "violin_parameter" in eq.replace(" ", "") and "*" not in eq:
            if "arbitrary" in eq or eq.strip() in {
                "target_parameter = violin_parameter",
                "target_parameter=violin_parameter",
            }:
                if status != "rejected":
                    raise ValueError(
                        f"Identity violin transfer must be rejected: {row.get('target_instrument')}"
                    )
    return rows


def transfer_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in candidates:
        out.append(
            {
                "target_instrument": c.get("target_instrument"),
                "target_technique": c.get("target_technique"),
                "target_parameter": c.get("target_parameter"),
                "source_instrument": c.get("source_instrument"),
                "source_parameter": c.get("source_parameter"),
                "physical_justification": c.get("physical_justification"),
                "proposed_scaling_variables": ";".join(c.get("proposed_scaling_variables") or []),
                "proposed_equation": c.get("proposed_equation"),
                "evidence_ids": ";".join(c.get("evidence_ids") or []),
                "additional_uncertainty": c.get("additional_uncertainty"),
                "transfer_status": c.get("transfer_status"),
                "rejection_reason": c.get("rejection_reason"),
                "activated": False,
            }
        )
    return out
