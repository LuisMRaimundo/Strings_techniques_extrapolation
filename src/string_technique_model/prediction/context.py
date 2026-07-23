"""Prediction context validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES


@dataclass
class ContextValidationResult:
    ok: bool
    status: str
    missing_required: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def validate_prediction_context(
    baseline_record: dict[str, Any] | None,
    request_context: dict[str, Any],
    *,
    required_metadata: set[str],
    technique_cfg: dict[str, Any] | None = None,
) -> ContextValidationResult:
    notes: list[str] = []
    missing: list[str] = []

    instrument = request_context.get("instrument")
    technique = request_context.get("technique")
    if instrument not in ALLOWED_INSTRUMENTS:
        return ContextValidationResult(False, "unsupported_instrument_technique_cell", notes=["bad_instrument"])
    if technique not in ALLOWED_TECHNIQUES:
        return ContextValidationResult(False, "unsupported_instrument_technique_cell", notes=["bad_technique"])

    if baseline_record is None:
        return ContextValidationResult(False, "missing_ordinary_baseline", notes=["no_baseline_record"])

    base_val = baseline_record.get("baseline_value")
    if base_val is None:
        base_val = baseline_record.get("baseline_mean")
    if base_val is None or (isinstance(base_val, float) and base_val != base_val):
        return ContextValidationResult(False, "missing_ordinary_baseline", notes=["null_baseline_value"])

    if baseline_record.get("technique") not in {None, "ordinary", "arco", "ordinario"}:
        # Ordinary baseline cells must be ordinary-bowing
        if str(baseline_record.get("technique")) != "ordinary":
            notes.append("baseline_technique_not_ordinary")

    for key in sorted(required_metadata):
        # Map request aliases
        aliases = {
            "stopped_pitch_name": ("stopped_pitch_name", "stopped_pitch"),
            "sounding_pitch_name": ("sounding_pitch_name", "pitch_name_sounding"),
            "sounding_pitch_midi": ("sounding_pitch_midi", "pitch_midi_sounding"),
        }
        keys = aliases.get(key, (key,))
        if not any(request_context.get(k) is not None for k in keys):
            missing.append(key)

    cfg = technique_cfg or {}
    if technique == "artificial_harmonic":
        if cfg.get("require_explicit_harmonic_order", True):
            if request_context.get("harmonic_order") is None:
                if "harmonic_order" not in missing:
                    missing.append("harmonic_order")
            else:
                allowed = set(cfg.get("allowed_orders") or [])
                if allowed and int(request_context["harmonic_order"]) not in allowed:
                    return ContextValidationResult(
                        False,
                        "outside_parameter_validity_range",
                        notes=[f"harmonic_order_not_allowed:{request_context['harmonic_order']}"],
                    )
        if request_context.get("harmonic_type") == "natural":
            return ContextValidationResult(
                False,
                "incompatible_metric",
                notes=["natural_harmonic_cannot_parameterise_artificial_harmonic"],
            )
        touched_interval = request_context.get("touched_interval")
        if touched_interval is not None and request_context.get("harmonic_order") is not None:
            from string_technique_model.production.harmonics import validate_harmonic_interval_order

            hv = validate_harmonic_interval_order(
                str(touched_interval),
                int(request_context["harmonic_order"]),
                allow_inference=bool(cfg.get("allow_order_inference", False)),
                left_hand_regime="artificial_harmonic",
                harmonic_type=str(request_context.get("harmonic_type") or "artificial"),
            )
            if not hv.ok:
                return ContextValidationResult(
                    False,
                    "outside_parameter_validity_range",
                    notes=list(hv.errors),
                )
            notes.extend(hv.warnings)
        # Double-bass written vs sounding — keep convention explicit; do not invent.
        if instrument == "cb" and (cfg.get("instruments") or {}).get("cb", {}).get(
            "require_written_and_sounding_distinction"
        ):
            if request_context.get("double_bass_pitch_convention") in {None, "unresolved"}:
                notes.append("cb_pitch_convention_unresolved")
            if (
                request_context.get("pitch_midi_written") is not None
                and request_context.get("pitch_midi_sounding") is not None
                and float(request_context["pitch_midi_written"])
                == float(request_context["pitch_midi_sounding"])
            ):
                notes.append("cb_written_equals_sounding_check_octave_transposition")

    # Flautando must not be auto-mapped even when contact-point fields are present.
    if str(request_context.get("timbre_execution_target") or "").lower() == "flautando":
        notes.append("flautando_execution_target_distinct_from_contact_point")
    if str(request_context.get("excitation_region") or "") in {
        "directly_on_bridge",
        "afterlength_behind_bridge",
    }:
        notes.append("excitation_region_outside_tasto_ponticello_continuum")

    if technique == "con_sordino" and cfg.get("require_mute_type", True):
        if not request_context.get("mute_type"):
            if "mute_type" not in missing:
                missing.append("mute_type")

    if technique == "sul_tasto":
        if cfg.get("equate_flautando"):
            notes.append("flautando_equivalence_enabled_by_config")
        # Keep distinct unless source equates — never auto-merge
        if str(request_context.get("articulation") or "").lower() == "flautando":
            notes.append("flautando_is_not_automatically_sul_tasto")

    if missing:
        return ContextValidationResult(
            False,
            "insufficient_context_metadata",
            missing_required=missing,
            notes=notes,
        )
    return ContextValidationResult(True, "context_ok", notes=notes)
