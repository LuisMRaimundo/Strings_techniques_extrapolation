"""User-facing metadata validation (error / warning / information)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from string_technique_model.pitch.registry import get_default_pitch_registry, load_instrument_midi_ranges
from string_technique_model.production.harmonics import validate_harmonic_interval_order
from string_technique_model.production.mute import normalize_mute_mass

Severity = Literal["error", "warning", "information"]


@dataclass
class ValidationIssue:
    row_index: int | None
    record_id: str | None
    field: str
    severity: Severity
    message: str
    invalid_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_index": self.row_index,
            "record_id": self.record_id,
            "field": self.field,
            "severity": self.severity,
            "message": self.message,
            "invalid_value": self.invalid_value,
        }


@dataclass
class MetadataValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def n_info(self) -> int:
        return sum(1 for i in self.issues if i.severity == "information")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "n_errors": self.n_errors,
            "n_warnings": self.n_warnings,
            "n_info": self.n_info,
            "issues": [i.to_dict() for i in self.issues],
        }


class MetadataValidationService:
    def __init__(self) -> None:
        self.registry = get_default_pitch_registry()
        self.instrument_ranges = load_instrument_midi_ranges()

    def validate_rows(self, rows: list[dict[str, Any]]) -> MetadataValidationReport:
        issues: list[ValidationIssue] = []
        for idx, row in enumerate(rows):
            issues.extend(self.validate_row(row, row_index=idx))
        return MetadataValidationReport(ok=not any(i.severity == "error" for i in issues), issues=issues)

    def validate_row(self, row: dict[str, Any], *, row_index: int | None = None) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        rid = row.get("record_id")

        def add(field: str, severity: Severity, message: str, value: Any = None) -> None:
            issues.append(
                ValidationIssue(row_index, rid if isinstance(rid, str) else None, field, severity, message, value)
            )

        # File path
        path = row.get("source_file") or row.get("audio_file")
        if path not in (None, ""):
            try:
                p = Path(str(path))
                # Malformed: empty after strip already handled; reject null bytes
                if "\x00" in str(path):
                    add("source_file", "error", "Malformed file path.", path)
                elif p.is_absolute() and not p.exists():
                    add("source_file", "warning", "Audio/source file path does not exist on this machine.", path)
            except (OSError, ValueError):
                add("source_file", "error", "Malformed file path.", path)

        # Speaking length
        speaking = row.get("speaking_length_m")
        if speaking not in (None, ""):
            try:
                if float(str(speaking)) <= 0:
                    add("speaking_length_m", "error", "Speaking length must be positive.", speaking)
            except (TypeError, ValueError):
                add("speaking_length_m", "error", "Speaking length is not a number.", speaking)

        # Pitch validity by mode
        mode = str(row.get("pitch_mode") or "unknown")
        if mode == "single_note":
            name = row.get("pitch_name") or row.get("pitch_name_sounding") or row.get("pitch_name_written")
            midi = row.get("pitch_midi") or row.get("pitch_midi_sounding") or row.get("pitch_midi_written")
            if name not in (None, ""):
                rec = self.registry.get_by_spelling(str(name))
                if rec is None:
                    add("pitch_name", "error", "Invalid pitch spelling.", name)
                elif midi not in (None, "") and abs(float(str(midi)) - rec.midi) > 0.51:
                    add("pitch_midi", "error", "Pitch name and MIDI value are inconsistent.", midi)
                else:
                    if midi in (None, "") and rec is not None:
                        add("pitch_midi", "information", "Derived MIDI value available from pitch spelling.", rec.midi)
                    add("fundamental_hz", "information", "Derived frequency available from MIDI/tuning.", rec.frequency_hz)
            instrument = row.get("instrument")
            midi_val = None
            try:
                if midi not in (None, ""):
                    midi_val = float(str(midi))
                elif name not in (None, ""):
                    r = self.registry.get_by_spelling(str(name))
                    midi_val = float(r.midi) if r else None
            except (TypeError, ValueError):
                midi_val = None
            if (
                midi_val is not None
                and instrument in self.instrument_ranges
                and not bool(row.get("show_all_pitches"))
            ):
                lo_i, hi_i = self.instrument_ranges[str(instrument)]
                if not (lo_i <= midi_val <= hi_i):
                    add(
                        "pitch_midi",
                        "warning",
                        "Pitch outside normal instrument range (disable filter for extended techniques).",
                        midi_val,
                    )
        elif mode == "pitch_range":
            lo = row.get("pitch_lowest_midi")
            hi = row.get("pitch_highest_midi")
            lo_n = row.get("pitch_lowest_name")
            hi_n = row.get("pitch_highest_name")
            if lo_n and self.registry.get_by_spelling(str(lo_n)) is None:
                add("pitch_lowest_name", "error", "Invalid lowest pitch.", lo_n)
            if hi_n and self.registry.get_by_spelling(str(hi_n)) is None:
                add("pitch_highest_name", "error", "Invalid highest pitch.", hi_n)
            try:
                if lo not in (None, "") and hi not in (None, "") and float(str(lo)) > float(str(hi)):
                    add("pitch_highest_midi", "error", "Highest pitch must be ≥ lowest pitch.", hi)
            except (TypeError, ValueError):
                add("pitch_lowest_midi", "error", "Pitch range MIDI values must be numeric.", lo)
        elif mode == "multiple_notes":
            names = row.get("pitch_names") or []
            if isinstance(names, str):
                names = [n.strip() for n in names.split(",") if n.strip()]
            for n in names:
                if self.registry.get_by_spelling(str(n)) is None:
                    add("pitch_names", "error", f"Invalid pitch in list: {n}", n)
        elif mode in {"unpitched_or_noise", "unknown", "open_string"}:
            pass

        if str(row.get("pitch_representation") or "unresolved") == "unresolved" and mode == "single_note":
            if row.get("pitch_name_written") or row.get("pitch_name_sounding"):
                add(
                    "pitch_representation",
                    "warning",
                    "Written/sounding convention unresolved.",
                    row.get("pitch_representation"),
                )

        # Harmonic interval/order
        left = str(row.get("left_hand_regime") or row.get("technique") or "")
        if "harmonic" in left.lower() or row.get("harmonic_type") or row.get("touched_interval"):
            order = row.get("harmonic_order")
            order_i = int(float(str(order))) if order not in (None, "") else None
            result = validate_harmonic_interval_order(
                row.get("touched_interval"),
                order_i,
                allow_inference=bool(row.get("allow_order_inference")),
                left_hand_regime=row.get("left_hand_regime"),
                harmonic_type=row.get("harmonic_type"),
            )
            for err in result.errors:
                add("harmonic_order", "error", err, order)
            for warn in result.warnings:
                severity: Severity = "warning"
                if "ambiguous" in warn.lower() or "inference" in warn.lower():
                    severity = "warning"
                add("touched_interval", severity, warn, row.get("touched_interval"))
            if row.get("notation_represents") in (None, "", "unresolved"):
                add("notation_represents", "warning", "Harmonic notation ambiguous (touched vs sounding).", None)

        # Mute mass
        if row.get("mute_mass") not in (None, ""):
            try:
                mass_g, _raw, warnings = normalize_mute_mass(row.get("mute_mass"))
                if mass_g is not None and mass_g < 0:
                    add("mute_mass", "error", "Invalid mute mass (negative).", row.get("mute_mass"))
                for w in warnings:
                    add("mute_mass", "warning", w, row.get("mute_mass"))
            except Exception as exc:  # noqa: BLE001 — surface as validation, not traceback
                add("mute_mass", "error", f"Invalid mute mass: {exc}", row.get("mute_mass"))

        # Technique completeness
        if not row.get("technique") and not row.get("left_hand_regime") and not row.get("bow_contact_regime"):
            add("technique_display", "warning", "Technique metadata incomplete.", None)

        # Optional advanced metadata absent
        if row.get("sample_rate_hz") in (None, ""):
            add("sample_rate_hz", "information", "Optional recording metadata (sample rate) absent.", None)

        return issues
