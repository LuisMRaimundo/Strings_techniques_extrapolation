# User Guide

This guide describes the recommended end-to-end workflow for the string
technique density model: from installing the package, entering a measured
register in the GUI, generating technique requests, running the extrapolation
pipeline, and interpreting the exported Excel workbook.

The workflow is deliberately conservative. Values that cannot be justified by
either measured ordinary data or an explicitly declared assumption remain
`NA`, and the corresponding audit fields state the reason.

## 1. Installation

The package targets Python 3.10 or newer. Install from the repository root:

```bat
python -m pip install -e ".[dev]"
```

The optional Bayesian backend is not required for the default workflow:

```bat
python -m pip install -e ".[bayes]"
```

When the Bayesian backend is unavailable, the pipeline still runs and simply
labels the produced intervals as `assumption_distribution_interval` rather
than `credible_interval` (see [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md)).

## 2. Launching the primary GUI

Only one GUI is officially supported for the day-to-day workflow:

```bat
python -m string_technique_model gui
```

The window title is `Manual register → technique requests` and the
implementation resides in
`src/string_technique_model/gui_metadata/extrapolator_app.py`. The former
`Narrow Extrapolator` and `Metadata Entry` windows are retained for
compatibility only and are documented as
[legacy](NARROW_EXTRAPOLATION_GUI.md) [secondary](METADATA_ENTRY_GUI.md)
interfaces.

The screen-by-screen reference is [GUI_REFERENCE.md](GUI_REFERENCE.md).

## 3. Measured register (tab 1)

1. Choose the instrument (`vln`, `vla`, `vlc`, `cb`) and the dynamic (`pp`,
   `mf`, `ff`).
2. Set the register endpoints in the `From note` and `To note` fields (for
   example `G3` to `G7`) and click `Build note column`.
3. Enter the ordinary EWSD values in the `value` column. You may:
   - type each value directly;
   - paste a values-only column via `Paste notes and/or values`; or
   - paste a `note<TAB>value` table (accepted by the parser).

European decimal commas are accepted (`70,623528` is treated as
`70.623528`).

Each row is stamped with provenance metadata. Manually entered rows are
labelled `data_status=manual_register_entry` with
`scientific_use=requires_source_workbook_for_doctoral_evidence`, whereas
rows imported from a workbook are labelled `data_status=measured_research_data`
with `scientific_use=allowed_with_workbook_provenance` and carry the source
workbook path, hash, and import run ID.

## 4. Requests (tab 2)

Requests describe the notes and techniques whose EWSD you want to estimate.

1. Tick the techniques to request for all filled notes. The available
   techniques are `con_sordino`, `sul_tasto`, `sul_ponticello`,
   `artificial_harmonic`, and `natural_harmonic`.
2. Configure the harmonic output range. The controls are:
   - `Use physically available harmonic range` (checkbox) — enable to force
     the generator to enumerate configured open string × order combinations up
     to the ceiling in `configs/extrapolation_harmonic_ranges.yaml`.
   - `From` / `To` — sounding-pitch bounds (`To` defaults to `C8`).
   - `Mode` — one of
     `configured_physically_plausible_harmonics`,
     `upper_register_only`,
     `custom_sounding_range`, or
     `selected_harmonic_orders`.
3. Choose the extrapolation method in the top bar. `hierarchical_spline` is
   mapped internally to `requested_method=automatic` when exported;
   `constant`, `physical_informed_bayesian`, and `evidence_only` are also
   available.
4. Click `Generate from filled register`. Non-harmonic techniques copy each
   ordinary note as a request; harmonic techniques instead enumerate
   sounding pitches that arise from `n · f₀` combinations subject to the
   range and mode above (ordinary chromatic pitches are never silently
   copied onto harmonic techniques).

## 5. Run and export (tab 3)

1. Click `Run requests`.
2. Inspect the results table. Column meanings are given in
   [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md).
3. Click `Export to Excel…`. The default filename is
   `nonlinear_extrapolation_results.xlsx`; the export writes multiple
   audit sheets, including `Model_Selection_Audit`, `Run_Summary`,
   `Priors_Used`, `Diagnostics`, and per-technique sheets.

The `← Return to start` button (top bar and File menu) clears the request and
result state while preserving the measured register, so that the researcher
can adjust the input values or the ticked techniques and re-run.

