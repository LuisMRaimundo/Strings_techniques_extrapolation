# String Technique Density Model

**Version:** `0.1.0`
(see [`pyproject.toml`](pyproject.toml) and [`CHANGELOG.md`](CHANGELOG.md))

Literature-informed estimation of acoustic density for extended
bowed-string techniques. The package supports a manual register entry
workflow, a nonlinear hierarchical extrapolation pipeline, a curated
literature evidence layer, and a user assumption registry.

**Start here:**
[docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md).
The full technical reference is
[docs/TECHNICAL_GUIDE.md](docs/TECHNICAL_GUIDE.md).

## Scope

- Instruments: orchestral bowed strings only — `vln` (violin),
  `vla` (viola), `vlc` (violoncello), `cb` (double bass).
- Dynamics: `pp`, `mf`, `ff`.
- Techniques with numerical output paths: `sul_tasto`, `sul_ponticello`,
  `con_sordino`. Harmonic techniques generate modal geometry (sounding
  pitches from `n · f₀` and open string × configured order) but the
  acoustic descriptor mapping remains numerically `NA`; multiphonics and
  flautando are qualitative only. See
  [docs/SCIENTIFIC_LIMITATIONS.md](docs/SCIENTIFIC_LIMITATIONS.md).
- Numerical technique-to-EWSD literature parameters remain **inactive**
  (`n_active_density_parameters == 0`). The metric identity `Φ(D) = D`
  is enforced.
- No audio is imported, played, or required. All computation is
  numerical.

## Installation

The package targets Python 3.10 or newer. From the repository root:

```bat
python -m pip install -e ".[dev]"
```

Optional Bayesian backend (PyMC / ArviZ / patsy):

```bat
python -m pip install -e ".[bayes]"
```

Windows quick start:

```bat
run.bat
```

## Primary workflow: GUI

The recommended workflow is the desktop GUI titled
`Manual register → technique requests`, implemented in
[`src/string_technique_model/gui_metadata/extrapolator_app.py`](src/string_technique_model/gui_metadata/extrapolator_app.py):

```bat
python -m string_technique_model gui
```

Three tabs:

1. **Measured register (type values)** — build a note column between two
   scientific-pitch endpoints, then paste or type the ordinary EWSD
   values.
2. **Requests (notes + techniques)** — tick techniques, configure the
   harmonic output range (physical range vs custom sounding range,
   `C8` ceiling), and generate one request per filled note × technique.
3. **Results** — run the nonlinear extrapolator and export the audit
   workbook.

Detailed reference: [docs/GUI_REFERENCE.md](docs/GUI_REFERENCE.md).
Full workflow: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Primary workflow: CLI

```bat
python -m string_technique_model nonlinear diagnose
python -m string_technique_model nonlinear fit-baseline --instrument vln --dynamic pp --research-excel path\to\research.xlsx
python -m string_technique_model nonlinear predict --technique sul_ponticello --instrument vln --dynamic pp --method hierarchical_spline --research-excel path\to\research.xlsx
```

Full CLI enumeration: [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

## Output

The nonlinear extrapolator writes a multi-sheet workbook by default at
`outputs/extrapolation/nonlinear_extrapolation_results.xlsx`. Sheets
include `Methodology`, `Posterior_Summary` (aliases `All_Results` and
`Note_Level_Results`), `Model_Selection`, `Model_Selection_Audit`,
`Technique_Effects`, `Diagnostics`, `Unavailable`, `Run_Summary`,
`Priors_Used`, and one sheet per technique. Column dictionary:
[docs/EXCEL_OUTPUT_REFERENCE.md](docs/EXCEL_OUTPUT_REFERENCE.md).

## Configuration

Configuration YAML files live under [`configs/`](configs). The most
influential files are:

- `extrapolation_model_selection.yaml` — thresholds and ladder families.
- `extrapolation_harmonic_ranges.yaml` — configured orders and
  sounding-pitch ceilings.
- `extrapolation_priors.yaml` — regularization / user-assumption priors.
- `extrapolation_models.yaml` — model shells and technique submodels.
- `density_metric.yaml` — canonical metric definition.
- `acoustic_descriptors.yaml` — descriptor registry.
- `analysis_profiles/*.yaml` — descriptor analysis profiles.
- `instruments.yaml` — per-instrument physical metadata.

Full field-level reference:
[docs/CONFIGURATION_REFERENCE.md](docs/CONFIGURATION_REFERENCE.md).

## Data schemas and outputs

- Row and result schemas:
  [docs/DATA_SCHEMA_REFERENCE.md](docs/DATA_SCHEMA_REFERENCE.md)
- Excel workbook layout:
  [docs/EXCEL_OUTPUT_REFERENCE.md](docs/EXCEL_OUTPUT_REFERENCE.md)
- Scientific limitations:
  [docs/SCIENTIFIC_LIMITATIONS.md](docs/SCIENTIFIC_LIMITATIONS.md)

## Literature corpus

Literature files live under
[`literature/`](literature). Local PDFs are treated as verification
material and are **git-ignored** so they do not enter a public
repository (see [`.gitignore`](.gitignore)):

```text
literature/corpus/books/
literature/corpus/articles/
literature/corpus/theses/
literature/corpus/reports/
literature/corpus/metadata/
```

The presence of a PDF does not activate any numerical EWSD parameter.
Secondary-synthesis figures require primary-source verification before
activation.

## Tests, lint, and types

```bat
python -m pytest -q
python -m ruff check src tests
python -m mypy src\string_technique_model
```

## Documentation validation

```bat
python tools\validate_documentation.py
```

A non-zero exit code indicates broken relative links, unbalanced math
delimiters, forbidden placeholders, or obsolete identifiers in the
documentation.

Absence of evidence in the local corpus must not be interpreted as
evidence of absence in the specialised literature.

## Honest scope statement

- The package does not recompute EWSD from spectra; it applies the
  identity `Φ(D) = D`.
- Numerical technique-to-EWSD literature parameters remain inactive.
- Mute figures rely on an explicit user assumption
  (`log(10^(-dB/10))`) with `alpha_origin=user_assumption`.
- Harmonic acoustic descriptors are numerically `NA`.
- Multiphonics and flautando produce qualitative output only.
- Instrument transfer is refused by default (violin parameters must not
  be silently reused for viola, cello, or contrabass).
- The Bayesian backend is optional; no pseudo-posterior is substituted
  when it is unavailable.

## Reports

Selected audit reports live under [`reports/`](reports):

- [`reports/documentation_audit.md`](reports/documentation_audit.md)
- [`reports/scientific_limitations.md`](reports/scientific_limitations.md)
- [`reports/technique_ontology_report.md`](reports/technique_ontology_report.md)
- [`reports/acoustic_descriptor_registry.md`](reports/acoustic_descriptor_registry.md)
- [`reports/pdf_integration_audit.md`](reports/pdf_integration_audit.md)
- [`reports/literature_gaps.md`](reports/literature_gaps.md)
