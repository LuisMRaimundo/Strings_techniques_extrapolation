# Metadata Entry GUI (legacy sheet)

> **Note:** The main `python -m string_technique_model gui` entry now opens the
> **[Narrow Extrapolator — numerical metadata](NARROW_EXTRAPOLATION_GUI.md)** window.
> The recording/metadata sheet below is secondary (Tools → Legacy recording metadata sheet…).
> It is not needed for the ST/SP/sordino numerical extrapolation workflow, and it is not an audio analyser.

## Launch (legacy sheet only)

```bash
python -c "from string_technique_model.gui_metadata.app import launch_metadata_gui; launch_metadata_gui()"
```

## Primary workflow

1. **New** or **Open** a metadata collection.
2. **Add Record** — one row per analysis unit.
3. Enter metadata in the table and/or the compact record editor.
4. **Validate**.
5. **Save** / **Export** (JSON, CSV, or Parquet when available).

## Main window

| Area | Contents |
|------|----------|
| Toolbar | New, Open, Save, Import, Export, Validate |
| Table | Spreadsheet-style grid (sort, filter, copy/paste, fill-down, column visibility) |
| Editor | Selected-row form (can be hidden under View) |
| Status bar | Record counts, validation tallies, current file |

## Core fields

Record ID, audio/source file, instrument, technique summary, dynamic, pitch mode, pitch information, string, performer, take, notes.

Missing values stay **explicitly unknown/null**. Nothing is silently filled with defaults such as `mf`.

## Pitch modes

| Mode | Behaviour |
|------|-----------|
| `single_note` | Pitch name, octave, accidental, MIDI, written/sounding |
| `pitch_range` | Lowest / highest pitch |
| `multiple_notes` | Searchable multi-pitch list, optional order |
| `open_string` | String, tuning, written and sounding |
| `unpitched_or_noise` | No pitch forced |
| `unknown` | Pitch fields remain null |

### Complete pitch registry

MIDI **0–127** chromatic registry with scientific pitch notation, frequency (A4=440 Hz), and enharmonic spellings. Instrument-range filtering uses `configs/instruments.yaml` and can be disabled for extended techniques / scordatura.

### Written vs sounding

Choose representation: written, sounding, both, or unresolved. Derivations are recorded; originals are not overwritten.

## Technique combination

Separate selectors for left-hand regime, bow-contact regime, mute state, articulation, and additional technique. A summary label is generated, e.g. `artificial harmonic + sul ponticello + con sordino`.

Harmonic, bow-contact, mute, multiphonic, and recording panels are collapsible and shown only when relevant / requested.

## Validation levels

- **Error** — invalid pitch, nonpositive speaking length, inconsistent harmonic interval/order, bad mute mass, malformed path.
- **Warning** — outside instrument range, ambiguous harmonic notation, incomplete technique, unresolved written/sounding.
- **Information** — derived MIDI/frequency, optional recording metadata absent.

## Legacy migration

Rows with a single pitch field load as `pitch_mode = single_note` with migration provenance. Null pitches become `pitch_mode = unknown` unless explicitly unpitched. Ranges are never inferred from isolated notes.

## Schema

`metadata_entry_v1`, compatible with the repository `CanonicalRecord` projection.
