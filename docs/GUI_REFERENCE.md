# GUI Reference

This reference describes the current primary graphical interface, its
implementation module, the layout of every tab, and the controls exposed
to the user.

The application is a Tkinter desktop program. It performs **no audio
processing** and requires no audio files. All computation is numerical.

## Implementation

- Module: `src/string_technique_model/gui_metadata/extrapolator_app.py`
- Class: `NarrowExtrapolatorApp`
- Entry point: `string-technique-model gui`, which invokes
  `string_technique_model.gui.launch_gui()` and ultimately
  `launch_extrapolator_gui()`.

Two other interfaces remain in the repository but are marked
legacy/secondary:

- [METADATA_ENTRY_GUI.md](METADATA_ENTRY_GUI.md)
- [NARROW_EXTRAPOLATION_GUI.md](NARROW_EXTRAPOLATION_GUI.md)

## Window

The main window title is exactly:

```
Manual register → technique requests
```

The default geometry is `1280 × 840` with a minimum size of
`1100 × 720`. On Windows the Tk `vista` theme is used when available.

## Menu bar

| Menu | Item | Effect |
|------|------|--------|
| `File` | `Save Measured register…` | Save the current register to an Excel workbook (sheets `Measured` and `Requests`). |
| `File` | `Load Measured register…` | Load a workbook and stamp provenance metadata on the loaded rows. |
| `File` | `Export results to Excel…` | Export the last result set (nonlinear workbook by preference). |
| `File` | `Open last Excel export` | Reveal the last exported workbook in the operating system. |
| `File` | `Return to start (edit & re-run)…` | Clear requests and results while preserving the measured register. |
| `File` | `Exit` | Close the application. |

## Top bar

The top bar shows an instruction line and the meta / method controls:

| Control | Purpose |
|---------|---------|
| `Instrument` combobox | `vln`, `vla`, `vlc`, `cb` (readonly). |
| `Dynamic` combobox | `pp`, `mf`, `ff` (readonly). |
| `From note` / `To note` entries | Register endpoints in scientific pitch notation. |
| `Build note column` button | Rebuild the register between `From` and `To`. |
| `Paste notes and/or values` button | Open a dialog to paste values (or `note<TAB>value` rows). |
| `Clear values` button | Set every `value` cell to `None`. |
| `Extrapolation method` combobox | `hierarchical_spline` (default), `constant`, `physical_informed_bayesian`, `evidence_only`. |

The `hierarchical_spline` selection is mapped to
`requested_method=automatic` in the exported Excel `Run_Summary` sheet, so
that automatic model selection is visible in the audit trail.

## Next-step banner

A `Next steps` label indicates the recommended action based on the current
state (paste values, generate requests, run, or export). Two buttons are
attached:

- `▶ Do next step` — advance one step in the workflow (build → generate →
  run).
- `← Return to start` — go back to tab 1 while keeping measured values.

## Tabs

There are three tabs, each with a numbered title.

### Tab 1 — `1. Measured register (type values)`

- The register grid supports direct editing of every cell, including note
  labels (double-click). Editing is provided by `RegisterGrid` in
  `src/string_technique_model/gui_metadata/register_grid.py`.
- A dedicated button navigates to tab 2 once at least one value has been
  provided.

### Tab 2 — `2. Requests (notes + techniques)`

- **Techniques** panel: one checkbox per technique. The order is fixed to
  `con_sordino`, `sul_tasto`, `sul_ponticello`, `artificial_harmonic`,
  `natural_harmonic`, matching the export block order.
- **Harmonic output range** panel:
  - `Use physically available harmonic range` checkbox — when enabled, the
    generator enumerates configured open string × order combinations up to
    the sounding-pitch ceiling defined in
    `configs/extrapolation_harmonic_ranges.yaml`.
  - `From` and `To` sounding-pitch entries; `To` defaults to `C8`.
  - `Mode` combobox with four options:
    - `configured_physically_plausible_harmonics`
    - `upper_register_only`
    - `custom_sounding_range`
    - `selected_harmonic_orders`
- `Generate from filled register` button generates one request per filled
  note × technique. Harmonic requests are generated from the sounding-pitch
  geometry rather than by copying the ordinary chromatic notes.

### Tab 3 — `3. Results`

- A results treeview mirrors the exported columns for
  `request_technique`, `request_note`, `instrument`, `dynamic`,
  `baseline_value`, `value`, `lower_bound`, `upper_bound`, `value_kind`,
  `qualitative_effect_vs_ordinary`, `attenuation_db_power`,
  `extrapolation_method`, and `warnings`.
- Buttons: `Run requests`, `Export to Excel…`, `Open Excel`, and
  `← Return to start`.
- The output path entry is prefilled with the default
  `outputs/extrapolation/note_level_requests.xlsx`. When the pipeline runs
  under an M1 method the exporter automatically switches the filename to
  `nonlinear_extrapolation_results.xlsx` unless the user path already
  contains `nonlinear`.

## Status bar

The bottom status bar shows two labels:

- `Register notes: N | Filled values: N | Requests: N`
- A free-form status message that mirrors the last action.

## Provenance stamped on rows

The application stamps every measured row with provenance information at
run time:

- Rows imported from a workbook receive `data_status=measured_research_data`,
  `scientific_use=allowed_with_workbook_provenance`, together with
  `source_workbook_path`, `source_workbook_hash`, `source_sheet`,
  `import_run_id`, and `source_path`.
- Rows entered manually receive `data_status=manual_register_entry` and
  `scientific_use=requires_source_workbook_for_doctoral_evidence`, plus a
  synthetic `source_path` derived from the note and the current instrument.

These fields are preserved in every export sheet and are the primary basis
for the doctoral audit trail described in
[USER_GUIDE.md](USER_GUIDE.md#7-provenance-warnings-for-doctoral-use).

## Return to start

The `← Return to start` button (also available as
`File → Return to start (edit & re-run)…`) clears the request grid and the
result set and returns to tab 1. The measured register values are kept so
that the user can re-run with a different technique selection or method
without re-entering the register.

## Method combobox mapping

The GUI displays `hierarchical_spline` as the default method name. When
requests are executed with this method, the run metadata written to the
Excel workbook records:

- `requested_method=automatic`
- `gui_displayed_method=hierarchical_spline`
- `effective_selection_mode=automatic`

For every other method the displayed and requested names are identical.

## Related documents

- [USER_GUIDE.md](USER_GUIDE.md) — end-to-end workflow.
- [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) — output columns.
- [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) — schema definitions.
- [NOTE_LEVEL_REQUESTS.md](NOTE_LEVEL_REQUESTS.md) — request format.
- [METADATA_ENTRY_GUI.md](METADATA_ENTRY_GUI.md) — legacy metadata sheet
  (secondary interface).
- [NARROW_EXTRAPOLATION_GUI.md](NARROW_EXTRAPOLATION_GUI.md) — legacy narrow
  extrapolator wording (secondary interface).
