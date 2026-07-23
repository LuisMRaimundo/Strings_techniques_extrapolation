"""Deterministic migration from legacy flat technique records."""

from __future__ import annotations

from typing import Any

from string_technique_model.production.bow_contact import validate_bow_contact
from string_technique_model.production.harmonics import validate_harmonic_interval_order
from string_technique_model.production.models import (
    BowContactInstruction,
    BowingConditions,
    HarmonicInstruction,
    MuteInstruction,
    PerformanceContext,
    ProductionInstruction,
)
from string_technique_model.production.mute import normalize_mute_mass

_MUTE_TYPE_ALIASES: dict[str, str] = {
    "orchestral": "standard_performance_orchestral",
    "standard": "standard_performance_orchestral",
    "standard_performance_orchestral": "standard_performance_orchestral",
    "performance": "performance_mute",
    "performance_mute": "performance_mute",
    "light_practice": "light_practice",
    "light": "light_practice",
    "practice": "heavy_practice",
    "heavy_practice": "heavy_practice",
    "hotel": "heavy_practice_hotel",
    "heavy_practice_hotel": "heavy_practice_hotel",
    "wood": "historical_or_modern_wood",
    "metal": "historical_metal",
    "historical": "historical",
    "adjustable": "adjustable_partial",
    "adjustable_partial": "adjustable_partial",
    "other": "other_explicitly_described",
    "none": "none",
    "unresolved": "unresolved",
}

_TECHNIQUE_ALIASES: dict[str, str] = {
    "ordinario": "ordinary",
    "ordinario arco": "ordinary",
    "arco": "ordinary",
    "artificial harmonic": "artificial_harmonic",
    "sul ponticello": "sul_ponticello",
    "ponticello": "sul_ponticello",
    "sul tasto": "sul_tasto",
    "tastiera": "sul_tasto",
    "con sordino": "con_sordino",
    "con sord.": "con_sordino",
    "muted": "con_sordino",
    "flautando": "flautando",
}


