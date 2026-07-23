"""Collection role assignment with data-leakage protection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from string_technique_model.collections.leakage import assert_role_separation
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.manual_entry.constants import ALLOWED_INSTRUMENTS, CANONICAL_TECHNIQUES, COLLECTION_ROLES


@dataclass
class RoleAssignmentResult:
    ok: bool
    role: str
    blocked: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "role": self.role,
            "blocked": self.blocked,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


class RoleAssignmentService:
    def __init__(self, metric_registry: MetricRegistry, *, target_metric: str = "ewsd_v1") -> None:
        self.metrics = metric_registry
        self.target_metric = target_metric

    def validate_role_assignment(
        self,
        *,
        role: str,
        frame: pd.DataFrame,
        meta: dict[str, Any],
        existing_calibration_ids: list[str] | None = None,
        existing_validation_ids: list[str] | None = None,
        calibration_frames: list[pd.DataFrame] | None = None,
        validation_frames: list[pd.DataFrame] | None = None,
    ) -> RoleAssignmentResult:
        reasons: list[str] = []
        warnings: list[str] = []
        if role not in COLLECTION_ROLES:
            return RoleAssignmentResult(False, role, True, [f"unknown_role:{role}"])

        if frame is None or frame.empty:
            reasons.append("empty_collection")

        # Instrument domain
        if "instrument" in frame.columns:
            bad = sorted(
                {
                    str(x)
                    for x in frame["instrument"].dropna().unique()
                    if str(x) not in ALLOWED_INSTRUMENTS
                }
            )
            if bad:
                reasons.append(f"instrument_outside_domain:{bad}")

        # Canonical technique required for modelling roles
        modelling_roles = {"baseline", "model_calibration", "external_validation"}
        if role in modelling_roles and "technique_mapping_status" in frame.columns:
            unmapped = int((frame["technique_mapping_status"] == "unmapped").sum())
            if unmapped:
                reasons.append(f"unmapped_techniques:{unmapped}")
        if role in modelling_roles and "technique" in frame.columns:
            null_tech = int(frame["technique"].isna().sum())
            if null_tech:
                reasons.append(f"null_canonical_technique:{null_tech}")
            non_can = sorted(
                {
                    str(x)
                    for x in frame["technique"].dropna().unique()
                    if str(x) not in CANONICAL_TECHNIQUES
                }
            )
            if non_can:
                reasons.append(f"non_canonical_techniques:{non_can}")

        if role in modelling_roles and "dynamic_mapping_status" in frame.columns:
            unmapped_d = int((frame["dynamic_mapping_status"] == "unmapped").sum())
            if unmapped_d:
                reasons.append(f"unmapped_dynamics:{unmapped_d}")

        # Metric compatibility
        mids = sorted({str(x) for x in frame.get("metric_definition_id", pd.Series(dtype=object)).dropna().unique()})
        for mid in mids:
            if mid not in self.metrics.definitions:
                reasons.append(f"unknown_metric:{mid}")
                continue
            cmp = self.metrics.compare(mid, self.target_metric)
            if cmp.status == "incompatible":
                reasons.append(f"incompatible_metric:{mid}:{cmp.reason}")

        # Provenance
        if not meta.get("source_description"):
            reasons.append("missing_source_description")
        if not meta.get("measured_or_estimated"):
            reasons.append("missing_measured_or_estimated")

        # Leakage: same collection cannot be both calibration and validation
        cal_ids = list(existing_calibration_ids or [])
        val_ids = list(existing_validation_ids or [])
        cid = str(meta.get("collection_id") or "")
        if role == "model_calibration":
            cal_ids = sorted(set(cal_ids + [cid]))
        if role == "external_validation":
            val_ids = sorted(set(val_ids + [cid]))
        sep = assert_role_separation([], cal_ids, val_ids)
        if not sep.ok:
            reasons.append(sep.message)

        # Observation-level leakage across frames
        if role == "model_calibration" and validation_frames:
            from string_technique_model.collections.leakage import detect_calibration_validation_leakage

            for vf in validation_frames:
                leak = detect_calibration_validation_leakage(frame, vf)
                if not leak.ok:
                    reasons.append(leak.message)
        if role == "external_validation" and calibration_frames:
            from string_technique_model.collections.leakage import detect_calibration_validation_leakage

            for cf in calibration_frames:
                leak = detect_calibration_validation_leakage(cf, frame)
                if not leak.ok:
                    reasons.append(leak.message)

        if role == "baseline" and meta.get("measured_or_estimated") in {
            "estimated",
            "simulated",
            "manually_transcribed",
        }:
            warnings.append(
                "Baseline role with non-measured status requires scientific justification"
            )

        blocked = bool(reasons)
        return RoleAssignmentResult(
            ok=not blocked,
            role=role,
            blocked=blocked,
            reasons=reasons,
            warnings=warnings,
        )
