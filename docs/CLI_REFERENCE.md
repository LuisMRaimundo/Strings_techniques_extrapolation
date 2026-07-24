# Command-Line Reference

This reference documents every command exposed by the `string-technique-model`
command-line interface, as defined by `src/string_technique_model/cli/`. All
commands are also available through `python -m string_technique_model …`.

## Top-level

```text
string-technique-model [-h] [-v]
    {run,estimate,lookup,gui,collection,baseline,literature,
     predict,assumptions,extrapolate,request,nonlinear,stress-test} …
```

| Option | Meaning |
|--------|---------|
| `-h`, `--help` | Show the argparse help and exit. |
| `-v`, `--verbose` | Emit `DEBUG`-level log records. |

### Note on Unicode arrows in help text

The `request` subparser help contains a Unicode right-arrow (`→`). On Windows
consoles that use the legacy `cp1252` code page this character is transcoded
to `?` or an escape sequence, which is cosmetic and does not affect
functionality. Set `PYTHONIOENCODING=utf-8` and/or `chcp 65001` before
running the CLI if you require the original glyph.

## `run` and `estimate`

Both commands dispatch to `string_technique_model.pipeline.run_pipeline`.
`estimate` requires at least one baseline collection identifier; `run` uses
the defaults declared in the run configuration.

| Argument | Type | Notes |
|----------|------|-------|
| `--config` | `Path` | Optional run configuration YAML. |
| `--instruments` | list of strings | Restrict instruments. |
| `--techniques` | list of strings | Restrict techniques. |
| `--baseline-collections` | list of strings | Baseline collections (required for `estimate`). |
| `--pooling-method` | string | Overrides the pooling method in the run configuration. |

Failure modes:

- Missing baseline collections for `estimate` — exit code `2`.
- Unresolvable configuration path — exit code `1`.

## `lookup`

Look up a single `(instrument, technique, note, dynamic)` cell.

```bat
string-technique-model lookup --instrument vln --technique sul_ponticello --note A4 --dynamic mf
```

| Argument | Required | Notes |
|----------|----------|-------|
| `--instrument` | yes | `vln`, `vla`, `vlc`, or `cb`. |
| `--technique` | yes | Technique identifier. |
| `--note` | yes | Scientific pitch notation. |
| `--dynamic` | yes | `pp`, `mf`, or `ff`. |
| `--baseline-collections` | no | Baseline collections to consult. |
| `--config` | no | Optional run configuration path. |

## `gui`

Launch the primary desktop application:

```bat
string-technique-model gui
```

This starts the *Manual register → technique requests* window. The former
narrow extrapolator window is retained for backward compatibility but is no
longer the default. See [GUI_REFERENCE.md](GUI_REFERENCE.md).

## `collection`

Registry and ingestion commands for measurement collections. Subcommands:

| Subcommand | Purpose |
|------------|---------|
| `register` | Register a collection in `configs/collections.yaml`. |
| `list` | List registered collections. |
| `inspect` | Inspect one collection. |
| `validate` | Validate schema and metric compatibility. |
| `import` | Import a collection to a canonical parquet plus rejection report. |
| `compare` | Compare metric compatibility across collections. |

Key `register` arguments: `--collection-id` (required), `--data-path`
(repeatable), `--format` (default `csv`), `--schema-mapping`,
`--metric-definition-id` (default `ewsd_v1`), `--default-role`
(repeatable), `--notes`, `--dry-run`.

Key `import` arguments: `--collection-id` (required), `--config`, `--dry-run`,
`--overwrite`/`--no-overwrite` (default overwrite), `--include-invalid-records`
(keep out-of-scope instruments for debugging only).

Failure modes:

- `validate` returns exit code `1` when schema validation fails.

## `baseline`

Ordinary-bowing baseline engine (Phase 2).

