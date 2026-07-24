# Documentation Audit

This audit records the files inspected, the substantive changes applied
during the documentation refresh, the obsolete statements removed or
marked as legacy, an inventory of formula-related notes, and the
inconsistencies observed between the documentation and the current
codebase.

Every finding is classified as **critical**, **major**, **moderate**,
**minor**, or **informational**.

## Files inspected

Documentation:

- [`docs/DOCUMENTATION_INDEX.md`](../docs/DOCUMENTATION_INDEX.md)
- [`docs/USER_GUIDE.md`](../docs/USER_GUIDE.md)
- [`docs/CLI_REFERENCE.md`](../docs/CLI_REFERENCE.md)
- [`docs/GUI_REFERENCE.md`](../docs/GUI_REFERENCE.md)
- [`docs/CONFIGURATION_REFERENCE.md`](../docs/CONFIGURATION_REFERENCE.md)
- [`docs/DATA_SCHEMA_REFERENCE.md`](../docs/DATA_SCHEMA_REFERENCE.md)
- [`docs/EXCEL_OUTPUT_REFERENCE.md`](../docs/EXCEL_OUTPUT_REFERENCE.md)
- [`docs/SCIENTIFIC_LIMITATIONS.md`](../docs/SCIENTIFIC_LIMITATIONS.md)
- [`docs/GLOSSARY.md`](../docs/GLOSSARY.md)
- [`docs/NONLINEAR_EXTRAPOLATION.md`](../docs/NONLINEAR_EXTRAPOLATION.md)
- [`docs/TECHNICAL_GUIDE.md`](../docs/TECHNICAL_GUIDE.md)
- [`docs/NARROW_EXTRAPOLATION_GUI.md`](../docs/NARROW_EXTRAPOLATION_GUI.md)
- [`docs/METADATA_ENTRY_GUI.md`](../docs/METADATA_ENTRY_GUI.md)
- [`docs/NARROW_EXTRAPOLATION.md`](../docs/NARROW_EXTRAPOLATION.md)
- [`docs/NOTE_LEVEL_REQUESTS.md`](../docs/NOTE_LEVEL_REQUESTS.md)
- [`docs/ACOUSTICS_STRESS_TESTING.md`](../docs/ACOUSTICS_STRESS_TESTING.md)
- [`README.md`](../README.md)

Code references cross-checked:

- `src/string_technique_model/cli/*.py` (argparse tree)
- `src/string_technique_model/gui_metadata/extrapolator_app.py`
  (primary GUI)
- `src/string_technique_model/extrapolation/nonlinear/domain.py`
  (`ExtrapolationResult`, `EvidenceTier`, `ValueKind`)
- `src/string_technique_model/extrapolation/nonlinear/export_nonlinear.py`
  (Excel exporter and `Run_Summary` keys)
- `src/string_technique_model/extrapolation/nonlinear/model_selection.py`
  (selection engine and gates)
- `src/string_technique_model/extrapolation/nonlinear/harmonic_register.py`
  (harmonic target generator)
- `configs/extrapolation_model_selection.yaml`
- `configs/extrapolation_harmonic_ranges.yaml`
- `configs/extrapolation_priors.yaml`
- `configs/extrapolation_models.yaml`
- `configs/density_metric.yaml`
- `configs/acoustic_descriptors.yaml`
- `configs/instruments.yaml`

## Follow-up corrections (same documentation refresh)

| Item | Resolution |
|------|------------|
| Invalid Markdown image embed of `architecture.mmd` | Replaced with a relative text link; Mermaid remains in fenced blocks. |
| Legacy narrow doc claimed harmonics “deferred” without scope | Banner added in `NARROW_EXTRAPOLATION.md` clarifying legacy-grid-only scope. |
| Duplicate pytest module basename `test_reproducibility.py` | Renamed extrapolation copy to `test_extrapolation_reproducibility.py`. |
| Guide validation script / section-heading tests | Updated to the rewritten section plan; Appendix D covers Phase-4 APIs and literature source IDs. |
| GUI smoke test expected `n_matched_baseline` | Updated for default automatic / nonlinear summary keys. |
| README missing “absence of evidence…” sentence | Restored exact phrase required by literature-layer tests. |

## Changes applied