def _norm(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    f = _coerce_float(value)
    if f is None:
        return None
    return int(f)


def _resolve_technique(record: dict[str, Any]) -> str | None:
    raw = record.get("technique")
    if raw is None:
        return None
    key = _norm(raw)
    if key in _TECHNIQUE_ALIASES:
        return _TECHNIQUE_ALIASES[key]
    return str(raw).strip()


def _map_mute_category(mute_type: str | None) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if mute_type is None or not str(mute_type).strip():
        return "unresolved", ["con_sordino without mute_type; category left unresolved"]
    key = _norm(mute_type)
    category = _MUTE_TYPE_ALIASES.get(key)
    if category is None:
        warnings.append(f"unrecognized mute_type {mute_type!r}; category left unresolved")
        return "unresolved", warnings
    return category, warnings


def _has_harmonic_fields(record: dict[str, Any]) -> bool:
    harmonic_keys = (
        "harmonic_type",
        "harmonic_order",
        "stopped_pitch_name",
        "stopped_pitch_midi",
        "touched_pitch_name",
        "touched_pitch_midi",
        "touched_interval",
    )
    return any(record.get(k) not in (None, "") for k in harmonic_keys)


def _build_left_hand(record: dict[str, Any], regime: str, warnings: list[str]) -> HarmonicInstruction:
    harmonic_type_raw = record.get("harmonic_type")
    harmonic_type: str | None = None
    if harmonic_type_raw:
        ht = _norm(harmonic_type_raw)
        if ht in {"natural", "artificial", "half", "multiphonic"}:
            harmonic_type = ht
        elif ht in {"artificial_harmonic", "artificial harmonic"}:
            harmonic_type = "artificial"
            warnings.append("normalized harmonic_type to 'artificial'")
        else:
            warnings.append(f"unrecognized harmonic_type {harmonic_type_raw!r}")

    if regime == "artificial_harmonic" and harmonic_type is None:
        harmonic_type = "artificial"

    touched_interval = record.get("touched_interval")
    harmonic_order = _coerce_int(record.get("harmonic_order"))

    interval_validation = validate_harmonic_interval_order(
        str(touched_interval) if touched_interval else None,
        harmonic_order,
        allow_inference=bool(record.get("allow_order_inference", False)),
        left_hand_regime=regime,
        harmonic_type=harmonic_type,
    )
    warnings.extend(interval_validation.warnings)
    if interval_validation.inferred_order is not None and harmonic_order is None:
        harmonic_order = interval_validation.inferred_order

    return HarmonicInstruction(
        left_hand_regime=regime,  # type: ignore[arg-type]
        harmonic_type=harmonic_type,  # type: ignore[arg-type]
        stopped_pitch_name=record.get("stopped_pitch_name"),
        stopped_pitch_midi=_coerce_float(record.get("stopped_pitch_midi")),
        touched_pitch_name=record.get("touched_pitch_name"),
        touched_pitch_midi=_coerce_float(record.get("touched_pitch_midi")),
        harmonic_order=harmonic_order,
        touched_interval=str(touched_interval) if touched_interval else None,
        string_name=record.get("string_name"),
        allow_order_inference=bool(record.get("allow_order_inference", False)),
    )


def _infer_bow_category_from_position(record: dict[str, Any]) -> str | None:
    """Infer verbal category from description text only — never from beta thresholds."""
    description = _norm(record.get("bow_position_description") or "")
    if "ponticello" in description or "pont." in description:
        return "sul_ponticello"
    if "tasto" in description or "tastiera" in description:
        return "sul_tasto"
    return None


def _build_bow_contact(
    record: dict[str, Any],
    *,
    default_category: str | None,
    warnings: list[str],
) -> BowContactInstruction:
    category = default_category
    inferred = _infer_bow_category_from_position(record)
    if inferred and category is None:
        category = inferred
    elif inferred and category and inferred != category:
        warnings.append(
            f"preserving bow category {category!r} alongside position hint {inferred!r}"
        )

    bow_ratio = _coerce_float(record.get("bow_position_ratio"))
    bow_bridge_m = _coerce_float(record.get("bow_bridge_distance_m"))
    speaking_m = _coerce_float(record.get("speaking_length_m"))
    beta = _coerce_float(record.get("relative_bow_bridge_distance_beta"))

    instruction = BowContactInstruction(
        category=category,  # type: ignore[arg-type]
        relative_bow_bridge_distance_beta=beta,
        bow_bridge_distance_m=bow_bridge_m,
        speaking_length_m=speaking_m,
        excitation_region=record.get("excitation_region"),
        motion_regime=record.get("motion_regime"),
        bow_position_ratio_deprecated=bow_ratio,
        beta_provenance=record.get("beta_provenance"),
    )

    validation = validate_bow_contact(instruction)
    warnings.extend(validation.warnings)
    if validation.relative_bow_bridge_distance_beta is not None:
        instruction = instruction.model_copy(
            update={"relative_bow_bridge_distance_beta": validation.relative_bow_bridge_distance_beta}
        )
    return instruction


def _build_mute(record: dict[str, Any], *, state: str, warnings: list[str]) -> MuteInstruction:
    mute_type = record.get("mute_type")
    category: str | None = "none"
    mute_warnings: list[str] = []

    if state == "on":
        category, mute_warnings = _map_mute_category(
            str(mute_type) if mute_type is not None else None
        )
    elif state == "off":
        category = "none"
    else:
        category = "unresolved"

    warnings.extend(mute_warnings)

    mass_g, mass_raw, mass_warnings = normalize_mute_mass(record.get("mute_mass"))
    warnings.extend(mass_warnings)

    return MuteInstruction(
        state=state,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        material=record.get("mute_material"),
        mute_mass_g=mass_g,
        mass_raw=mass_raw or (str(record.get("mute_mass")) if record.get("mute_mass") is not None else None),
        geometry=record.get("mute_geometry"),
        bridge_contact_area=record.get("bridge_contact_area"),
        placement=record.get("mute_placement"),
        adjustable_setting=record.get("adjustable_setting"),
        device_model_id=record.get("device_model_id"),
    )


def _build_performance_context(record: dict[str, Any]) -> PerformanceContext:
    return PerformanceContext(
        instrument=record.get("instrument"),
        pitch_name_written=record.get("pitch_name_written"),
        pitch_midi_written=_coerce_float(record.get("pitch_midi_written")),
        pitch_name_sounding=record.get("pitch_name_sounding"),
        pitch_midi_sounding=_coerce_float(record.get("pitch_midi_sounding")),
        string_name=record.get("string_name"),
        fundamental_frequency_hz=_coerce_float(record.get("fundamental_hz")),
        register=record.get("register"),
        performer_id=record.get("performer_id"),
        instrument_id=record.get("instrument_id"),
        instrument_setup=record.get("instrument_setup"),
        string_model=record.get("string_model"),
        string_scale_m=_coerce_float(record.get("string_scale_m")),
        bow_rosin_metadata=record.get("bow_rosin_metadata"),
        room=record.get("room"),
        microphone=record.get("microphone"),
        microphone_position=record.get("microphone_position"),
        recording_geometry=record.get("recording_geometry"),
        ensemble_or_section_size=_coerce_int(record.get("ensemble_or_section_size")),
        player_index=_coerce_int(record.get("player_index")),
        take_index=_coerce_int(record.get("take_index")),
        repeated_measure_design=record.get("repeated_measure_design"),
        inter_player_variance=record.get("inter_player_variance"),
        within_player_variance=record.get("within_player_variance"),
    )


def migrate_legacy_technique_record(record: dict[str, Any]) -> ProductionInstruction:
    """Deterministically map a flat legacy record to ProductionInstruction."""
    warnings: list[str] = []
    technique = _resolve_technique(record)
    legacy_label = technique or record.get("technique")

    left_hand: HarmonicInstruction | None = None
    bow_default: str | None = None
    mute_state = "off"
    timbre: str | None = None

    articulation = record.get("articulation")
    if articulation and _norm(articulation) == "flautando":
        timbre = "flautando"

    if technique == "flautando":
        timbre = "flautando"
        warnings.append(
            "legacy label flautando mapped to timbre_execution_target; "
            "not equated to sul_tasto (information loss if only flautando was recorded)"
        )
        technique = None

    if technique == "ordinary" or technique is None:
        left_hand = _build_left_hand(record, "ordinary_stopped", warnings)
        bow_default = "ordinario"
        mute_state = "off"
    elif technique == "artificial_harmonic":
        left_hand = _build_left_hand(record, "artificial_harmonic", warnings)
        bow_default = None
        if _infer_bow_category_from_position(record):
            bow_default = _infer_bow_category_from_position(record)
            warnings.append("preserved bow position hints alongside artificial_harmonic")
        if record.get("mute_type") or record.get("mute_mass"):
            mute_state = "on"
    elif technique == "sul_tasto":
        bow_default = "sul_tasto"
        regime = "artificial_harmonic" if _has_harmonic_fields(record) else "ordinary_stopped"
        if regime != "ordinary_stopped":
            left_hand = _build_left_hand(record, regime, warnings)
        else:
            left_hand = _build_left_hand(record, "ordinary_stopped", warnings)
        if record.get("mute_type") or record.get("mute_mass"):
            mute_state = "on"
    elif technique == "sul_ponticello":
        bow_default = "sul_ponticello"
        regime = "artificial_harmonic" if _has_harmonic_fields(record) else "ordinary_stopped"
        left_hand = _build_left_hand(record, regime, warnings)
        if record.get("mute_type") or record.get("mute_mass"):
            mute_state = "on"
    elif technique == "con_sordino":
        left_hand = _build_left_hand(
            record,
            "artificial_harmonic" if _has_harmonic_fields(record) else "ordinary_stopped",
            warnings,
        )
        mute_state = "on"
        if _infer_bow_category_from_position(record):
            bow_default = _infer_bow_category_from_position(record)
    else:
        warnings.append(f"unrecognized legacy technique {technique!r}; fields partially migrated")
        left_hand = _build_left_hand(record, "ordinary_stopped", warnings)

    bow_contact = _build_bow_contact(record, default_category=bow_default, warnings=warnings)
    mute = _build_mute(record, state=mute_state, warnings=warnings)
    bowing = BowingConditions(
        force_n=_coerce_float(record.get("bow_force_n")),
        velocity_m_s=_coerce_float(record.get("bow_velocity_m_s")),
        articulation=record.get("articulation"),
        hair_inclination=record.get("hair_inclination"),
        contact_area_descriptor=record.get("contact_area_descriptor"),
        dynamic=record.get("dynamic"),
    )

    if timbre is None:
        timbre = "ordinary_colour"

    provenance: dict[str, Any] = {}
    if record.get("provenance"):
        provenance["source_provenance"] = record.get("provenance")
    if record.get("record_id"):
        provenance["record_id"] = record.get("record_id")

    missingness: dict[str, Any] = {}
    if record.get("missingness_status"):
        missingness["legacy_missingness_status"] = record.get("missingness_status")

    return ProductionInstruction(
        legacy_technique_label=str(legacy_label) if legacy_label else None,
        left_hand=left_hand,
        bow_contact=bow_contact,
        mute=mute,
        bowing=bowing,
        timbre_execution_target=timbre,  # type: ignore[arg-type]
        performance_context=_build_performance_context(record),
        provenance=provenance,
        missingness=missingness,
        migration_warnings=warnings,
    )


def _scalar(value: Any) -> str | float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def production_to_tabular(prod: ProductionInstruction) -> dict[str, str | float | int | None]:
    """Flatten a ProductionInstruction to JSON-serializable scalars."""
    lh = prod.left_hand
    bc = prod.bow_contact
    mute = prod.mute
    bow = prod.bowing
    ctx = prod.performance_context

    row: dict[str, str | float | int | None] = {
        "schema_version": prod.schema_version,
        "legacy_technique_label": prod.legacy_technique_label,
        "timbre_execution_target": prod.timbre_execution_target,
        "migration_warnings": ", ".join(prod.migration_warnings) if prod.migration_warnings else None,
        "left_hand_regime": lh.left_hand_regime if lh else None,
        "harmonic_type": lh.harmonic_type if lh else None,
        "harmonic_order": lh.harmonic_order if lh else None,
        "touched_interval": lh.touched_interval if lh else None,
        "stopped_pitch_name": lh.stopped_pitch_name if lh else None,
        "stopped_pitch_midi": lh.stopped_pitch_midi if lh else None,
        "touched_pitch_name": lh.touched_pitch_name if lh else None,
        "touched_pitch_midi": lh.touched_pitch_midi if lh else None,
        "bow_contact_category": bc.category,
        "relative_bow_bridge_distance_beta": bc.relative_bow_bridge_distance_beta,
        "bow_bridge_distance_m": bc.bow_bridge_distance_m,
        "speaking_length_m": bc.speaking_length_m,
        "excitation_region": bc.excitation_region,
        "motion_regime": bc.motion_regime,
        "mute_state": mute.state,
        "mute_category": mute.category,
        "mute_material": mute.material,
        "mute_mass_g": mute.mute_mass_g,
        "mute_mass_raw": mute.mass_raw,
        "dynamic": bow.dynamic,
        "articulation": bow.articulation,
        "bow_force_n": bow.force_n,
        "bow_velocity_m_s": bow.velocity_m_s,
        "instrument": ctx.instrument,
        "pitch_name_written": ctx.pitch_name_written,
        "pitch_midi_written": ctx.pitch_midi_written,
        "pitch_name_sounding": ctx.pitch_name_sounding,
        "pitch_midi_sounding": ctx.pitch_midi_sounding,
        "fundamental_frequency_hz": ctx.fundamental_frequency_hz,
        "string_name": ctx.string_name,
        "register": ctx.performance_register,
        "performer_id": ctx.performer_id,
        "instrument_id": ctx.instrument_id,
    }
    return {k: _scalar(v) for k, v in row.items()}