| Subcommand | Purpose |
|------------|---------|
| `build` | Build an ordinary-bowing baseline. |
| `inspect` | Inspect the baseline run configuration. |
| `validate` | Validate the baseline run configuration. |
| `compare-methods` | Compare pooling methods (dry run). |

Selected `build` arguments: `--collections`, `--metric-definition`,
`--pooling-method`, `--run-config`, `--output-dir`, `--dry-run`,
`--overwrite`/`--no-overwrite`, `--seed`, `--strict`, `--instrument`,
`--dynamic`, `--pitch-min`, `--pitch-max`, `--no-wide`.

## `literature`

Specialised-literature evidence layer (Phase 3).

| Subcommand | Purpose |
|------------|---------|
| `inventory` | Build a literature inventory. |
| `validate-sources` | Validate the source registry. |
| `build-evidence-matrix` | Build the sixteen-cell evidence matrix. |
| `build-parameter-ledger` | Build the parameter evidence ledger. |
| `report-gaps` | Report literature gaps. |
| `export-bibtex` | Export a verified BibTeX file. |
| `validate-all` | Validate the entire literature layer. |
| `build-all` | Build all literature artefacts. |
| `ingest-package` | Ingest / validate the curated evidence package. |
| `scan-corpus` | Scan local literature files. |
| `register-source` | Register a local corpus file. |
| `add-extract` | Curate a page-level evidence extract. |

Failure modes:

- `validate-all` returns exit code `1` unless the run-level validation
  succeeds.
- `register-source` and `add-extract` refuse to persist when required
  metadata is missing.

## `predict`

Evidence-gated technique prediction (Phase 4).

| Subcommand | Purpose |
|------------|---------|
| `build` | Build technique predictions from an ordinary baseline table. |
| `from-ordinary` | Forecast techniques from ordinary CDM or baseline data. |
| `validate-context` | Validate prediction request contexts. |
| `inspect-parameters` | Inspect activation of parameters for a single cell. |
| `explain` | Explain a `prediction_id` from a prior output. |
| `sensitivity` | Run sensitivity scaffolding. |
| `validation-status` | Report whether external validation has been claimed. |

Selected `build` arguments: `--baseline` (required), `--backend`
(`metric-only` or `spectrum-aware`), `--activate-user-assumptions`,
`--instrument` / `--technique` / `--dynamic`, `--pitch-min`, `--pitch-max`,
`--allow-transfer`, `--mode` (`evidence-only` or
`evidence-plus-user-assumptions`), `--output-dir`, `--seed`, `--n-draws`.

Selected `from-ordinary` arguments: `--instrument` (required), `--dynamic`,
`--techniques`, `--source-json`, `--baseline`,
`--activate-user-assumptions`, `--mode`.

Failure modes:

- Assumption-based rows are labelled `result_basis=user_assumption` and are
  never marked literature-validated.
- `explain` returns exit code `1` when the `prediction_id` is not found.

## `assumptions`

User numerical assumptions.

| Subcommand | Purpose |
|------------|---------|
| `list` | List assumptions. |
| `validate` | Validate the assumption registry. |
| `show` | Show a single assumption. |
| `activate` | Set `active_for_density_prediction=true` (writes a `.bak`). |
| `deactivate` | Set `active_for_density_prediction=false` (writes a `.bak`). |
| `applicable` | Show which assumptions apply to a given cell. |
| `audit` | Emit a markdown audit report. |

Each write command produces a warning banner reminding the user that a user
assumption is not literature-validated.

## `extrapolate`

Umbrella command combining the legacy grid extrapolator and the nonlinear
Phase-1 pipeline.

| Subcommand | Purpose |
|------------|---------|
| `grid` | Legacy narrow literature grid extrapolator. |
| `fit-baseline` | Fit the ordinary baseline splines. |
| `fit-technique` | Fit a technique submodel (bow contact or mute). |
| `predict` | Predict a technique register (nonlinear). |
| `compare` | Compare `M0` constant vs `M1` hierarchical spline. |
| `diagnose` | Report backend capability diagnostics. |
| `export` | Alias of `predict` with an Excel export path. |