| File | Change | Type |
|------|--------|------|
| `docs/DOCUMENTATION_INDEX.md` | Created; enumerates the current documentation, authoritative document per subject, and the recommended reading order. | New |
| `docs/USER_GUIDE.md` | Created; end-to-end workflow with the primary GUI, interpretation of `value_kind` / `NA` / assumptions, harmonic range controls, doctoral provenance checklist. | New |
| `docs/CLI_REFERENCE.md` | Created; documents every subcommand of the current `argparse` tree, argument sets, examples, and failure modes; notes the Unicode-arrow console issue on Windows. | New |
| `docs/GUI_REFERENCE.md` | Created; documents the current primary GUI (title `Manual register → technique requests`), three tabs, technique checkboxes, harmonic controls (physical range, `C8`, selection modes), the method combobox mapping `hierarchical_spline → requested_method=automatic`, and the `Return to start` button. Points to `src/string_technique_model/gui_metadata/extrapolator_app.py`; marks `METADATA_ENTRY_GUI.md` as legacy secondary. | New |
| `docs/CONFIGURATION_REFERENCE.md` | Created; documents the key YAML files with per-field type, default, and effect. | New |
| `docs/DATA_SCHEMA_REFERENCE.md` | Created; documents measurement / request / result rows, `EvidenceTier`, `ValueKind`, `data_status`, `scientific_use`, harmonic geometry fields, and `missing_covariates` vs `missing_model_components`. | New |
| `docs/EXCEL_OUTPUT_REFERENCE.md` | Created; documents the nonlinear workbook sheets and the `Run_Summary` keys, including the distinction between `estimate_*` and `posterior_*` columns and the `modal_metadata_status`, `acoustic_calibration_status`, `missing_model_components` fields. | New |
| `docs/SCIENTIFIC_LIMITATIONS.md` | Created; explicit inventory of limitations matching code reality (sparse targets, EWSD identity-only, mute dB → EWSD assumption, no `A_m(f)`, harmonic modal geometry vs numeric acoustic model, violin-centric literature, no fake Bayes, and others). | New |
| `docs/GLOSSARY.md` | Created; symbols, acronyms, confused-term pairs. | New |
| `docs/NONLINEAR_EXTRAPOLATION.md` | Rewritten; aligned with current code (model selection, harmonic modal generation plus acoustic NA, honest estimate fields, selection after enrichment), positioned as specialist companion that links to `TECHNICAL_GUIDE.md`. | Rewrite |
| `docs/NARROW_EXTRAPOLATION_GUI.md` | Added `LEGACY / SECONDARY` banner and obsolete-claim notice near the `Launch` section. Content retained. | Update |
| `docs/METADATA_ENTRY_GUI.md` | Added `LEGACY / SECONDARY` banner; older cross-reference to the Narrow Extrapolator as the default `gui` entry is marked obsolete. Content retained. | Update |
| `docs/TECHNICAL_GUIDE.md` | Corrected the capability table entry that previously said harmonic sounding-pitch geometry from `n · f₀` was not implemented (see finding **F-01** below). | Correction |
| `README.md` | Rewritten; points to `docs/DOCUMENTATION_INDEX.md` and `docs/TECHNICAL_GUIDE.md`, documents install and run, states the honest scope, notes literature PDFs are git-ignored for the public repo, records the current version `0.1.0`. | Update |
| `reports/documentation_audit.md` | This report. | New |
| `tools/validate_documentation.py` | Created; checks broken relative links, unbalanced math delimiters, forbidden placeholders, obsolete identifiers, and presence of the anchor documents. | New |

## Obsolete statements removed or marked legacy

- `docs/METADATA_ENTRY_GUI.md` previously stated that
  `python -m string_technique_model gui` opens the Narrow Extrapolator
  window. This is no longer true; the primary GUI is the
  `Manual register → technique requests` window. Marked as **legacy /
  secondary** with an explicit obsolete-claim notice.
- `docs/NARROW_EXTRAPOLATION_GUI.md` implicitly described the Narrow
  Extrapolator as the primary interface. Marked as **legacy /
  secondary** with an explicit obsolete-claim notice near the `Launch`
  section.
- `docs/TECHNICAL_GUIDE.md` capability table previously stated that
  harmonic sounding-pitch geometry from `n · f₀` was **not
  implemented**. This is false: the geometry generator is implemented in
  `src/string_technique_model/extrapolation/nonlinear/harmonic_register.py`
  and used by the nonlinear pipeline. The table entry has been split
  into two rows (geometry: implemented; acoustic descriptor / EWSD
  mapping: not implemented). Finding **F-01**.

## Formula inventory notes

- The identity `Φ(D) = D` remains the canonical metric map. It is
  quoted verbatim in the technical guide and the user guide, and it is
  the only formula that binds the runtime pipeline. See
  `configs/density_metric.yaml` and
  `src/string_technique_model/density/metric.py`.
- The ordinary baseline is a penalized B-spline on MIDI with a log
  transform. Documented in the technical guide (long form) and the
  nonlinear document (short form).
- The technique log-ratio `log R_{t,i,d}(p) = α_t + u_{t,i} + v_{t,d} +
  g_{t,i}(p)` is emitted only when the register curve is identifiable;
  otherwise `g_t(p) = 0` and the label
  `constant_technique_effect_over_smoothed_baseline` is applied.
- Interval widths use the log-`R` scale; when the fit is dominated by
  the prior, `interval_type=assumption_distribution_interval`. No
  classical confidence intervals are emitted.
