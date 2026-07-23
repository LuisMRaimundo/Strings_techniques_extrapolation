"""Stable SHA-256 duplicate detection for manual entry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

DUPLICATE_CLASSES = frozenset(
    {
        "exact_duplicate",
        "probable_duplicate",
        "legitimate_replicate",
        "conflicting_observation",
        "not_duplicate",
    }
)


def fingerprint_row(row: dict[str, Any], *, fields: list[str] | None = None) -> str:
    keys = fields or [
        "collection_id",
        "instrument",
        "technique",
        "pitch_name_sounding",
        "pitch_midi_sounding",
        "dynamic",
        "density_value",
        "metric_definition_id",
        "replicate_id",
        "take_id",
    ]
    payload = {k: _norm(row.get(k)) for k in keys}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value).strip()


@dataclass
class DuplicateFinding:
    classification: str
    fingerprint: str
    row_indices: list[int]
    reason: str
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "fingerprint": self.fingerprint,
            "row_indices": self.row_indices,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
        }


class DuplicateDetectionService:
    def classify_rows(self, rows: list[dict[str, Any]]) -> list[DuplicateFinding]:
        by_fp: dict[str, list[int]] = {}
        for i, row in enumerate(rows):
            fp = fingerprint_row(row)
            by_fp.setdefault(fp, []).append(i)

        findings: list[DuplicateFinding] = []
        # exact pasted duplicates
        for fp, idxs in by_fp.items():
            if len(idxs) < 2:
                continue
            reps = [rows[i].get("replicate_id") for i in idxs]
            takes = [rows[i].get("take_id") for i in idxs]
            if any(r not in (None, "", "nan") for r in reps) or any(
                t not in (None, "", "nan") for t in takes
            ):
                findings.append(
                    DuplicateFinding(
                        "legitimate_replicate",
                        fp,
                        idxs,
                        "Same scientific key with distinct replicate_id/take_id",
                        requires_confirmation=False,
                    )
                )
            else:
                findings.append(
                    DuplicateFinding(
                        "exact_duplicate",
                        fp,
                        idxs,
                        "Identical rows (same fingerprint)",
                        requires_confirmation=True,
                    )
                )

        # probable / conflicting: same key different density
        key_groups: dict[str, list[int]] = {}
        for i, row in enumerate(rows):
            key = fingerprint_row(
                row,
                fields=[
                    "collection_id",
                    "instrument",
                    "technique",
                    "pitch_name_sounding",
                    "dynamic",
                    "metric_definition_id",
                ],
            )
            key_groups.setdefault(key, []).append(i)
        for key, idxs in key_groups.items():
            if len(idxs) < 2:
                continue
            values = {_norm(rows[i].get("density_value")) for i in idxs}
            reps = [rows[i].get("replicate_id") for i in idxs]
            if len(values) > 1:
                if any(r not in (None, "", "nan") for r in reps):
                    findings.append(
                        DuplicateFinding(
                            "legitimate_replicate",
                            key,
                            idxs,
                            "Repeated measurements with distinct replicate_id",
                            requires_confirmation=False,
                        )
                    )
                else:
                    findings.append(
                        DuplicateFinding(
                            "conflicting_observation",
                            key,
                            idxs,
                            "Same key with conflicting density_value",
                            requires_confirmation=True,
                        )
                    )
            else:
                # same value already covered by exact_duplicate unless replicate
                if not any(f.fingerprint == key for f in findings):
                    if any(r not in (None, "", "nan") for r in reps):
                        findings.append(
                            DuplicateFinding(
                                "legitimate_replicate",
                                key,
                                idxs,
                                "Repeated identical measurements with replicate_id",
                            )
                        )
                    else:
                        findings.append(
                            DuplicateFinding(
                                "probable_duplicate",
                                key,
                                idxs,
                                "Same key and value without replicate markers",
                                requires_confirmation=True,
                            )
                        )
        return findings
