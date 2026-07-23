"""Metric and observation validation for manual entry (service layer)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from string_technique_model.collections.instruments_domain import (
    EXCLUSION_REASON_UNSUPPORTED,
    UNSUPPORTED_STATUS,
    normalize_instrument_label,
)
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.manual_entry.constants import (
    ALLOWED_INSTRUMENTS,
    COLLECTION_ROLES,
    COLLECTION_TYPES,
    MEASURED_OR_ESTIMATED,
)
from string_technique_model.manual_entry.mapping import MappingService
from string_technique_model.manual_entry.numbers import parse_density_input, validate_against_domain
from string_technique_model.manual_entry.pitch import apply_cb_transposition, resolve_pitch_fields


@dataclass
class FieldIssue:
    row: int | None
    field: str
    invalid_value: Any
    reason: str
    severity: str  # error | warning
    required_correction: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "field": self.field,
            "invalid_value": self.invalid_value,
            "reason": self.reason,
            "severity": self.severity,
            "required_correction": self.required_correction,
        }


@dataclass
class ValidationReport:
    ok: bool
    status: str
    issues: list[FieldIssue] = field(default_factory=list)
    n_valid: int = 0
    n_warning: int = 0
    n_invalid: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "n_valid": self.n_valid,
            "n_warning": self.n_warning,
            "n_invalid": self.n_invalid,
            "details": self.details,
        }


class MetricValidationService:
    def __init__(
        self,
        metric_registry: MetricRegistry,
        mapping_service: MappingService | None = None,
        *,
        target_metric_definition_id: str = "ewsd_v1",
    ) -> None:
        self.metrics = metric_registry
        self.mapping = mapping_service or MappingService()
        self.target_metric_definition_id = target_metric_definition_id

    def validate_collection_metadata(self, meta: dict[str, Any]) -> list[FieldIssue]:
        issues: list[FieldIssue] = []
        required = [
            "collection_id",
            "display_name",
            "collection_type",
            "collection_role",
            "metric_definition_id",
            "created_by",
            "measured_or_estimated",
            "source_description",
        ]
        for key in required:
            if meta.get(key) is None or str(meta.get(key)).strip() == "":
                issues.append(
                    FieldIssue(
                        None,
                        key,
                        meta.get(key),
                        "missing_required_field",
                        "error",
                        f"Provide {key}",
                    )
                )
        cid = str(meta.get("collection_id") or "")
        if cid and not _safe_collection_id(cid):
            issues.append(
                FieldIssue(
                    None,
                    "collection_id",
                    cid,
                    "unsafe_identifier",
                    "error",
                    "Use [A-Za-z0-9_.-]+ only",
                )
            )
        if meta.get("collection_type") and meta["collection_type"] not in COLLECTION_TYPES:
            issues.append(
                FieldIssue(
                    None,
                    "collection_type",
                    meta.get("collection_type"),
                    "unknown_collection_type",
                    "error",
                    f"Choose one of {sorted(COLLECTION_TYPES)}",
                )
            )
        if meta.get("collection_role") and meta["collection_role"] not in COLLECTION_ROLES:
            issues.append(
                FieldIssue(
                    None,
                    "collection_role",
                    meta.get("collection_role"),
                    "unknown_collection_role",
                    "error",
                    f"Choose one of {sorted(COLLECTION_ROLES)}",
                )
            )
        mid = meta.get("metric_definition_id")
        if mid and mid not in self.metrics.definitions:
            issues.append(
                FieldIssue(
                    None,
                    "metric_definition_id",
                    mid,
                    "unregistered_metric",
                    "error",
                    "Select a registered metric_definition_id or register a new definition",
                )
            )
        moe = meta.get("measured_or_estimated")
        if moe and moe not in MEASURED_OR_ESTIMATED:
            issues.append(
                FieldIssue(
                    None,
                    "measured_or_estimated",
                    moe,
                    "invalid_measured_or_estimated",
                    "error",
                    f"Choose one of {sorted(MEASURED_OR_ESTIMATED)}",
                )
            )
        return issues

    def validate_observation(
        self,
        row: dict[str, Any],
        *,
        row_index: int | None = None,
        confirmed_locale: str | None = None,
        cb_transposition_semitones: int | None = None,
        cb_sounding_confirmed: bool = False,
    ) -> list[FieldIssue]:
        issues: list[FieldIssue] = []

        # Instrument
        raw_inst = row.get("instrument")
        mapped = normalize_instrument_label(raw_inst)
        if raw_inst is None or str(raw_inst).strip() == "":
            issues.append(
                FieldIssue(
                    row_index,
                    "instrument",
                    raw_inst,
                    "missing_required_field",
                    "error",
                    "Select vln, vla, vlc, or cb",
                )
            )
        elif mapped is None:
            issues.append(
                FieldIssue(
                    row_index,
                    "instrument",
                    raw_inst,
                    UNSUPPORTED_STATUS,
                    "error",
                    EXCLUSION_REASON_UNSUPPORTED,
                )
            )
        elif mapped not in ALLOWED_INSTRUMENTS:
            issues.append(
                FieldIssue(
                    row_index,
                    "instrument",
                    raw_inst,
                    UNSUPPORTED_STATUS,
                    "error",
                    EXCLUSION_REASON_UNSUPPORTED,
                )
            )

        # Technique mapping (unknown preserved as unmapped — warning, not discard)
        tech_label = row.get("technique") or row.get("original_technique_label")
        tech_map = self.mapping.map_technique(None if tech_label is None else str(tech_label))
        if not tech_label or not str(tech_label).strip():
            issues.append(
                FieldIssue(
                    row_index,
                    "technique",
                    tech_label,
                    "missing_required_field",
                    "error",
                    "Provide a technique label",
                )
            )
        elif tech_map.mapping_status == "unmapped":
            issues.append(
                FieldIssue(
                    row_index,
                    "technique",
                    tech_label,
                    "unmapped",
                    "warning",
                    "Create an explicit mapping or leave unmapped (excluded from modelling)",
                )
            )

        # Dynamic — never default to mf
        dyn_label = row.get("dynamic") or row.get("original_dynamic_label")
        dyn_map = self.mapping.map_dynamic(None if dyn_label is None else str(dyn_label))
        if dyn_label is None or str(dyn_label).strip() == "":
            issues.append(
                FieldIssue(
                    row_index,
                    "dynamic",
                    dyn_label,
                    "missing_dynamic_not_defaulted",
                    "warning",
                    "Provide a dynamic or accept unmapped missing dynamic",
                )
            )
        elif dyn_map.mapping_status == "unmapped":
            issues.append(
                FieldIssue(
                    row_index,
                    "dynamic",
                    dyn_label,
                    "unmapped",
                    "warning",
                    "Map dynamic explicitly or leave unmapped",
                )
            )

        # Metric
        mid = row.get("metric_definition_id")
        if not mid or str(mid).strip() == "":
            issues.append(
                FieldIssue(
                    row_index,
                    "metric_definition_id",
                    mid,
                    "missing_required_field",
                    "error",
                    "Select a registered metric_definition_id",
                )
            )
            domain = None
        elif mid not in self.metrics.definitions:
            issues.append(
                FieldIssue(
                    row_index,
                    "metric_definition_id",
                    mid,
                    "unregistered_metric",
                    "error",
                    "Register the metric definition first",
                )
            )
            domain = None
        else:
            domain = str(self.metrics.get(str(mid)).config.get("mathematical_domain") or "")
            compat = self.metrics.compare(str(mid), self.target_metric_definition_id)
            if compat.status == "incompatible":
                issues.append(
                    FieldIssue(
                        row_index,
                        "metric_definition_id",
                        mid,
                        "incompatible",
                        "warning",
                        compat.reason,
                    )
                )

        # Density
        parsed = parse_density_input(row.get("density_value"), confirmed_locale=confirmed_locale)
        if not parsed.ok:
            issues.append(
                FieldIssue(
                    row_index,
                    "density_value",
                    row.get("density_value"),
                    parsed.reason or "invalid",
                    "error",
                    "Enter a finite numeric value; confirm locale if ambiguous",
                )
            )
        else:
            ok_dom, why = validate_against_domain(parsed.value, domain)
            if not ok_dom:
                issues.append(
                    FieldIssue(
                        row_index,
                        "density_value",
                        parsed.value,
                        why or "outside_domain",
                        "error",
                        f"Value must satisfy domain {domain!r}; values are not clipped",
                    )
                )

        # Pitch
        pitch = resolve_pitch_fields(
            pitch_name=row.get("pitch_name_sounding") or row.get("pitch") or row.get("pitch_name"),
            pitch_midi=row.get("pitch_midi_sounding") if row.get("pitch_midi_sounding") is not None else row.get("pitch_midi"),
            fundamental_hz=row.get("fundamental_hz"),
        )
        if not pitch["ok"] and not pitch["errors"]:
            issues.append(
                FieldIssue(
                    row_index,
                    "pitch",
                    None,
                    "missing_required_field",
                    "error",
                    "Provide pitch name, MIDI, or frequency",
                )
            )
        for err in pitch["errors"]:
            issues.append(
                FieldIssue(
                    row_index,
                    "pitch",
                    {
                        "name": row.get("pitch_name_sounding"),
                        "midi": row.get("pitch_midi_sounding"),
                        "hz": row.get("fundamental_hz"),
                    },
                    err,
                    "error",
                    "Correct pitch name / MIDI / frequency consistency",
                )
            )

        instrument_code = mapped
        if instrument_code == "cb":
            cb = apply_cb_transposition(
                written_name=row.get("pitch_name_written"),
                written_midi=row.get("pitch_midi_written"),
                sounding_name=row.get("pitch_name_sounding") or pitch.get("pitch_name_sounding"),
                sounding_midi=row.get("pitch_midi_sounding")
                if row.get("pitch_midi_sounding") is not None
                else pitch.get("pitch_midi_sounding"),
                transposition_semitones=cb_transposition_semitones
                if cb_transposition_semitones is not None
                else row.get("cb_transposition_semitones"),
                confirmed=cb_sounding_confirmed or bool(row.get("cb_sounding_confirmed")),
            )
            for err in cb["errors"]:
                issues.append(
                    FieldIssue(
                        row_index,
                        "pitch_name_sounding",
                        cb.get("pitch_midi_sounding"),
                        err,
                        "error",
                        "Confirm double-bass sounding pitch; do not overwrite written pitch",
                    )
                )

        moe = row.get("measured_or_estimated")
        if moe and moe not in MEASURED_OR_ESTIMATED:
            issues.append(
                FieldIssue(
                    row_index,
                    "measured_or_estimated",
                    moe,
                    "invalid_measured_or_estimated",
                    "error",
                    f"Choose one of {sorted(MEASURED_OR_ESTIMATED)}",
                )
            )

        # Uncertainty: do not invent; SD ≠ SE
        if row.get("uncertainty_type") == "standard_deviation" and row.get("standard_error") is not None:
            if row.get("uncertainty_value") is None and row.get("standard_deviation") is None:
                issues.append(
                    FieldIssue(
                        row_index,
                        "uncertainty_type",
                        "standard_deviation",
                        "sd_se_confusion",
                        "warning",
                        "Do not treat SE as SD; fill the matching field",
                    )
                )

        return issues

    def validate_rows(self, rows: list[dict[str, Any]], meta: dict[str, Any] | None = None) -> ValidationReport:
        issues: list[FieldIssue] = []
        if meta is not None:
            issues.extend(self.validate_collection_metadata(meta))
        row_statuses: list[str] = []
        for i, row in enumerate(rows):
            row_issues = self.validate_observation(row, row_index=i)
            issues.extend(row_issues)
            if any(x.severity == "error" for x in row_issues):
                row_statuses.append("invalid")
            elif any(x.severity == "warning" for x in row_issues):
                row_statuses.append("warning")
            else:
                row_statuses.append("valid")
        n_invalid = row_statuses.count("invalid")
        n_warning = row_statuses.count("warning")
        n_valid = row_statuses.count("valid")
        meta_errors = [i for i in issues if i.row is None and i.severity == "error"]
        if n_invalid or meta_errors:
            status = "validation_failed"
            ok = False
        elif n_warning or any(i.severity == "warning" for i in issues):
            status = "validation_warning"
            ok = True
        else:
            status = "ready_to_commit"
            ok = True
        return ValidationReport(
            ok=ok and status in {"ready_to_commit", "validation_warning"},
            status=status,
            issues=issues,
            n_valid=n_valid,
            n_warning=n_warning,
            n_invalid=n_invalid,
            details={"row_statuses": row_statuses},
        )


def _safe_collection_id(cid: str) -> bool:
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", cid))
