"""Build a full ordinary pitch register for manual value entry."""

from __future__ import annotations

import re
from typing import Any

from string_technique_model.extrapolation.baselines import normalize_instrument
from string_technique_model.pitch.registry import get_default_pitch_registry, load_instrument_midi_ranges

# European decimal: 70,623528 or 70.623528
_NUM_RE = re.compile(r"^[+-]?(?:\d+[.,]\d+|\d+)$")
# Scientific pitch-ish: C3, C#3, Db4, A4…
_NOTE_RE = re.compile(r"^[A-Ga-g](?:#|b|♯|♭)?-?\d+$")


def _norm_note(label: str) -> str:
    s = str(label).strip().replace("♯", "#").replace("♭", "b").replace(" ", "")
    # Capitalize letter
    if s:
        s = s[0].upper() + s[1:]
    return s


def parse_number(cell: str) -> float | None:
    """Parse a numeric cell; accepts European comma decimals (70,623528)."""
    if cell is None:
        return None
    s = str(cell).strip()
    if not s or s.lower() in {"na", "nan", "none", "-", ""}:
        return None
    # thousand-dot + decimal-comma: 1.234,56 → strip dots then comma→dot
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+,\d+", s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # plain European decimal
        s = s.replace(",", ".")
    elif "," in s and "." in s and s.rfind(",") > s.rfind("."):
        # 1.234,56 already handled above; 1,234.56 US style
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def resolve_note(label: str) -> tuple[str, int] | None:
    """Return (canonical_scientific_pitch, midi) or None if unknown."""
    reg = get_default_pitch_registry()
    p = reg.get_by_spelling(_norm_note(label))
    if p is None:
        return None
    return p.scientific_pitch, p.midi