## 6. Interpreting the results

### 6.1 `value_kind`

Each row carries a `value_kind` field with one of the following values
(defined in `src/string_technique_model/extrapolation/nonlinear/domain.py`):

| Value | Meaning |
|-------|---------|
| `measured` | Recorded ordinary observation. |
| `derived_from_measured` | Derived by a documented transformation of measurements. |
| `extrapolated` | Predicted from a fitted or hierarchical submodel. |
| `approximate_from_penalized_fit` | Interval width uses the penalized fit approximation, not classical inference. |
| `assumption_based_extrapolation` | Value depends on an activated user assumption or regularization prior. |
| `qualitative_only` | No admissible numerical model; qualitative tendency only. |
| `unavailable` | No admissible numerical model and no qualitative estimate. |

### 6.2 `NA` and `na_reason`

When the pipeline refuses to produce a numerical value, the exporter fills
`na_reason` with a stable identifier explaining why. The most common values
are:

| `na_reason` | Origin |
|-------------|--------|
| `insufficient_harmonic_metadata` | Modal geometry is incomplete; the harmonic gate refused a numeric answer. |
| `no_harmonic_acoustic_calibration_data` | Modal frequencies were generated but no calibrated harmonic descriptor model exists. |
| `excluded_by_analysis_scope` | The requested target was outside the configured analysis range. |

Refer to [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) for the
complete list of gating fields.

### 6.3 Assumptions

Numerical rows produced under an assumption are labelled with:

- `alpha_origin` — for example `regularization_assumption` or
  `user_assumption`;
- `assumption_ids` — only identifiers matching `ASSUMP_*`;
- `assumptions_trace` — free-form audit trail.

Assumption-based rows are **never** labelled literature-validated. See
[SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) for the policy.

### 6.4 Harmonic range controls

The harmonic geometry columns exported in the workbook are described in the
[data schema reference](DATA_SCHEMA_REFERENCE.md#harmonic-geometry-fields).
Key fields:

- `harmonic_type`, `harmonic_order`, `string_name`;
- `production_pitch`, `stopped_pitch`, `touched_pitch`, `open_string_pitch`;
- `sounding_pitch`, `sounding_midi`, `sounding_midi_float`,
  `sounding_frequency_hz`, `nearest_tempered_pitch`, `cents_deviation`;
- `physical_range_min`, `physical_range_max`, `analysis_range_min`,
  `analysis_range_max`;
- `included_by_physical_model`, `included_by_analysis_filter`,
  `excluded_reason`, `selection_mode`,
  `order_selection_reason`.

The physically available orders per instrument and the sounding-pitch
ceiling are configured in `configs/extrapolation_harmonic_ranges.yaml`.

## 7. Provenance warnings for doctoral use

Before citing an exported value in a thesis or peer-reviewed paper, verify:

1. `data_status` is `measured_research_data` (with `source_workbook_path`,
   `source_workbook_hash`, and `import_run_id`) rather than
   `manual_register_entry` or `unknown`.
2. `value_kind` is either `measured`, `derived_from_measured`, or
   `extrapolated` from a model whose `evidence_tier` you can defend.
3. `alpha_origin` and `assumption_ids` do not silently rely on an activated
   assumption unless the assumption is explicitly acknowledged.
4. `bayesian_backend_used` is `True` if the row is reported as a Bayesian
   credible interval; otherwise the `interval_type` will be
   `assumption_distribution_interval` and must be described as such.
5. `modal_metadata_status` and `acoustic_calibration_status` do not indicate
   `unavailable` for harmonic rows.
6. `missing_covariates` and `missing_model_components` are empty (or
   deliberately accepted).

The exporter deliberately hides Bayesian-only columns (`posterior_mean`,
`posterior_median`, `posterior_sd`, `credible_interval_*`) when the Bayesian
backend was not actually run. The neutral columns
(`estimate_mean`, `estimate_median`, `estimate_sd`, `interval_low`,
`interval_high`) are always preferred for reporting.

## 8. Where to go next

- [GUI_REFERENCE.md](GUI_REFERENCE.md) — control-by-control reference of the
  primary GUI.
- [CLI_REFERENCE.md](CLI_REFERENCE.md) — reproducible batch runs.
- [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) — full column
  dictionary.
- [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) — what the model
  cannot do (and why).
- [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) — full technical reference with
  formulas.