`grid` arguments (see `src/string_technique_model/cli/extrapolation.py`):
`--evidence`, `--targets`, `--baseline-dir`, `--research-excel`,
`--orchidea-root`, `--orchidea-manifest`, `--no-orchidea-manifest`,
`--output`.

`predict` and `export` share `--technique` and `--instrument` (required),
`--dynamic` (default `pp`), `--method` (one of `constant`,
`hierarchical_spline`, `physical_informed_bayesian`, `evidence_only`),
`--quantity` (default `EWSD_score_acoustic_balanced`), `--research-excel`,
`--orchidea-root`, `--export-xlsx`. `predict` additionally accepts `--mode`
as a compatibility alias for `--method`.

`fit-baseline` accepts `--instrument`, `--dynamic`, `--quantity`,
`--research-excel`, and `--orchidea-root`.

`fit-technique` accepts `--technique` (required), `--instrument` (required),
`--dynamic`, `--model`, `--research-excel`, and `--orchidea-root`.

Failure modes:

- Missing ordinary rows for the requested instrument/dynamic — exit code `2`
  with `error=no_ordinary_rows` (fit-baseline) or `missing_baseline`
  (fit-technique, predict).

## `request`

Note-level requests (`Measured notes → needed notes + technique`).

| Argument | Purpose |
|----------|---------|
| `--workbook` | Excel workbook containing `Measured` and `Requests` sheets. |
| `--research-excel` | Use a Spectral Analyser research Excel as the measured registry. |
| `--requests` | Optional separate requests Excel or CSV. |
| `--instrument` | Default instrument if missing in columns. |
| `--dynamic` | Default dynamic if missing in columns. |
| `--evidence` | Evidence YAML. |
| `--write-template` | Write a Measured/Requests template Excel and exit. |
| `--output` | Output Excel path (default `outputs/extrapolation/note_level_requests.xlsx`). |

Failure modes:

- Missing both measured and request rows — exit code `2` with an explanatory
  error message.

The help string contains a Unicode arrow; see the note in the top-level
section for the Windows console consideration.

## `nonlinear`

Direct access to the Phase-1 nonlinear pipeline. The subcommands mirror
`extrapolate {fit-baseline, fit-technique, predict, compare, diagnose}`
and share identical argument sets.

| Subcommand | Purpose |
|------------|---------|
| `fit-baseline` | Fit the ordinary baseline splines. |
| `fit-technique` | Fit a technique submodel. |
| `predict` | Predict a technique register. |
| `compare` | Compare `M0` constant vs `M1` hierarchical spline. |
| `diagnose` | Report backend capability diagnostics. |

The `diagnose` command reports the Bayesian backend availability (from
`bayesian_backend.check_backend`) and the current EWSD mapping status (from
`descriptor_model.ewsd_mapping_status`). It never claims a numerical
EWSD transform that is not registered.

## `stress-test`

Scientific acoustics stress testing.

| Subcommand | Argument | Meaning |
|------------|----------|---------|
| `acoustics` | `--tier` | One of `fast`, `extended`, `benchmark`, or `all`. |

See [ACOUSTICS_STRESS_TESTING.md](ACOUSTICS_STRESS_TESTING.md) for details.

## Global exit codes

| Code | Meaning |
|------|---------|
| `0` | Success. |
| `1` | Recoverable error (missing configuration, validation failure, uncaught exception). |
| `2` | Invalid arguments or empty inputs (missing baseline rows, unknown subcommand, missing required rows). |

## See also

- [USER_GUIDE.md](USER_GUIDE.md)
- [GUI_REFERENCE.md](GUI_REFERENCE.md)
- [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md)
- [NOTE_LEVEL_REQUESTS.md](NOTE_LEVEL_REQUESTS.md)
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md)
