# Excel Output Reference

The nonlinear extrapolation pipeline exports a multi-sheet Excel workbook.
The exporter is
`src/string_technique_model/extrapolation/nonlinear/export_nonlinear.py`.
This reference documents each sheet and its columns.

The workbook is produced under `outputs/extrapolation/` by default; the
GUI writes `nonlinear_extrapolation_results.xlsx`. The CLI honours
`--export-xlsx`.

## Sheet inventory

| Sheet | Purpose |
|-------|---------|
| `Methodology` | Fixed topic / detail pairs summarising the methodology. |
| `Posterior_Summary` | Full row-per-cell audit summary (from `ExtrapolationResult.to_row()`). |
| `All_Results` | Alias of `Posterior_Summary` (kept for GUI compatibility). |
| `Note_Level_Results` | Alias of `Posterior_Summary` (kept for older note-level readers). |
| `Model_Selection` | Compact per-cell selection outcome. |
| `Model_Selection_Audit` | One row per candidate / rejected model. |
| `Technique_Effects` | Distinct technique-effect entries with `alpha_t`, prior identifiers, and assumption trails. |
| `By_Technique` | Cell counts grouped by technique, instrument, dynamic, and model. |
| `Diagnostics` | Per-cell diagnostic subset. |
| `Unavailable` | Subset of `Posterior_Summary` where `value_kind == unavailable`. |
| `Harmonic_Coverage` | Per instrument×collection×technique×dynamic coverage manifest (measured / missing pitches, hashes). |
| `Harmonic_Source_Selection` | Resolver audit per harmonic result (`support_class`, source/target, candidates, transfer gates). |
| `Dynamic_Transfers` | Subset where `support_class == same_instrument_dynamic_transfer`. |
| `Unsupported_Harmonic_Targets` | Harmonic rows with `unsupported` / missing `estimate_mean`. |
| `Run_Summary` | Key-value run metadata. |
| `Model_Comparison` | Optional comparison of `M0` vs `M1` when provided. |
| `Priors_Used` | Loaded priors with activation status. |
| `<technique>` | One sheet per technique (name truncated to 31 characters). |

## `Methodology` sheet

Fixed content that describes the methodology at run time. Each row is a
`(topic, detail)` pair. Topics currently emitted:

`Model selection`, `Stages`, `Ladder`, `Config`, `Baseline`,
`Technique shape`, `Intervals`, `Estimate columns`, `Assumptions`,
`Harmonics`, `EWSD mapping`. This sheet is intentionally static.

## `Posterior_Summary`, `All_Results`, `Note_Level_Results`

These three sheets carry the same content: the full flattened
`ExtrapolationResult` row set. Column meanings are defined in
[DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md).

### `estimate_*` vs `posterior_*`

The exporter distinguishes two families of columns:

- **Neutral estimate columns**: `estimate_mean`, `estimate_median`,
  `estimate_sd`, `interval_low`, `interval_high`, `interval_type`,
  `interval_formula`. These are always populated when the pipeline
  produces a numerical value, regardless of the backend.
- **Bayesian-only columns**: `posterior_mean`, `posterior_median`,
  `posterior_sd`, `credible_interval_low`, `credible_interval_high`,
  `credible_interval_probability`, `log_ratio_mean`, `log_ratio_sd`,
  `probability_above_ordinary`. These are **cleared to `None` on export**
  when `bayesian_backend_used=False`. This prevents readers from
  misinterpreting a penalized-fit approximation as a credible interval.

Downstream consumers should therefore read the neutral columns unless the
Bayesian backend was explicitly enabled and produced a valid posterior
sample.

## `Model_Selection` sheet (compact)

One row per distinct `(technique, instrument, dynamic, selected_model_id,
selection_reason)` tuple:

| Column | Meaning |
|--------|---------|
| `technique`, `instrument`, `dynamic`, `target_quantity`, `model_family` | Cell coordinates. |
| `selected_model_id` | Model identifier ultimately used. |
| `selection_reason` | Reason emitted by the selection engine. |
| `fallback_level` | Fallback rung (for example `qualitative_or_na`). |
| `model_selection_status` | Coarse status. |
| `candidate_model_ids` | Semicolon-separated list of admissible candidates. |
| `rejected_model_ids` | Semicolon-separated list of rejected candidates. |
| `available_covariates`, `required_covariates`, `missing_covariates`, `missing_model_components` | Covariate audit. |
| `modal_metadata_status` | For harmonic families: `complete`, `incomplete`, or `unknown`. |
| `acoustic_calibration_status` | For harmonic families: `calibrated`, `unavailable`, or `unknown`. |
| `target_technique_observations`, `distinct_pitch_count` | Data availability summary. |
| `value_kind` | Selected `ValueKind` for the cell. |

## `Model_Selection_Audit` sheet (full audit)

One row per candidate and per rejected model in the cell. Adds:

| Column | Meaning |
|--------|---------|
| `model_id` | Candidate or rejected model identifier. |
| `role` | `selected`, `candidate_admissible_or_listed`, or `rejected`. |
| `rejection_reason` | Reason emitted for rejected models. |
| `pitch_span_semitones` | Register span across the observations. |
| `assumption_ids` | Assumption identifiers consulted for this model. |

