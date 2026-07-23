"""Generate harmonic targets from physical string×order geometry.

Ordinary chromatic registers must NOT be copied onto harmonic techniques.

Pipeline:
  1) generate all physically plausible targets (open string × order, or artificial map)
  2) apply optional analysis / user sounding-range filter
  3) mark inclusion reasons (never call analysis-excluded rows 'impossible')
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.baselines import normalize_instrument
from string_technique_model.extrapolation.register_builder import resolve_note
from string_technique_model.manual_entry.pitch import midi_to_hz, midi_to_pitch_name

DEFAULT_HARMONIC_RANGES = PACKAGE_ROOT / "configs" / "extrapolation_harmonic_ranges.yaml"
INSTRUMENTS_YAML = PACKAGE_ROOT / "configs" / "instruments.yaml"

SelectionMode = Literal[
    "configured_physically_plausible_harmonics",
    "upper_register_only",
    "custom_sounding_range",
    "selected_harmonic_orders",
]

_TOUCH_TO_ORDER = {"P4": 4, "M3": 5, "m3": 6, "P5": 3}
_ORDER_TO_TOUCH_SEMITONES = {3: 7, 4: 5, 5: 4, 6: 3}


def load_harmonic_range_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(resolve_path(path or DEFAULT_HARMONIC_RANGES))


def _open_strings(instrument: str) -> list[str]:
    inst = normalize_instrument(instrument)
    cfg = load_yaml(resolve_path(INSTRUMENTS_YAML))
    block = (cfg.get("instruments") or {}).get(inst) or {}
    strings = block.get("open_string_tuning") or block.get("open_string_tuning_sounding") or []
    return [str(s) for s in strings]


def _midi_label(midi: int | float | None) -> str | None:
    if midi is None:
        return None
    return midi_to_pitch_name(int(round(float(midi))))


def _cents_deviation(midi_float: float) -> float:
    return float((midi_float - round(midi_float)) * 100.0)


def _instrument_block(cfg: dict[str, Any], instrument: str, kind: str) -> dict[str, Any]:
    inst = normalize_instrument(instrument)
    key = "natural" if "natural" in kind else "artificial"
    reg = (cfg.get("harmonic_register") or {}).get(inst) or {}
    return dict(reg.get(key) or {})


def physical_sounding_bounds(
    instrument: str,
    harmonic_type: str,
    *,
    config: dict[str, Any] | None = None,
) -> tuple[float, float, str, str]:
    """Lowest/highest physically generated sounding MIDI for configured orders."""
    cfg = config or load_harmonic_range_config()
    defaults = cfg.get("defaults") or {}
    block = _instrument_block(cfg, instrument, harmonic_type)
    max_label = str(block.get("maximum_sounding_pitch") or defaults.get("maximum_sounding_pitch") or "C8")
    rmax = resolve_note(max_label)
    midi_max = float(rmax[1]) if rmax else 108.0
    opens = _open_strings(instrument)
    if not opens:
        return 0.0, midi_max, "C0", max_label
    open_midis = [resolve_note(s)[1] for s in opens if resolve_note(s)]
    if "natural" in harmonic_type:
        orders = [int(o) for o in (block.get("orders") or [2, 3, 4, 5, 6, 7, 8]) if int(o) >= 2]
        # Lowest physical natural: order-2 of lowest open string
        midi_min = float(min(open_midis) + 12)  # n=2 → +1 octave
        # Recompute from actual partials for accuracy
        lows: list[float] = []
        highs: list[float] = []
        for om in open_midis:
            f0 = midi_to_hz(om)
            if f0 is None:
                continue
            for order in orders:
                mf = 69.0 + 12.0 * math.log2((float(f0) * order) / 440.0)
                if mf <= midi_max + 1e-9:
                    lows.append(mf)
                    highs.append(mf)
        if lows:
            return min(lows), min(max(highs), midi_max), _midi_label(min(lows)) or "?", max_label
        return float(min(open_midis) + 12), midi_max, _midi_label(min(open_midis) + 12) or "?", max_label
    # Artificial: stopped from lowest open → sounding ≈ stopped + 24 for order 4
    order = int((block.get("orders") or [defaults.get("artificial_default_order") or 4])[0])
    offset = int(round(12.0 * math.log2(float(order))))
    midi_min = float(min(open_midis) + offset)
    return midi_min, midi_max, _midi_label(midi_min) or "?", max_label


def _resolve_filter_bounds(
    instrument: str,
    harmonic_type: str,
    *,
    selection_mode: SelectionMode,
    sounding_min: str | None,
    sounding_max: str | None,
    config: dict[str, Any],
) -> tuple[float | None, float | None, str | None, str | None]:
    """Return analysis/user filter bounds (None,None = no lower/upper analytical cut)."""
    defaults = config.get("defaults") or {}
    phys_min, phys_max, phys_min_l, phys_max_l = physical_sounding_bounds(
        instrument, harmonic_type, config=config
    )
    if selection_mode == "configured_physically_plausible_harmonics":
        return None, phys_max, None, phys_max_l
    if selection_mode == "upper_register_only":
        # Keep upper half of physical range as a soft analytical window
        mid = (phys_min + phys_max) / 2.0
        return mid, phys_max, _midi_label(mid), phys_max_l
    # custom_sounding_range or selected_harmonic_orders with explicit bounds
    max_label = sounding_max or phys_max_l or str(defaults.get("maximum_sounding_pitch") or "C8")
    rmax = resolve_note(str(max_label))
    midi_max = float(rmax[1]) if rmax else phys_max
    if sounding_min:
        rmin = resolve_note(str(sounding_min))
        midi_min = float(rmin[1]) if rmin else phys_min
        return midi_min, midi_max, rmin[0] if rmin else None, rmax[0] if rmax else max_label
    return None, midi_max, None, rmax[0] if rmax else max_label


def generate_natural_harmonic_targets(
    instrument: str,
    *,
    dynamic: str = "mf",
    sounding_min: str | None = None,
    sounding_max: str | None = None,
    include_low_harmonics: bool = True,
    orders: list[int] | None = None,
    quantity: str = "EWSD_score_acoustic_balanced",
    config: dict[str, Any] | None = None,
    selection_mode: SelectionMode | None = None,
    retain_excluded_by_analysis: bool | None = None,
) -> list[dict[str, Any]]:
    """Natural partials: f_n = n * f_open for each string and configured order."""
    cfg = config or load_harmonic_range_config()
    defaults = cfg.get("defaults") or {}
    mode: SelectionMode = selection_mode or defaults.get(  # type: ignore[assignment]
        "selection_mode", "configured_physically_plausible_harmonics"
    )
    if include_low_harmonics and mode == "custom_sounding_range" and sounding_min is None:
        mode = "configured_physically_plausible_harmonics"
    if not include_low_harmonics and sounding_min is None and mode == "configured_physically_plausible_harmonics":
        # Backward-compat: old flag False with no custom min → still physical (new default)
        mode = "configured_physically_plausible_harmonics"
    retain = (
        defaults.get("retain_excluded_by_analysis", False)
        if retain_excluded_by_analysis is None
        else retain_excluded_by_analysis
    )
    block = _instrument_block(cfg, instrument, "natural_harmonic")
    order_list = [int(o) for o in (orders or block.get("orders") or [2, 3, 4, 5, 6, 7, 8]) if int(o) >= 2]
    order_min = int(block.get("configured_order_min") or (min(order_list) if order_list else 2))
    order_max = int(block.get("configured_order_max") or (max(order_list) if order_list else 8))
    order_reason = str(defaults.get("order_selection_reason") or "practical_analysis_scope")
    phys_min, phys_max, phys_min_l, phys_max_l = physical_sounding_bounds(
        instrument, "natural_harmonic", config=cfg
    )
    filt_min, filt_max, anal_min_l, anal_max_l = _resolve_filter_bounds(
        instrument,
        "natural_harmonic",
        selection_mode=mode,
        sounding_min=sounding_min,
        sounding_max=sounding_max,
        config=cfg,
    )
    if sounding_max:
        r = resolve_note(sounding_max)
        if r:
            filt_max = float(r[1])
            anal_max_l = r[0]
    if mode == "custom_sounding_range" and sounding_min:
        r = resolve_note(sounding_min)
        if r:
            filt_min = float(r[1])
            anal_min_l = r[0]

    rows: list[dict[str, Any]] = []
    for open_name in _open_strings(instrument):
        resolved = resolve_note(open_name)
        if resolved is None:
            continue
        open_pitch, open_midi = resolved
        f0 = midi_to_hz(open_midi)
        if f0 is None:
            continue
        for order in order_list:
            freq = float(f0) * int(order)
            midi_float = 69.0 + 12.0 * math.log2(freq / 440.0)
            if midi_float > phys_max + 1e-6:
                continue
            nearest = int(round(midi_float))
            nearest_pitch = midi_to_pitch_name(nearest)
            if nearest_pitch is None:
                continue
            included_physical = True
            in_analysis = True
            excluded_reason = None
            target_status = "in_physical_and_analysis_range"
            if filt_min is not None and midi_float < filt_min - 1e-9:
                in_analysis = False
                excluded_reason = "excluded_by_analysis_scope"
                target_status = "excluded_by_analysis_scope"
            if filt_max is not None and midi_float > filt_max + 1e-9:
                in_analysis = False
                excluded_reason = "excluded_by_analysis_scope"
                target_status = "excluded_by_analysis_scope"
            if not in_analysis and not retain:
                continue
            rows.append(
                {
                    "note": nearest_pitch,
                    "midi": nearest,
                    "technique": "natural_harmonic",
                    "instrument": normalize_instrument(instrument),
                    "dynamic": str(dynamic).strip().lower(),
                    "quantity": quantity,
                    "harmonic_type": "natural_harmonic",
                    "string": open_pitch,
                    "open_string_pitch": open_pitch,
                    "harmonic_order": int(order),
                    "production_pitch": open_pitch,
                    "stopped_pitch": None,
                    "touched_pitch": None,
                    "sounding_pitch": nearest_pitch,
                    "sounding_midi": nearest,
                    "sounding_midi_float": float(midi_float),
                    "sounding_frequency_hz": freq,
                    "nearest_tempered_pitch": nearest_pitch,
                    "cents_deviation": _cents_deviation(midi_float),
                    "physical_range_min": phys_min_l,
                    "physical_range_max": phys_max_l,
                    "analysis_range_min": anal_min_l,
                    "analysis_range_max": anal_max_l or phys_max_l,
                    "target_range_min": anal_min_l or phys_min_l,
                    "target_range_max": anal_max_l or phys_max_l,
                    "within_harmonic_analysis_range": in_analysis,
                    "included_by_physical_model": included_physical,
                    "included_by_analysis_filter": in_analysis,
                    "excluded_reason": excluded_reason,
                    "target_status": target_status,
                    "feasibility_status": "physically_admissible_open_string_partial",
                    "pitch_generation_method": "natural_partial_n_times_open_frequency",
                    "selection_mode": mode,
                    "configuration_policy": "open_string_partials_configured_orders",
                    "configured_order_min": order_min,
                    "configured_order_max": order_max,
                    "order_selection_reason": order_reason,
                    "baseline_semantics": "sounding_pitch",
                    "metadata": {
                        "harmonic_generation": "natural_partial",
                        "selection_mode": mode,
                        "order_selection_reason": order_reason,
                    },
                }
            )
    rows.sort(key=lambda r: (float(r["sounding_midi_float"]), int(r["harmonic_order"]), str(r["string"])))
    return rows


def generate_artificial_harmonic_targets(
    instrument: str,
    *,
    dynamic: str = "mf",
    sounding_min: str | None = None,
    sounding_max: str | None = None,
    include_low_harmonics: bool = True,
    harmonic_order: int | None = None,
    touch_interval: str | None = None,
    quantity: str = "EWSD_score_acoustic_balanced",
    config: dict[str, Any] | None = None,
    selection_mode: SelectionMode | None = None,
    retain_excluded_by_analysis: bool | None = None,
) -> list[dict[str, Any]]:
    """Artificial targets from playable stopped pitches → sounding ≈ stopped + 12*log2(order)."""
    cfg = config or load_harmonic_range_config()
    defaults = cfg.get("defaults") or {}
    mode: SelectionMode = selection_mode or defaults.get(  # type: ignore[assignment]
        "selection_mode", "configured_physically_plausible_harmonics"
    )
    retain = (
        defaults.get("retain_excluded_by_analysis", False)
        if retain_excluded_by_analysis is None
        else retain_excluded_by_analysis
    )
    block = _instrument_block(cfg, instrument, "artificial_harmonic")
    order = int(
        harmonic_order
        or (block.get("orders") or [defaults.get("artificial_default_order") or 4])[0]
    )
    interval = str(touch_interval or block.get("touch_interval") or defaults.get("artificial_touch_interval") or "P4")
    config_policy = str(
        block.get("configuration_policy")
        or defaults.get("artificial_configuration_policy")
        or "canonical_single_string_assignment"
    )
    order_min = int(block.get("configured_order_min") or order)
    order_max = int(block.get("configured_order_max") or order)
    order_reason = str(defaults.get("order_selection_reason") or "practical_analysis_scope")
    # Artificial audit label is more specific than the shared natural mode name
    artificial_mode = (
        "configured_playable_stopped_to_sounding"
        if mode == "configured_physically_plausible_harmonics"
        else mode
    )
    stop_offset = int(round(12.0 * math.log2(float(order))))
    phys_min, phys_max, phys_min_l, phys_max_l = physical_sounding_bounds(
        instrument, "artificial_harmonic", config=cfg
    )
    filt_min, filt_max, anal_min_l, anal_max_l = _resolve_filter_bounds(
        instrument,
        "artificial_harmonic",
        selection_mode=mode,
        sounding_min=sounding_min,
        sounding_max=sounding_max,
        config=cfg,
    )
    if mode == "custom_sounding_range":
        if sounding_min:
            r = resolve_note(sounding_min)
            if r:
                filt_min = float(r[1])
                anal_min_l = r[0]
        if sounding_max:
            r = resolve_note(sounding_max)
            if r:
                filt_max = float(r[1])
                anal_max_l = r[0]

    opens = _open_strings(instrument)
    open_midis = [resolve_note(s)[1] for s in opens if resolve_note(s)]
    stopped_min = min(open_midis) if open_midis else 55
    stopped_max = (max(open_midis) + 24) if open_midis else 90

    # Sounding span from physical stopped range
    sound_lo = int(math.ceil(stopped_min + stop_offset))
    sound_hi = int(math.floor(min(stopped_max + stop_offset, phys_max)))

    rows: list[dict[str, Any]] = []
    for sounding_midi in range(sound_lo, sound_hi + 1):
        stopped_midi = sounding_midi - stop_offset
        if stopped_midi < stopped_min or stopped_midi > stopped_max:
            continue
        sounding_pitch = midi_to_pitch_name(sounding_midi)
        stopped_pitch = midi_to_pitch_name(stopped_midi)
        if sounding_pitch is None or stopped_pitch is None:
            continue
        string_name = None
        for open_name in reversed(opens):
            r = resolve_note(open_name)
            if r is not None and r[1] <= stopped_midi:
                string_name = r[0]
                break
        if string_name is None and opens:
            rr = resolve_note(opens[0])
            string_name = rr[0] if rr else opens[0]
        touched_midi = stopped_midi + _ORDER_TO_TOUCH_SEMITONES.get(order, 5)
        touched_pitch = midi_to_pitch_name(touched_midi)
        freq = midi_to_hz(sounding_midi)
        midi_float = float(sounding_midi)
        in_analysis = True
        excluded_reason = None
        target_status = "in_physical_and_analysis_range"
        if filt_min is not None and midi_float < filt_min - 1e-9:
            in_analysis = False
            excluded_reason = "excluded_by_analysis_scope"
            target_status = "excluded_by_analysis_scope"
        if filt_max is not None and midi_float > filt_max + 1e-9:
            in_analysis = False
            excluded_reason = "excluded_by_analysis_scope"
            target_status = "excluded_by_analysis_scope"
        if not in_analysis and not retain:
            continue
        rows.append(
            {
                "note": sounding_pitch,
                "midi": sounding_midi,
                "technique": "artificial_harmonic",
                "instrument": normalize_instrument(instrument),
                "dynamic": str(dynamic).strip().lower(),
                "quantity": quantity,
                "harmonic_type": "artificial_harmonic",
                "string": string_name,
                "open_string_pitch": string_name,
                "harmonic_order": order,
                "production_pitch": stopped_pitch,
                "stopped_pitch": stopped_pitch,
                "touched_pitch": touched_pitch,
                "touch_interval": interval,
                "sounding_pitch": sounding_pitch,
                "sounding_midi": sounding_midi,
                "sounding_midi_float": midi_float,
                "sounding_frequency_hz": freq,
                "nearest_tempered_pitch": sounding_pitch,
                "cents_deviation": 0.0,
                "physical_range_min": phys_min_l,
                "physical_range_max": phys_max_l,
                "analysis_range_min": anal_min_l,
                "analysis_range_max": anal_max_l or phys_max_l,
                "target_range_min": anal_min_l or phys_min_l,
                "target_range_max": anal_max_l or phys_max_l,
                "within_harmonic_analysis_range": in_analysis,
                "included_by_physical_model": True,
                "included_by_analysis_filter": in_analysis,
                "excluded_reason": excluded_reason,
                "target_status": target_status,
                "feasibility_status": "stopped_pitch_in_instrument_range",
                "pitch_generation_method": "artificial_from_playable_stopped_pitch",
                "selection_mode": artificial_mode,
                "configuration_policy": config_policy,
                "configured_order_min": order_min,
                "configured_order_max": order_max,
                "order_selection_reason": order_reason,
                "baseline_semantics": "sounding_pitch",
                "metadata": {
                    "harmonic_generation": "artificial_from_stopped_range",
                    "selection_mode": artificial_mode,
                    "configuration_policy": config_policy,
                },
            }
        )
    return rows


def generate_harmonic_targets(
    instrument: str,
    harmonic_type: str,
    *,
    dynamic: str = "mf",
    sounding_min: str | None = None,
    sounding_max: str | None = None,
    include_low_harmonics: bool = True,
    quantity: str = "EWSD_score_acoustic_balanced",
    config: dict[str, Any] | None = None,
    selection_mode: SelectionMode | None = None,
    retain_excluded_by_analysis: bool | None = None,
) -> list[dict[str, Any]]:
    tech = str(harmonic_type).strip().lower()
    # Legacy flag: include_low_harmonics=False + explicit sounding_min → custom window
    mode = selection_mode
    if mode is None and sounding_min and not include_low_harmonics:
        mode = "custom_sounding_range"
    if tech == "natural_harmonic":
        return generate_natural_harmonic_targets(
            instrument,
            dynamic=dynamic,
            sounding_min=sounding_min,
            sounding_max=sounding_max,
            include_low_harmonics=include_low_harmonics,
            quantity=quantity,
            config=config,
            selection_mode=mode,
            retain_excluded_by_analysis=retain_excluded_by_analysis,
        )
    if tech == "artificial_harmonic":
        return generate_artificial_harmonic_targets(
            instrument,
            dynamic=dynamic,
            sounding_min=sounding_min,
            sounding_max=sounding_max,
            include_low_harmonics=include_low_harmonics,
            quantity=quantity,
            config=config,
            selection_mode=mode,
            retain_excluded_by_analysis=retain_excluded_by_analysis,
        )
    raise ValueError(f"Unsupported harmonic_type: {harmonic_type!r}")


def annotate_baseline_extrapolation(
    target: dict[str, Any],
    *,
    baseline_midi_min: float | None,
    baseline_midi_max: float | None,
    limited_semitones: float = 3.0,
    physical_semitones: float = 12.0,
) -> dict[str, Any]:
    """Mark whether sounding pitch lies outside the ordinary baseline domain."""
    out = dict(target)
    sm = out.get("sounding_midi_float", out.get("sounding_midi", out.get("midi")))
    if sm is None or baseline_midi_min is None or baseline_midi_max is None:
        out["within_ordinary_baseline_range"] = None
        out["outside_ordinary_baseline_range"] = None
        out["baseline_extrapolation_semitones"] = None
        return out
    smf = float(sm)
    if baseline_midi_min <= smf <= baseline_midi_max:
        out["within_ordinary_baseline_range"] = True
        out["outside_ordinary_baseline_range"] = False
        out["baseline_extrapolation_semitones"] = 0.0
        out["baseline_support_policy"] = "inside_ordinary_baseline"
        return out
    dist = smf - baseline_midi_max if smf > baseline_midi_max else baseline_midi_min - smf
    out["within_ordinary_baseline_range"] = False
    out["outside_ordinary_baseline_range"] = True
    out["baseline_extrapolation_semitones"] = float(dist)
    if dist <= limited_semitones:
        out["baseline_support_policy"] = "limited_out_of_domain_uncertainty_inflated"
    elif dist <= physical_semitones:
        out["baseline_support_policy"] = "requires_physical_spectral_or_explicit_assumption"
    else:
        out["baseline_support_policy"] = "default_unavailable_beyond_12_semitones"
    return out