def build_register_from_note_list(
    note_names: list[str],
    instrument: str,
    dynamic: str,
    *,
    values: list[float | None] | None = None,
    quantity: str = "EWSD_score_acoustic_balanced",
    technique: str = "ordinary",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build register from an explicit list of note names (user-inputted notes)."""
    inst = normalize_instrument(instrument)
    dyn = str(dynamic).strip().lower()
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for i, raw in enumerate(note_names):
        if raw is None or str(raw).strip() == "":
            warnings.append(f"row {i+1}: empty note skipped")
            continue
        resolved = resolve_note(str(raw))
        if resolved is None:
            warnings.append(f"row {i+1}: note {raw!r} not recognised — kept as typed")
            note = _norm_note(str(raw))
            midi = None
        else:
            note, midi = resolved
        val = None
        if values is not None and i < len(values):
            val = values[i]
        rows.append(
            {
                "note": note,
                "midi": midi,
                "value": val,
                "instrument": inst,
                "dynamic": dyn,
                "technique": technique,
                "quantity": quantity,
                "metadata": {"input_note": str(raw)},
            }
        )
    if not rows:
        warnings.append("no notes accepted from input list")
    else:
        warnings.append(f"accepted {len(rows)} inputted notes")
    return rows, warnings


def build_register_from_notes(
    start_note: str,
    end_note: str,
    instrument: str,
    dynamic: str,
    *,
    quantity: str = "EWSD_score_acoustic_balanced",
    technique: str = "ordinary",
) -> list[dict[str, Any]]:
    """Chromatic register from start_note to end_note inclusive (e.g. G3→G7)."""
    inst = normalize_instrument(instrument)
    dyn = str(dynamic).strip().lower()
    a = resolve_note(start_note)
    b = resolve_note(end_note)
    if a is None or b is None:
        raise ValueError(
            f"Unknown note range: {start_note!r} … {end_note!r}. "
            "Use spellings like G3, G#3, Ab3, C6."
        )
    lo, hi = (a[1], b[1]) if a[1] <= b[1] else (b[1], a[1])
    reg = get_default_pitch_registry()
    rows: list[dict[str, Any]] = []
    for midi in range(lo, hi + 1):
        p = reg.get_by_midi(midi)
        if p is None:
            continue
        rows.append(
            {
                "note": p.scientific_pitch,
                "midi": p.midi,
                "value": None,
                "instrument": inst,
                "dynamic": dyn,
                "technique": technique,
                "quantity": quantity,
                "metadata": {},
            }
        )
    return rows


def build_empty_register(
    instrument: str,
    dynamic: str,
    *,
    quantity: str = "EWSD_score_acoustic_balanced",
    technique: str = "ordinary",
    show_all_midi: bool = False,
    start_note: str | None = None,
    end_note: str | None = None,
) -> list[dict[str, Any]]:
    """Instrument sounding range, or explicit start_note…end_note when given."""
    if start_note and end_note:
        return build_register_from_notes(
            start_note,
            end_note,
            instrument,
            dynamic,
            quantity=quantity,
            technique=technique,
        )
    inst = normalize_instrument(instrument)
    dyn = str(dynamic).strip().lower()
    reg = get_default_pitch_registry()
    ranges = load_instrument_midi_ranges()
    pitches = reg.filter_instrument_range(inst, show_all=show_all_midi, instrument_ranges=ranges)
    return [
        {
            "note": p.scientific_pitch,
            "midi": p.midi,
            "value": None,
            "instrument": inst,
            "dynamic": dyn,
            "technique": technique,
            "quantity": quantity,
            "metadata": {},
        }
        for p in pitches
    ]


def merge_values_into_register(
    register: list[dict[str, Any]],
    values_by_note: dict[str, float],
) -> list[dict[str, Any]]:
    """Fill register values from a note→value map (case-insensitive note keys)."""
    lookup = {_norm_note(k).upper(): float(v) for k, v in values_by_note.items()}
    out: list[dict[str, Any]] = []
    for row in register:
        key = _norm_note(str(row["note"])).upper()
        new = dict(row)
        if key in lookup:
            new["value"] = lookup[key]
        out.append(new)
    return out


def apply_value_list(
    register: list[dict[str, Any]],
    values: list[float | None],
    *,
    start_index: int = 0,
) -> list[dict[str, Any]]:
    """Paste a column of values onto the register in order (whole-register entry)."""
    out = [dict(r) for r in register]
    for offset, val in enumerate(values):
        idx = start_index + offset
        if idx >= len(out):
            break
        out[idx]["value"] = val
    return out


def measured_with_values_only(register: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only rows where the user entered a numeric value."""
    kept: list[dict[str, Any]] = []
    for row in register:
        if row.get("value") is None:
            continue
        try:
            float(row["value"])
        except (TypeError, ValueError):
            continue
        kept.append(row)
    return kept


TECHNIQUE_SORT_ORDER: tuple[str, ...] = (
    "con_sordino",
    "sul_tasto",
    "sul_ponticello",
    "artificial_harmonic",
    "natural_harmonic",
    "ordinary",
)


def generate_requests_for_register(
    measured: list[dict[str, Any]],
    techniques: list[str],
    *,
    only_notes_with_values: bool = True,
    harmonic_sounding_min: str | None = None,
    harmonic_sounding_max: str | None = None,
    include_low_harmonics: bool = True,
    harmonic_selection_mode: str | None = None,
) -> list[dict[str, Any]]:
    """Request each technique for filled notes, grouped by technique then note.

    Harmonic techniques use modal sounding targets (partials / artificial map),
    not a copy of the ordinary chromatic register.
    """
    rows = measured_with_values_only(measured) if only_notes_with_values else measured
    ordered_techs = [t for t in TECHNIQUE_SORT_ORDER if t in techniques]
    ordered_techs += [t for t in techniques if t not in ordered_techs]
    requests: list[dict[str, Any]] = []
    harmonic_techs = {"natural_harmonic", "artificial_harmonic"}
    for tech in ordered_techs:
        if tech in harmonic_techs:
            if not rows:
                continue
            inst = str(rows[0].get("instrument") or "vln")
            dyn = str(rows[0].get("dynamic") or "mf")
            qty = rows[0].get("quantity") or "EWSD_score_acoustic_balanced"
            from string_technique_model.extrapolation.nonlinear.harmonic_register import (
                generate_harmonic_targets,
            )

            for ht in generate_harmonic_targets(
                inst,
                tech,
                dynamic=dyn,
                sounding_min=harmonic_sounding_min,
                sounding_max=harmonic_sounding_max,
                include_low_harmonics=include_low_harmonics,
                quantity=str(qty),
                selection_mode=harmonic_selection_mode,  # type: ignore[arg-type]
            ):
                requests.append(
                    {
                        "note": ht.get("sounding_pitch") or ht.get("note"),
                        "technique": tech,
                        "instrument": ht.get("instrument") or inst,
                        "dynamic": dyn,
                        "quantity": qty,
                        "harmonic_type": ht.get("harmonic_type"),
                        "string": ht.get("string"),
                        "harmonic_order": ht.get("harmonic_order"),
                        "stopped_pitch": ht.get("stopped_pitch"),
                        "touched_pitch": ht.get("touched_pitch"),
                        "sounding_pitch": ht.get("sounding_pitch"),
                        "sounding_midi_float": ht.get("sounding_midi_float"),
                        "cents_deviation": ht.get("cents_deviation"),
                        "pitch_generation_method": ht.get("pitch_generation_method"),
                        "metadata": dict(ht.get("metadata") or {}),
                    }
                )
            continue
        for row in rows:
            requests.append(
                {
                    "note": row["note"],
                    "technique": tech,
                    "instrument": row["instrument"],
                    "dynamic": row["dynamic"],
                    "quantity": row.get("quantity") or "EWSD_score_acoustic_balanced",
                    "metadata": {},
                }
            )
    # Sort notes within each technique block by MIDI
    def note_midi(note: str | None) -> int:
        if not note:
            return 9999
        resolved = resolve_note(str(note))
        return resolved[1] if resolved else 9999

    return sorted(
        requests,
        key=lambda r: (
            TECHNIQUE_SORT_ORDER.index(r["technique"])
            if r["technique"] in TECHNIQUE_SORT_ORDER
            else 99,
            note_midi(r.get("note")),
            str(r.get("note") or ""),
        ),
    )


def _split_line_cells(line: str) -> list[str]:
    """Split a pasted line into cells without breaking European decimals."""
    line = line.strip()
    if not line:
        return []
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    if ";" in line:
        return [c.strip() for c in line.split(";")]
    # space-separated note + number: "C3 70,623528"
    parts = line.split()
    if len(parts) == 2 and _NOTE_RE.match(parts[0].replace("♯", "#").replace("♭", "b")):
        return parts
    # single cell (value-only column, or "note,value" with US decimals only)
    if "," in line:
        left, right = line.split(",", 1)
        # "C3,70,623528" is ambiguous; prefer note + european number if left looks like note
        # and full line after first comma is a european number when rejoined... 
        # Better: if left is note and parse_number(rest) works with comma kept:
        if _NOTE_RE.match(left.strip().replace("♯", "#").replace("♭", "b")):
            rest = line[len(left) + 1 :].strip()
            if parse_number(rest) is not None:
                return [left.strip(), rest]
        # otherwise treat whole line as one European number
        return [line]
    return [line]


def parse_pasted_note_value_table(text: str) -> tuple[list[str | None], list[float | None], list[str]]:
    """Parse pasted text as value column, or note+value columns.

    Accepts European decimals: 70,623528
    Returns (notes_or_none, values, warnings).
    """
    notes: list[str | None] = []
    values: list[float | None] = []
    warnings: list[str] = []
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # drop leading/trailing empty lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return [], [], ["empty paste"]

    # skip header if present
    first_cells = _split_line_cells(lines[0])
    if first_cells and any(c.lower() in {"note", "value", "ewsd", "ewsd_score_acoustic_balanced"} for c in first_cells):
        lines = lines[1:]

    two_col = 0
    for line in lines:
        if not line.strip():
            notes.append(None)
            values.append(None)
            continue
        cells = _split_line_cells(line)
        if len(cells) >= 2:
            n_raw, v_raw = cells[0], cells[1]
            note = _norm_note(n_raw) if _NOTE_RE.match(n_raw.replace("♯", "#").replace("♭", "b")) else None
            val = parse_number(v_raw)
            if note is None and parse_number(n_raw) is not None and _NOTE_RE.match(
                v_raw.replace("♯", "#").replace("♭", "b")
            ):
                # swapped columns
                note = _norm_note(v_raw)
                val = parse_number(n_raw)
            notes.append(note)
            values.append(val)
            if note is not None:
                two_col += 1
        else:
            cell = cells[0] if cells else ""
            if _NOTE_RE.match(cell.replace("♯", "#").replace("♭", "b")) and parse_number(cell) is None:
                notes.append(_norm_note(cell))
                values.append(None)
            else:
                notes.append(None)
                values.append(parse_number(cell))

    if two_col:
        warnings.append(f"parsed {two_col} note+value rows (European decimals accepted)")
    else:
        warnings.append(f"parsed {sum(v is not None for v in values)} value-only rows (European decimals accepted)")
    return notes, values, warnings


def parse_pasted_values(text: str) -> list[float | None]:
    """Parse clipboard/text: one European/US number per line."""
    _notes, values, _w = parse_pasted_note_value_table(text)
    return values


def apply_pasted_table(
    register: list[dict[str, Any]],
    text: str,
    *,
    start_index: int = 0,
    instrument: str | None = None,
    dynamic: str | None = None,
    rebuild_from_pasted_notes: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply paste.

    - If note names are present: rebuild the register from those notes (accept user input).
    - Else: fill values in order onto the existing note column.
    """
    notes, values, warnings = parse_pasted_note_value_table(text)
    pasted_notes = [n for n in notes if n]
    inst = instrument or (register[0]["instrument"] if register else "vln")
    dyn = dynamic or (register[0]["dynamic"] if register else "pp")

    if pasted_notes and rebuild_from_pasted_notes:
        # Align values to original line indices for notes that survived
        aligned_vals: list[float | None] = []
        for n, v in zip(notes, values):
            if n:
                aligned_vals.append(v)
        out, w2 = build_register_from_note_list(
            pasted_notes, inst, dyn, values=aligned_vals
        )
        warnings.extend(w2)
        warnings.append("register rebuilt from your inputted note names")
        return out, warnings

    if pasted_notes:
        named = {n: v for n, v in zip(notes, values) if n and v is not None}
        out = merge_values_into_register(register, named)
        warnings.append(f"matched {len(named)} values by note name onto existing register")
        return out, warnings

    out = apply_value_list(register, values, start_index=start_index)
    n_fill = sum(1 for v in values if v is not None)
    if n_fill != len(register):
        warnings.append(
            f"value count ({n_fill}) differs from note column ({len(register)}). "
            "Click Build note column with the correct From/To (e.g. G3→G7), then paste again."
        )
    else:
        warnings.append(f"filled {n_fill} values onto existing note column")
    return out, warnings