Together with `Model_Selection`, this sheet documents every step of the
selection engine.

## `Technique_Effects` sheet

Distinct technique-effect entries:

| Column | Meaning |
|--------|---------|
| `technique`, `instrument`, `dynamic` | Cell coordinates. |
| `alpha_t` | Log-ratio coefficient. |
| `technique_multiplier` | Multiplicative effect on the baseline. |
| `alpha_origin` | Origin label (`regularization_assumption`, `user_assumption`, `evidence_only`, …). |
| `effect_kind` | Free-form effect label. |
| `attenuation_db_power` | Mute audit label (never used as an EWSD multiplier). |
| `assumption_ids`, `assumptions_trace`, `assumptions_used` | Assumption trail. |
| `prior_ids` | Semicolon-separated priors consulted. |
| `model_id` | Model that produced the effect. |

## `Diagnostics` sheet

Diagnostic subset (per cell):

| Column | Meaning |
|--------|---------|
| `record_id`, `technique`, `pitch`, `model_id` | Identity. |
| `interval_type` | Type of interval reported. |
| `sigma_origin`, `sigma_value`, `sigma_estimated_from_data` | Residual scale. |
| `register_shape_identified`, `shape_source` | Register curve identifiability. |
| `prior_dominated`, `model_status`, `evidence_tier` | Result labels. |
| `baseline_n_observations`, `baseline_n_knots`, `baseline_penalty_lambda` | Baseline spline diagnostics. |

## `Run_Summary` sheet

Key-value run metadata written after every export. Always present keys:

| Key | Meaning |
|-----|---------|
| `exported_at_utc` | ISO 8601 UTC timestamp. |
| `requested_method` | Method requested by the caller. For the GUI this is `automatic` whenever `hierarchical_spline` was selected. |
| `baseline_model` | Comma-separated list of baseline model identifiers used. |
| `n_results` | Total number of result rows. |
| `n_numeric_results` | Number of rows with a non-null `estimate_mean` and `value_kind != unavailable`. |
| `n_unavailable` | Number of rows with `value_kind == unavailable`. |
| `n_assumption_distribution_intervals` | Number of rows whose `interval_type` is `assumption_distribution_interval`. |
| `data_status_values` | Comma-separated distinct `data_status` values. |
| `techniques_exported` | Comma-separated distinct techniques. |
| `selected_technique_model.<technique>` | Selected model per technique. |

GUI-authored runs additionally add:

| Key | Meaning |
|-----|---------|
| `gui_displayed_method` | The method as it appears in the GUI (`hierarchical_spline`, `constant`, …). |
| `effective_selection_mode` | Effective selection mode (`automatic` or the raw method). |
| `harmonic_sounding_min`, `harmonic_sounding_max` | Requested sounding-pitch bounds. |
| `include_low_harmonics` | Whether low-order harmonics were included. |
| `source_workbook_path`, `import_run_id` | Provenance forwarded from the loaded workbook. |
| `cli_method_control` | Only set when the CLI wrote the metadata directly. |
| `load_warnings` | Trimmed load-warning list. |

## `Unavailable` sheet

Subset of `Posterior_Summary` for rows with `value_kind == unavailable`.
Use this sheet to audit which cells were refused and why.

## Harmonic audit sheets

- **`Harmonic_Coverage`** — regenerated coverage manifest rows (instrument, collection, technique, dynamic, measured/missing pitches, counts, SSA/EWSD version, source files/hashes).
- **`Harmonic_Source_Selection`** — one row per harmonic result with `support_class`, source/target instrument and dynamic, collection, `source_record_ids`, transfer formula/gates, candidate JSON, `estimate_mean` / `na_reason`.
- **`Dynamic_Transfers`** — rows accepted as `same_instrument_dynamic_transfer`.
- **`Unsupported_Harmonic_Targets`** — harmonic rows with unavailable numeric EWSD under the resolver gates.

## `Model_Comparison` sheet

Populated when the caller supplied `comparisons` (currently used by the
`extrapolate compare` CLI command). Columns match
`ModelComparisonResult`: `comparison_id`, `instrument`, `technique`,
`dynamic`, `target_quantity`, `status`, `m0_model_id`, `m1_model_id`,
`n_holdout`, `rmse_m0`, `rmse_m1`, `mae_m0`, `mae_m1`, `coverage_m0`,
`coverage_m1`, `preferred_model`, `warnings`.

## `Priors_Used` sheet

Full dump of the priors loaded by the exporter (see
[CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) for the priors
file). Columns mirror the `PriorSpec` model.

## Per-technique sheets

For every technique observed in the results, the exporter writes a sheet
named after the technique (truncated to 31 characters). The columns match
`Posterior_Summary`.

## Related documents

- [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) — full column
  meaning for `ExtrapolationResult`.
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — configuration
  files consumed by the pipeline.
- [USER_GUIDE.md](USER_GUIDE.md) — reading the workbook in the doctoral
  workflow.
- [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) — companion
  reference to the technical guide.
