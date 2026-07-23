"""Prediction request schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        import math

        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
    except Exception:  # noqa: BLE001
        pass
    # pandas NA
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:  # noqa: BLE001
        pass
    if isinstance(value, str) and value.strip() in {"", "nan", "None", "<NA>"}:
        return None
    return value


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    baseline_cell_id: str | None = None
    instrument: str
    target_technique: str
    pitch_name_written: str | None = None
    pitch_midi_written: float | None = None
    pitch_name_sounding: str | None = None
    pitch_midi_sounding: float | None = None
    dynamic: str | None = None
    string_name: str | None = None
    articulation: str | None = None
    harmonic_order: int | None = None
    harmonic_type: str | None = None
    stopped_pitch: str | None = None
    stopped_pitch_name: str | None = None
    stopped_pitch_midi: float | None = None
    touched_pitch: str | None = None
    touched_pitch_name: str | None = None
    touched_interval: str | None = None
    mute_type: str | None = None
    mute_material: str | None = None
    mute_mass: float | str | None = None
    mute_mass_g: float | None = None
    mute_category: str | None = None
    bow_position_ratio: float | None = None  # deprecated alias of beta
    relative_bow_bridge_distance_beta: float | None = None
    bow_bridge_distance_m: float | None = None
    speaking_length_m: float | None = None
    bow_force_n: float | None = None
    bow_velocity_m_s: float | None = None
    excitation_region: str | None = None
    motion_regime: str | None = None
    timbre_execution_target: str | None = None
    notation_represents: str | None = None
    double_bass_pitch_convention: str | None = None
    pitch_register: str | None = None
    temporal_region: str | None = None
    requested_backend: str = "metric-only"
    target_metric_definition_id: str = "ewsd_v1"
    spectral_representation: dict[str, Any] | None = None
    production_instruction: dict[str, Any] | None = None

    @field_validator("instrument")
    @classmethod
    def _inst(cls, v: str) -> str:
        if v not in ALLOWED_INSTRUMENTS:
            raise ValueError(f"Unsupported instrument: {v}")
        return v

    @field_validator("target_technique")
    @classmethod
    def _tech(cls, v: str) -> str:
        if v not in ALLOWED_TECHNIQUES:
            raise ValueError(f"Unsupported technique: {v}")
        return v

    def technique(self) -> str:
        return self.target_technique

    def to_context(self) -> dict[str, Any]:
        stopped_name = self.stopped_pitch_name or self.stopped_pitch
        return {
            "instrument": self.instrument,
            "technique": self.target_technique,
            "pitch_name_written": self.pitch_name_written,
            "pitch_midi_written": self.pitch_midi_written,
            "pitch_name_sounding": self.pitch_name_sounding,
            "pitch_midi_sounding": self.pitch_midi_sounding,
            "dynamic": self.dynamic,
            "string_name": self.string_name,
            "articulation": self.articulation,
            "harmonic_order": self.harmonic_order,
            "harmonic_type": self.harmonic_type
            or ("artificial" if self.target_technique == "artificial_harmonic" else None),
            "stopped_pitch": stopped_name,
            "stopped_pitch_name": stopped_name,
            "stopped_pitch_midi": self.stopped_pitch_midi,
            "touched_pitch": self.touched_pitch_name or self.touched_pitch,
            "touched_interval": self.touched_interval,
            "mute_type": self.mute_type,
            "mute_material": self.mute_material,
            "mute_mass": self.mute_mass,
            "mute_mass_g": self.mute_mass_g,
            "mute_category": self.mute_category,
            "bow_position_ratio": self.bow_position_ratio,
            "relative_bow_bridge_distance_beta": self.relative_bow_bridge_distance_beta,
            "bow_bridge_distance_m": self.bow_bridge_distance_m,
            "speaking_length_m": self.speaking_length_m,
            "bow_force_n": self.bow_force_n,
            "bow_velocity_m_s": self.bow_velocity_m_s,
            "excitation_region": self.excitation_region,
            "motion_regime": self.motion_regime,
            "timbre_execution_target": self.timbre_execution_target,
            "notation_represents": self.notation_represents,
            "double_bass_pitch_convention": self.double_bass_pitch_convention,
            "register": self.pitch_register,
            "temporal_region": self.temporal_region,
            "target_metric_definition_id": self.target_metric_definition_id,
            "requested_backend": self.requested_backend,
            "spectral_representation": self.spectral_representation,
            "production_instruction": self.production_instruction,
        }


def load_prediction_requests(path: Path | str | None = None) -> list[PredictionRequest]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "prediction_requests.yaml")
    data = load_yaml(path)
    return [PredictionRequest.model_validate(item) for item in (data.get("requests") or [])]


def request_from_baseline_row(
    row: dict[str, Any],
    *,
    technique: str,
    backend: str = "metric-only",
    extras: dict[str, Any] | None = None,
) -> PredictionRequest:
    payload = {
        "baseline_cell_id": _clean(row.get("baseline_cell_id")),
        "instrument": _clean(row.get("instrument")),
        "target_technique": technique,
        "pitch_name_written": _clean(row.get("pitch_name_written")),
        "pitch_midi_written": _clean(row.get("pitch_midi_written")),
        "pitch_name_sounding": _clean(row.get("pitch_name_sounding")),
        "pitch_midi_sounding": _clean(row.get("pitch_midi_sounding")),
        "dynamic": _clean(row.get("dynamic")),
        "string_name": _clean(row.get("string_name")),
        "articulation": _clean(row.get("articulation")),
        "requested_backend": backend,
        "target_metric_definition_id": _clean(row.get("target_metric_definition_id")) or "ewsd_v1",
    }
    if extras:
        payload.update({k: _clean(v) for k, v in extras.items()})
    return PredictionRequest.model_validate(payload)