- Mute mapping is expressed as `α_mute = log(10^(-dB/10))` for
  instrument-specific dB values (`~6 dB` for violin, `~4 dB` for
  viola). This is a user assumption; there is no derivation from mute
  mass or mute material in the code.
- The harmonic sounding pitch is `n · f₀`; the geometry is implemented,
  but no acoustic descriptor / EWSD numerical mapping is registered.

No LaTeX formulas were invented for entries labelled as unimplemented.

## Inconsistencies found

The following inconsistencies were identified in the research phase.
Each is classified below.

| ID | Finding | Classification | Resolution |
|----|---------|----------------|------------|
| F-01 | `TECHNICAL_GUIDE.md` capability table claimed harmonic sounding-pitch from `n · f₀` was **not implemented**; the code implements the geometry generator (`harmonic_register.py`), which is invoked by the nonlinear predict path and exports full geometry columns. | **Critical** | Corrected the entry in the technical guide; explicit split into geometry (implemented) vs acoustic descriptor / EWSD mapping (not implemented). |
| F-02 | Narrow documentation (`NARROW_EXTRAPOLATION.md`, `NARROW_EXTRAPOLATION_GUI.md`) discouraged applying mute dB as an EWSD multiplier, while the nonlinear priors registry (`configs/extrapolation_priors.yaml`) does exactly that under `alpha_mute_vln` / `alpha_mute_vla` with `source=user_assumption`. | **Major** | Documented the difference explicitly in `SCIENTIFIC_LIMITATIONS.md` and `CONFIGURATION_REFERENCE.md`; the narrow documentation now sits under the legacy grid pipeline (`extrapolate grid`) and is decoupled from the nonlinear pipeline. |
| F-03 | Descriptor spectral slope is defined as `spectral_slope_logfreq_db_linreg_v1` with units `dB_per_decade_log10Hz` (`configs/acoustic_descriptors.yaml`). Older references sometimes used the naming shorthand `spectral_slope_db_per_harmonic`, which is a different definition. | **Moderate** | Documented the distinction in `GLOSSARY.md` under confused-term pairs. |
| F-04 | Legacy GUI documents (`NARROW_EXTRAPOLATION_GUI.md`, `METADATA_ENTRY_GUI.md`) described the *wrong* primary GUI. The current entry `python -m string_technique_model gui` launches the *Manual register → technique requests* window implemented in `gui_metadata/extrapolator_app.py`. | **Major** | Added `LEGACY / SECONDARY` banners; new `GUI_REFERENCE.md` documents the primary GUI; the documentation index and README point to it. |
| F-05 | Some documents referred to a nonexistent `acoustics/` package. The implemented backend is under `descriptors/`; there is no `src/string_technique_model/acoustics` directory. | **Minor** | Documentation now consistently refers to `descriptors/`. |
| F-06 | The EWSD `F(D₁, …, D_k)` composition is unresolved in the local corpus. Some earlier drafts implied a validated formula. | **Moderate** | `SCIENTIFIC_LIMITATIONS.md` states explicitly that `EWSD F(D)` is unresolved; the nonlinear document quotes the `observed_scalar_direct_model` label used in `Methodology`. |
| F-07 | Older text referred to an obsolete identifier `harmonic_insufficient_metadata`. The current identifier is `insufficient_harmonic_metadata` (emitted by the metadata gate). | **Minor** | Documentation now uses only the current identifier; the validator refuses the obsolete identifier. |

## Residual gaps

- No numeric EWSD mapping is registered for harmonic techniques, and no
  such mapping is invented in the documentation. The harmonic geometry
  is documented and the two gate identifiers
  (`harmonic_modal_metadata_gate` and
  `harmonic_modal_acoustic_model_unavailable`) are described in
  `SCIENTIFIC_LIMITATIONS.md` and `DATA_SCHEMA_REFERENCE.md`.
- The Bayesian backend is optional; the exporter clears Bayesian
  columns when the backend was not actually run. The user guide and
  the Excel reference both flag this explicitly.
- The legacy narrow priority-1 grid extrapolator
  (`extrapolate grid`) coexists with the nonlinear pipeline. Both are
  documented but the nonlinear pipeline is now the primary interface.

## Findings by severity (summary)

| Severity | Count |
|----------|------:|
| Critical | 1 (F-01) |
| Major | 2 (F-02, F-04) |
| Moderate | 2 (F-03, F-06) |
| Minor | 2 (F-05, F-07) |
| Informational | 0 |

## Validation

The documentation set was checked with
[`tools/validate_documentation.py`](../tools/validate_documentation.py).
The tool exits non-zero on any of the following: broken relative Markdown
links, unbalanced `$$` display math delimiters, uneven `$` counts
outside fenced code blocks, presence of `TODO_DOC`, `TBD_FORMULA`, or
`lorem ipsum`, presence of the obsolete identifier
`harmonic_insufficient_metadata`, or absence of
`docs/TECHNICAL_GUIDE.md` or `docs/DOCUMENTATION_INDEX.md`.
