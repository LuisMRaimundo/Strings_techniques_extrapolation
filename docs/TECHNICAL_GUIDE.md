# Technical Guide

**Program:** `string-technique-model` — Strings Techniques Extrapolation
**Distribution name:** `string-technique-model` (PyPI-style), Python package `string_technique_model`
**Version:** `0.1.0` (`pyproject.toml`)
**Commit at snapshot:** `644df08`
**Document date:** 2026-07-24
**Python requirement:** `>=3.10`
**Console scripts:** `string-technique-model`, `string-technique-gui`
**Optional extras:** `[bayes] = pymc, arviz, patsy`; `[dev] = pytest, pytest-cov, ruff, mypy, pandas-stubs, types-PyYAML`
**Math rendering:** UTF-8 Markdown for StackEdit / KaTeX. Inline math uses `$ ... $`, display math uses `$$ ... $$`. No image equations, no Unicode substitutes for math operators.

> **Reading rule.** This guide describes the system **as implemented in this commit**. Every formula is tagged with a status: **IMPLEMENTED**, **IMPLEMENTED_FALLBACK**, **OPTIONAL_BACKEND**, **REFERENCE_MODEL**, **PLANNED**, or **ASSUMPTION**. A formula that appears in code exactly as written is **IMPLEMENTED**; a formula whose numerical constants come from user-supplied priors is **ASSUMPTION**; a formula used only for documentation of an oracle relationship is **REFERENCE_MODEL**.

> **Validation layers.** This document strictly separates three layers that are often conflated in acoustics-adjacent software:
>
> 1. **Software verification** — the code computes what the specification says (unit tests, algebraic identities, boundary handling). The commit ships with roughly **482 collected tests** (with `PYTHONPATH=src`; count verified at documentation refresh).
> 2. **Numerical / model verification** — fitted objects reproduce known synthetic cases (spline recovery, log/exp round-trip, interval scaling with baseline).
> 3. **Ecological acoustic validity** — whether the fitted numbers correspond to real bowed-string acoustic phenomena. This layer is **not established here** for extended techniques. The repository does not claim that its numerical outputs are validated acoustic predictions of `sul tasto`, `sul ponticello`, `con sordino`, or harmonics on real instruments.

---

## 1. Title, version, status and validation statement

**Canonical short title:** *Strings Techniques Extrapolation — literature-informed nonlinear extrapolation of a scalar acoustic-balanced density score (EWSD) from ordinary bowing to extended techniques (sul tasto, sul ponticello, con sordino, harmonic register).*

**Scope of implementation.**

- Ordinary baseline: **IMPLEMENTED** as a log-linear penalized cubic B-spline on MIDI, per instrument $\times$ dynamic.
- Bow-contact techniques (`sul_tasto`, `sul_ponticello`): **IMPLEMENTED** as multiplicative log-ratio submodels with an ordinary baseline shape; alpha centres come from **ASSUMPTION** priors when observations are absent.
- Mute technique (`con_sordino`): **IMPLEMENTED** as a mute log-scalar effect driven by a dB power reduction **ASSUMPTION** (about 6 dB for violin, 4 dB for viola), mapped to a log-ratio via `log(10^{-\mathrm{dB}/10})`.
- Harmonic register (`natural_harmonic`, `artificial_harmonic`): **IMPLEMENTED** for pitch generation only; acoustic EWSD values remain **PLANNED**.
- Optional Bayesian backend (PyMC/ArviZ): **OPTIONAL_BACKEND**; when the extra is not installed, the pipeline reports `bayesian_backend_unavailable` and never fabricates posteriors.
- Acoustic descriptors: separate backend under `descriptors/`; **IMPLEMENTED** as scalar/vector features. They are not currently used to compute EWSD from spectra — see §11.

**What this software is not.** It is not a physical simulator of bowed-string instruments. It is not a spectral EWSD predictor. It does not measure loudness in sones. It does not decide whether extended techniques are perceptually equivalent to their labels.

---

## 2. Purpose and research scope

The repository supports a doctoral research pipeline that must:

1. Accept a manually curated register of ordinary EWSD values per note (musician-facing GUI or research Excel).
2. Fit a **smooth ordinary baseline** as a function of MIDI pitch, per instrument and dynamic.
3. Extrapolate that baseline to selected extended techniques by applying a **multiplicative log-ratio** effect $\exp(\alpha_t + g_t(p))$.
4. Choose, in an auditable and deterministic way, the **simplest identifiable model** that the data support (constant $\rightarrow$ linear $\rightarrow$ penalized spline $\rightarrow$ physical-informed $\rightarrow$ spectral/modal); never auto-select the most complex.
5. Generate **harmonic sounding pitches** from physically plausible string $\times$ order combinations up to a configured ceiling (`C8` by default), not by copying the ordinary chromatic register.
6. Produce **audit-grade Excel outputs** with methodology, model selection audit, diagnostics, priors, unavailable cells, and provenance.
7. Distinguish, in every output cell, between:
   - measured or partially empirical numbers,
   - assumption-based extrapolations (with named `ASSUMP_*` identifiers),
   - qualitative-only cells,
   - unavailable cells (with explicit `na_reason`).

The scientific interpretation always distinguishes **software verification** from **ecological acoustic validity**.

---

## 3. System architecture

### 3.1 General architecture

The machine-editable Mermaid source for the architecture diagram is also
stored at [`technical_guide_assets/architecture.mmd`](technical_guide_assets/architecture.mmd).

```mermaid
flowchart LR
  subgraph IN[Ingestion]
    GUI[Manual register GUI]
    XLS[Research Excel or Orchidea manifests]
    CFG[YAML configs]
  end
  subgraph PITCH[Pitch registry]
    PR[MIDI-Hz mapping and pitch names]
  end
  subgraph BL[Ordinary baseline]
    BSPL[log linear penalized B-spline on MIDI]
    BFIT[BaselineFitCollection per instrument x dynamic]
  end
  subgraph SEL[Model selection]
    DA[DataAvailability audit]
    LADDER[complexity ladder M0..M5]
    DECIS[ModelSelectionDecision]
  end
  subgraph TECH[Technique submodels]
    BOW[bow contact log-ratio submodel]
    MUTE[mute log-scalar submodel]
    HARM[harmonic register pitch generator]
    NA[unavailable / qualitative fallback]
  end
  subgraph EWSD[Density metric]
    PHI[Phi(D)=D on precomputed EWSD scalar]
  end
  subgraph POST[Uncertainty]
    LOGR[multiplicative logR interval]
    ADI[assumption distribution interval]
    BAY[optional Bayesian backend PyMC/ArviZ]
  end
  subgraph OUT[Outputs]
    XLSX[nonlinear_extrapolation_results.xlsx]
    REP[Excel sheets: Methodology, Model_Selection, Diagnostics ...]
    PROV[provenance: data_status, source_workbook_hash ...]
  end
  GUI --> PITCH --> BSPL
  XLS --> BSPL
  CFG --> SEL
  CFG --> TECH
  CFG --> PHI
  BSPL --> BFIT --> TECH
  BFIT --> DA --> LADDER --> DECIS --> TECH
  TECH --> POST --> OUT
  PHI --> TECH
  HARM --> DECIS
  DECIS --> NA
  NA --> OUT
```

### 3.2 Harmonic register generation flow

```mermaid
flowchart TD
  A[Request harmonic technique + instrument] --> B{harmonic_type}
  B -->|natural| C[for each open string]
  C --> C1[f_n = n * f_open for configured orders n in 2..N_max]
  C1 --> D[compute sounding MIDI: m = 69 + 12*log2(f_n/440)]
  B -->|artificial| E[iterate stopped MIDI over playable range]
  E --> E1[sounding = stopped + 12*log2(order); default order=4 P4 touch]
  D --> F{sounding <= max_sounding_midi = 108 C8?}
  E1 --> F
  F -->|yes| G[emit target row with harmonic geometry]
  F -->|no| H[reject: outside instrument analysis range]
  G --> I{model_selection}
  I -->|harmonic_metadata_complete=false| J[harmonic_modal_metadata_gate]
  I -->|harmonic_metadata_complete=true and no calibration| K[harmonic_modal_acoustic_model_unavailable]
  J --> L[value_kind=unavailable, na_reason=insufficient_harmonic_metadata]
  K --> M[value_kind=unavailable, na_reason=no_harmonic_acoustic_calibration_data]
  L --> N[Excel: modal_frequencies_generated_acoustic_values_unavailable]
  M --> N
```

### 3.3 Data-flow direction

Ingestion $\rightarrow$ pitch normalisation $\rightarrow$ ordinary baseline fit $\rightarrow$ model-selection audit $\rightarrow$ technique submodel fit (or unavailable) $\rightarrow$ interval assembly $\rightarrow$ Excel export with full provenance.

Qualitative constraints and evidence extraction from literature remain in the repository as separate infrastructure but do **not** inject numbers into EWSD estimates unless a curator-activated parameter passes the activation gate.

---

## 4. Repository structure

Principal directories:

```
Strings_Techniques_Extrapolation/
  pyproject.toml
  README.md
  CHANGELOG.md
  CITATION.cff
  configs/                    # YAML authority files (all runtime parameters)
    analysis_profiles/
    datasets/
    extrapolation/            # provisional density effects, GUI presets
    schemas/                  # collection schema mappings
  data/                       # sample and reference data
  docs/                       # this guide and related documents
    technical_guide_assets/   # Mermaid sources and README
  literature/                 # corpus PDFs and identity manifest
  notebooks/
  outputs/                    # generated Excel and CSV runs (git-ignored)
  reports/                    # generated Markdown reports
  scripts/
  src/string_technique_model/
    analytical_levels/        # 4-layer separation
    applicability/            # resolver engine
    assumptions/              # user numerical assumptions
    baseline/                 # ordinary baseline pitch/MIDI utilities
    cli/                      # argparse subcommands
    collections/              # collection registry and ingestion
    constraints/              # qualitative-only engine
    density/                  # Phi(D)=D metric
    descriptors/              # acoustic descriptor backend
    extrapolation/
      nonlinear/              # baseline, splines, model_selection,
                              #   bow_contact_model, mute_model,
                              #   harmonic_register, harmonic_model,
                              #   bayesian_backend, posterior, prediction,
                              #   export_nonlinear, priors, provenance
    gui_metadata/             # extrapolator_app.py, register grids
    instruments/              # instrument registry
    io/                       # parquet preflight
    literature/               # evidence layer
    manual_entry/             # pitch helpers, entry pipelines
    measurement_domains/
    metadata_entry/
    metrics/
    models/                   # technique models and capabilities
    ontology/                 # technique ontology loader
    pitch/                    # full chromatic registry MIDI 0..127
    prediction/               # legacy prediction pipeline
    production/               # ProductionInstruction, beta, harmonics
    provenance.py             # provenance helpers
    recognition/              # MIR label mapping
    sensitivity/
    testing/                  # stress runner
    transforms/
    uncertainty/
    validation/
    visualization/
  tests/                       # ~482 collected tests (with PYTHONPATH=src)
```

The nonlinear extrapolation stack lives in `src/string_technique_model/extrapolation/nonlinear/`. The manual GUI is `src/string_technique_model/gui_metadata/extrapolator_app.py`.

---

## 5. Installation and execution

### 5.1 Environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix
source .venv/bin/activate

pip install -e .
# Optional Bayesian backend
pip install -e ".[bayes]"
# Development tooling
pip install -e ".[dev]"
```

### 5.2 Console scripts

- `string-technique-model` $\rightarrow$ `string_technique_model.cli:main`
- `string-technique-gui` $\rightarrow$ `string_technique_model.gui:main`

Equivalent module invocations:

```bash
python -m string_technique_model --help
python -m string_technique_model gui
```

### 5.3 Running the test suite

```bash
# With src layout on PYTHONPATH
PYTHONPATH=src python -m pytest -q
# or
python -m pytest -q
```

At the document snapshot the collector reports **482 tests collected**.

---

## 6. Conceptual data model

The pipeline reasons over four analytical levels (`analytical_levels/`):

1. **Production instruction** (`ProductionInstruction`): what the player physically does — left hand, bow-contact region, mute, bowing, timbre-execution target, performance context.
2. **Acoustic result** (`AcousticDescriptorObservation`, precomputed EWSD scalars).
3. **Perceptual organization** (`PerceptualOrganizationAssessment`).
4. **Musical-textural function** (`TexturalFunctionAssessment`; stub only).

The scalar EWSD number lives at level 2 and is treated as **precomputed** (see §11): the repository does not re-derive EWSD from an audio spectrum in this commit.

Explicit non-implications:

- A technique label does not determine EWSD.
- An acoustic descriptor value does not determine a textural function.
- Perceptual/textural conclusions require contextual variables.

---

## 7. Metadata schema

### 7.1 Ordinary register row (manual entry / research Excel / Orchidea)

Fields:

- `note`: scientific pitch name (e.g. `G3`, `A#4`).
- `midi`: integer MIDI number (0..127).
- `value`: numeric EWSD acoustic-balanced score (positive).
- `instrument`: one of `vln`, `vla`, `vlc`, `cb`.
- `dynamic`: one of `ppp`, `pp`, `mp`, `mf`, `f`, `ff`, `fff` (categorical order enforced in `baseline.DYNAMIC_ORDER`).
- `technique`: `ordinary` / `ordinario` / `arco` / `arco_normal` for baseline rows.
- `quantity`: descriptor identifier, default `EWSD_score_acoustic_balanced`.
- `source_path`, `source_workbook_path`, `source_workbook_hash`, `source_sheet`, `import_run_id`, `source_row_id`: provenance.
- `data_status`: one of `measured_real`, `measured_research_data`, `manual_register_entry`, `synthetic`, `synthetic_integration_test`, `mixed`, `unknown`.
- `scientific_use`: e.g. `prohibited_for_doctoral_evidence` (mandatory tag for synthetic rows).

### 7.2 Extrapolation result row

The full schema of `ExtrapolationResult` (`extrapolation/nonlinear/domain.py`) includes, in addition to identity fields:

- Neutral estimate fields: `estimate_mean`, `estimate_median`, `estimate_sd`, `interval_low`, `interval_high`, `interval_type`.
- Bayesian-only fields (populated only when `bayesian_backend_used=True`): `posterior_mean`, `posterior_median`, `posterior_sd`, `credible_interval_low`, `credible_interval_high`.
- Log-ratio parameters: `log_ratio_mean`, `log_ratio_sd`, `technique_multiplier`, `alpha_t`, `alpha_origin`, `effect_kind`.
- Model selection: `model_family`, `selected_model_id`, `candidate_model_ids`, `rejected_model_ids`, `rejection_reasons`, `selection_reason`, `fallback_level`, `complexity_level`, `model_selection_status`.
- Harmonic geometry: `harmonic_type`, `harmonic_order`, `string_name`, `stopped_pitch`, `touched_pitch`, `open_string_pitch`, `sounding_pitch`, `sounding_midi`, `sounding_midi_float`, `sounding_frequency_hz`, `cents_deviation`, `nearest_tempered_pitch`, `physical_range_min`, `physical_range_max`, `analysis_range_min`, `analysis_range_max`, `selection_mode`, `configuration_policy`, `configured_order_min`, `configured_order_max`, `order_selection_reason`.
- Evidence and provenance: `evidence_tier`, `assumption_ids`, `assumptions_trace`, `source_ids`, `data_status`, `scientific_use`, `source_workbook_path`, `source_workbook_hash`, `source_sheet`, `import_run_id`, `source_row_ids`, `value_kind`, `warnings`, `diagnostics_status`, `convergence_status`, `sensitivity_status`, `model_status`, `na_reason`.

`data_status = synthetic` implies `scientific_use = prohibited_for_doctoral_evidence` at the export layer.

---

## 8. Pitch registry and formulas

Pitch handling lives in `src/string_technique_model/manual_entry/pitch.py` (with helpers in `baseline/pitch.py` and `pitch/registry.py`).

### 8.1 Formula — MIDI to frequency

**Equation.**

$$
f(m) = 440 \cdot 2^{(m - 69)/12}
$$

**Symbols.**

| Symbol | Definition | Unit | Code field |
|---|---|---|---|
| $m$ | MIDI note number | dimensionless | `midi` |
| $f(m)$ | Sounding frequency at MIDI $m$ | Hz | `sounding_frequency_hz` |
| $A_4$ | Reference pitch (hard-coded) | Hz | constant `440.0` |
| $m_{\mathrm{ref}}$ | Reference MIDI (hard-coded) | dimensionless | constant `69` |

**Implementation.** `manual_entry/pitch.py::midi_to_hz`.

**Assumptions.** 12-tone equal temperament; $A_4 = 440$ Hz fixed; no explicit alternative reference pitch.

**Status:** **IMPLEMENTED**.

### 8.2 Formula — frequency to MIDI

**Equation.**

$$
m(f) = 69 + 12 \log_2\!\left(\frac{f}{440}\right)
$$

**Implementation.** `manual_entry/pitch.py::hz_to_midi`. Returns `None` for non-finite or non-positive $f$.

**Status:** **IMPLEMENTED**.

### 8.3 Cents deviation from equal temperament

**Equation.**

$$
c = 1200 \cdot \log_2\!\left(\frac{f_n}{f_{\mathrm{ET}}}\right)
$$

where $f_n$ is the physical partial frequency and $f_{\mathrm{ET}}$ is the frequency of the nearest equal-tempered MIDI note.

In the harmonic register generator this is computed as

$$
c = (m_{\mathrm{float}} - \mathrm{round}(m_{\mathrm{float}})) \cdot 100
$$

with $m_{\mathrm{float}} = 69 + 12 \log_2(f_n / 440)$.

**Implementation.** `extrapolation/nonlinear/harmonic_register.py::_cents_deviation`.

**Status:** **IMPLEMENTED**.

### 8.4 Chromatic registry

`src/string_technique_model/pitch/registry.py` exposes the complete chromatic MIDI space $\{0, 1, \dots, 127\}$; an instrument-range filter is optional.

---

## 9. Technique ontology

The ontology (`configs/technique_ontology.yaml`) declares:

- **Left-hand regimes:** `ordinary_stopped`, `natural_harmonic`, `artificial_harmonic`, `half_harmonic`, `natural_harmonic_glissando`, `artificial_harmonic_glissando`, `multiphonic`.
- **Bow-contact categories:** ordered continuum on the speaking string from `sul_tasto` through neutral to `sul_ponticello`, plus off-continuum regions `directly_on_bridge` and `afterlength`.
- **Mute categories:** performance, light practice, heavy practice, historical, adjustable partial, and legacy orchestral/hotel labels.
- **Timbre execution targets:** e.g. `flautando`, distinct from bow-contact categories.
- **Harmonic interval $\leftrightarrow$ order map (allowed):** `P4 -> 4`, `M3 -> 5`, `m3 -> 6`, `P5 -> 3`.

Technique-to-family routing in the model-selection engine (`extrapolation/nonlinear/model_selection.py::TECHNIQUE_TO_FAMILY`):

| Technique | Family |
|---|---|
| `ordinary`, `ordinario`, `arco`, `arco_normal` | `ordinary_baseline_model` |
| `sul_tasto`, `sul_ponticello` | `bow_contact_model` |
| `con_sordino` | `mute_transfer_model` |
| `natural_harmonic`, `artificial_harmonic` | `harmonic_modal_model` |
| `multiphonics`, `multiphonic` | `multiphonic_component_model` |
| `flautando` | `execution_target_model` |

Composability rules and non-inversion between `sul_tasto` and `sul_ponticello` are enforced explicitly: they are not mirror images of one another.

---

## 10. Acoustic descriptor backend

The descriptor backend (`src/string_technique_model/descriptors/`) is separate from EWSD prediction. It exposes reproducible acoustic features on audio, with all analysis parameters recorded on each `DescriptorResult` (no silent defaults). Registry: `configs/acoustic_descriptors.yaml` (version `0.5.0-descriptor-backend`). Default profile: `configs/analysis_profiles/default_descriptor_v1.yaml`.

STFT defaults:

- `sample_rate_hz`: 44100
- `fft_size`: 4096
- `window_type`: `hann`
- `hop_size`: 1024
- `frequency_min_hz`: 50.0
- Weighting: `power` for centroid unless overridden

### 10.1 Spectral centroid

**Descriptor ID:** `DESC_SPECTRAL_CENTROID`, method `spectral_centroid_v1`.

**Equation.**

$$
C = \frac{\sum_{k} f_k \, W_k}{\sum_{k} W_k}
$$

with $W_k \in \{\lvert X_k \rvert, \lvert X_k \rvert^2\}$ (magnitude or power weighting, configured explicitly). The reported value is the mean of per-frame centroids across STFT frames.

**Symbols.**

| Symbol | Definition | Unit |
|---|---|---|
| $f_k$ | Frequency of FFT bin $k$ | Hz |
| $W_k$ | Weight of bin $k$ (magnitude or power) | linear |
| $C$ | Per-frame spectral centroid | Hz |

**Implementation.** `descriptors/centroid.py::compute_spectral_centroid`.

**Assumptions.** Non-silent frame; weighting kind is declared and preserved in output.

**Status:** **IMPLEMENTED**.

### 10.2 Spectral slope

**Descriptor ID:** `DESC_SPECTRAL_SLOPE`, method `spectral_slope_logfreq_db_linreg_v1`.

**Equation.** OLS slope of dB-power versus $\log_{10}$ frequency:

$$
y_k = 10 \log_{10}(P_k), \qquad x_k = \log_{10}(f_k),
$$

$$
\hat{\beta} = \frac{\sum_k (x_k - \bar{x})(y_k - \bar{y})}{\sum_k (x_k - \bar{x})^2}, \quad \text{unit: dB per decade of } \log_{10}\text{Hz}
$$

DC is excluded; band defaults to `[100 Hz, 5000 Hz]`.

**Implementation.** `descriptors/slope.py::compute_spectral_slope`.

**Status:** **IMPLEMENTED**.

### 10.3 Harmonic-to-noise ratio (spectral-mask)

**Descriptor ID:** `DESC_HNR`, method `hnr_spectral_mask_v1`.

**Equation.**

$$
\mathrm{HNR}_{\mathrm{mask}} = 10 \log_{10}\!\left(\frac{E_h}{E_n}\right)
$$

where $E_h = \sum_{k \in \mathcal{M}_h} P_k$ is the power inside $\pm b$-bin harmonic masks centred at $k f_0$ for $k = 1, \dots, K$, and $E_n = \sum_{k \notin \mathcal{M}_h} P_k$ is the complementary residual power.

**Assumptions.** This is the **spectral-mask** definition; it is **not** autocorrelation HNR and **not** harmonic-model residual HNR.

**Implementation.** `descriptors/hnr.py::spectral_mask_hnr_db`.

**Status:** **IMPLEMENTED**.

### 10.4 Spectral flux

**Descriptor ID:** `DESC_SPECTRAL_FLUX`, method `spectral_flux_l1_halfwave_v1`.

**Equation.** For adjacent frames with $L_1$-normalised magnitude spectra $\tilde{M}_t$:

$$
\mathrm{Flux}(t) = \sum_{k} \max\!\bigl(0,\; \tilde{M}_t(k) - \tilde{M}_{t-1}(k)\bigr)
$$

The scalar descriptor is the mean of $\mathrm{Flux}(t)$ across frame transitions.

**Implementation.** `descriptors/flux.py`.

**Status:** **IMPLEMENTED**.

### 10.5 Long-term average spectrum

**Descriptor ID:** `DESC_LTAS`, method `ltas_mean_power_v1`.

**Equation.**

$$
\mathrm{LTAS}(k) = \frac{1}{T} \sum_{t=1}^{T} P_t(k)
$$

where $P_t(k)$ is the power at bin $k$ in frame $t$.

**Implementation.** `descriptors/ltas.py`.

**Status:** **IMPLEMENTED** (vector-valued).

### 10.6 Frame-level spectral variance (temporal)

**Descriptor ID:** `DESC_FRAME_SPECTRAL_VARIANCE`, method `frame_spectral_variance_centroid_v1`.

**Equation.** Temporal variance of per-frame spectral centroids:

$$
V_t(C) = \frac{1}{T - 1} \sum_{t=1}^{T} (C_t - \bar{C})^2, \quad \text{unit: Hz}^2
$$

**Note.** This is distinct from within-frame spectral spread.

**Implementation.** `descriptors/variance.py`.

**Status:** **IMPLEMENTED**.

### 10.7 Attenuation (typed)

**Descriptor ID:** `DESC_ABSOLUTE_ATTENUATION`, method `typed_attenuation_v1`.

**Equations.**

$$
\mathrm{dB}_{\mathrm{amp}} = 20 \log_{10}\!\left(\frac{A_2}{A_1}\right), \qquad
\mathrm{dB}_{\mathrm{pow}} = 10 \log_{10}\!\left(\frac{P_2}{P_1}\right)
$$

$$
\frac{A_2}{A_1} = 10^{\mathrm{dB}/20}, \qquad
\frac{P_2}{P_1} = 10^{\mathrm{dB}/10}
$$

**Implementation.** `descriptors/attenuation.py`.

**Assumptions.** Amplitude and power ratios are typed and refuse cross-conversion; sones are refused as dB (`refuse_sones_as_db`); bridge-mobility attenuation cannot be reported as radiated SPL.

**Status:** **IMPLEMENTED**.

### 10.8 Partials

**Descriptor IDs:** `DESC_PARTIAL_SALIENCE`, `DESC_PITCH_COMPONENT_COUNT` — peak-based, with configurable prominence, minimum separation, and amplitude thresholds. Synthetic multi-sinusoids are numerical proxies, not physical multiphonics.

**Status:** **IMPLEMENTED** (proxies).

### 10.9 Unresolved descriptors

`DESC_TEMPORAL_MODULATION`, `DESC_ATTACK_TIME`, `DESC_LOUDNESS`, `DESC_FUNDAMENTAL_SALIENCE`, `DESC_UPPER_PARTIAL_ENERGY_RATIO`, `DESC_BRIDGE_MOBILITY`, `DESC_INTER_PLAYER_VARIABILITY` — declared in the registry as `implemented: false`.

**Status:** **PLANNED**.

> **Warning — descriptor $\ne$ EWSD.** All descriptors carry `ewsd_compatibility = incompatible_without_activated_mapping`. Descriptor outputs must not be used as EWSD numbers without a registered, curator-validated transfer function.

---

## 11. EWSD score and the identity metric

`EWSD_score_acoustic_balanced` (short name `CDM_TD`) is a **precomputed** upstream acoustic-balanced density score. Its numerical values enter the repository through curated collections; the repository does **not** recompute EWSD from a spectrum in this commit.

### 11.1 Formula — canonical metric map

**Equation.**

$$
\Phi(D) = D
$$

(identity on the precomputed scalar; declared explicitly in `configs/density_metric.yaml`).

**Implementation.** `density/metric.py::DensityMetric.phi`.

**Status:** **IMPLEMENTED_FALLBACK** — the metric map is an identity because a validated transfer function is not present.

### 11.2 Honesty about the acoustic transfer function

The internal registry `_EWSD_TRANSFER_FUNCTIONS` (`extrapolation/nonlinear/descriptor_model.py`) is **empty**. Consequently, `ewsd_mapping_status("EWSD_score_acoustic_balanced")` returns `observed_scalar_direct_model`.

The intended acoustic transfer is a function $F$ of a spectral descriptor tuple:

$$
D \;\stackrel{?}{=}\; F(D_1, D_2, \dots, D_k)
$$

**No such $F$ is implemented.** The system therefore models $D$ as a directly observed scalar and reports the model reduction as `observed_scalar_direct_model` on every export.

**Status:** the reference relationship $D = F(D_1, \dots, D_k)$ is a **REFERENCE_MODEL** for future work; not evaluated numerically in this commit.

> **Warning.** Do not describe cells produced from this identity metric as spectral EWSD predictions. They are model-reduced estimates on the measured scalar.

---

## 12. Ordinary baseline

The ordinary baseline is a smooth function of MIDI pitch, fitted per instrument and per dynamic.

### 12.1 Formula — log-linear penalized B-spline baseline

**Equation.**

$$
\log B_{i, d}(p) \;=\; \beta_{0,\, i, d} \;+\; s_{i, d}(p),
\qquad
B_{i, d}(p) \;=\; \exp\!\bigl(\beta_{0,\, i, d} + s_{i, d}(p)\bigr)
$$

with $p$ the MIDI pitch of the observation and $s_{i,d}$ a penalized cubic B-spline (see §13).

**Symbols.**

| Symbol | Definition | Unit / Domain |
|---|---|---|
| $i$ | Instrument identifier | `vln`, `vla`, `vlc`, `cb` |
| $d$ | Dynamic identifier | `pp`, `mf`, `ff`, ... |
| $p$ | MIDI pitch | 0..127 |
| $B_{i,d}(p)$ | Ordinary baseline EWSD estimate | same as $D$ |
| $\beta_{0}$ | Intercept in log-space | same as $\log D$ |
| $s_{i,d}(p)$ | Penalized cubic B-spline term | dimensionless in log-space |

**Implementation.**

- `extrapolation/nonlinear/baseline.py::fit_ordinary_baseline`
- `extrapolation/nonlinear/splines.py::fit_penalized_bspline`
- Config: `configs/extrapolation_models.yaml` (`penalty_lambda: 1.0`, `spline_degree: 3`, `n_basis: 8`, `log_transform: true`, `quantity: EWSD_score_acoustic_balanced`).

**Assumptions.** Only rows with `technique` in `{ordinary, ordinario, arco, arco_normal}` are used. `value` must be strictly positive (else the routine raises). Groups with fewer than 2 rows are skipped. The intercept carries **no penalty**; only spline coefficients do.

**Status:** **IMPLEMENTED**.

### 12.2 Prediction from a baseline fit

For any query MIDI $p^\star$:

$$
\hat{B}_{i,d}(p^\star) \;=\; \exp\!\bigl(\hat{\beta}_{0} + s_{i,d}(p^\star)\bigr)
$$

and a boolean flag `outside_baseline_range` is raised when $p^\star \notin [p_{\min}, p_{\max}]$ of the fitted MIDI domain.

**Status:** **IMPLEMENTED**.

### 12.3 Residual scale

The routine estimates a residual standard deviation

$$
\hat{\sigma}_{\mathrm{res}} \;=\; \sqrt{\frac{1}{\nu} \sum_{n} \bigl(y_n - \hat{y}_n\bigr)^2},
\qquad \nu = \max(1, N - K - 1)
$$

where $K$ is the number of spline basis columns and $N$ is the observation count. It is used only as descriptive metadata; it is not the technique-level $\sigma$ used for intervals.

**Status:** **IMPLEMENTED**.

---

## 13. Splines and regularization

### 13.1 Cubic B-spline basis

Open uniform knot vectors are constructed with boundary knots repeated $\text{degree} + 1$ times:

$$
\mathbf{t} \;=\; \bigl(\,\underbrace{x_{\min}, \dots, x_{\min}}_{\text{degree}+1},\, t_1, \dots, t_{n_{\mathrm{int}}},\, \underbrace{x_{\max}, \dots, x_{\max}}_{\text{degree}+1}\,\bigr)
$$

Default degree is $3$; default number of basis columns is $n_{\mathrm{basis}} = 8$. Basis evaluation uses SciPy's `BSpline` where available and a Cox--de Boor recursion as fallback (`extrapolation/nonlinear/splines.py::_de_boor_basis`).

**Status:** **IMPLEMENTED**.

### 13.2 Penalized least squares

**Formula — P-spline objective.**

$$
\hat{\boldsymbol{\beta}} \;=\; \arg\min_{\boldsymbol{\beta}} \; \bigl\lVert \mathbf{y} - \mathbf{B}\boldsymbol{\beta} \bigr\rVert_{2}^{2} \;+\; \lambda \, \boldsymbol{\beta}^{\top} \mathbf{P} \boldsymbol{\beta}
$$

with second-difference penalty

$$
\mathbf{P} \;=\; \mathbf{D}_2^{\top} \mathbf{D}_2,
\qquad
(\mathbf{D}_2 \boldsymbol{\beta})_i \;=\; \beta_i - 2\beta_{i+1} + \beta_{i+2}
$$

**Symbols.**

| Symbol | Definition |
|---|---|
| $\mathbf{B}$ | Design matrix, shape $(N, K)$ |
| $\boldsymbol{\beta}$ | Coefficient vector, length $K$ |
| $\lambda$ | Penalty strength, `penalty_lambda` in YAML (default `1.0`) |
| $\mathbf{D}_2$ | Second-difference operator |

**Closed-form solution.**

$$
\hat{\boldsymbol{\beta}} \;=\; \bigl(\mathbf{B}^{\top}\mathbf{B} \;+\; \lambda \mathbf{P}\bigr)^{-1} \mathbf{B}^{\top} \mathbf{y}
$$

**Implementation.**

- `extrapolation/nonlinear/splines.py::second_difference_penalty_matrix`
- `extrapolation/nonlinear/splines.py::fit_penalized_bspline`

**Assumptions.** OLS + RW2-style penalty; the penalty acts only on B-spline coefficients (not on any intercept augmented outside the basis).

**Status:** **IMPLEMENTED**.

### 13.3 Extrapolation flag

`predict_bspline` marks any query point outside $[x_{\min}, x_{\max}]$ with `outside_range=True`. Callers must either widen uncertainty or refuse extrapolation.

**Status:** **IMPLEMENTED**.

---

## 14. Automatic model selection

Model selection is an explicit function:

$$
M^{\star} \;=\; \mathcal{S}(T,\, Q,\, \mathcal{D},\, E,\, C)
$$

with

- $T$ = technique identifier,
- $Q$ = target quantity (`EWSD_score_acoustic_balanced` or a registered descriptor),
- $\mathcal{D}$ = data availability audit (observations, distinct pitches, span, covariates, spectra),
- $E$ = evidence tier hint,
- $C$ = configuration (`configs/extrapolation_model_selection.yaml`).

**Status of the selection engine:** **IMPLEMENTED** (`extrapolation/nonlinear/model_selection.py`).

### 14.1 Thresholds

From `configs/extrapolation_model_selection.yaml`:

| Threshold | Value |
|---|---|
| `min_distinct_pitches_for_linear` | 3 |
| `min_distinct_pitches_for_spline` | 6 |
| `min_pitch_span_semitones_for_spline` | 12 |
| `min_observations_for_linear` | 3 |
| `min_observations_for_spline` | 6 |
| `min_design_rank_ratio` | 0.85 |

### 14.2 Complexity ladder

Ascending: `M0_constant_effect` $\rightarrow$ `M1_regularized_linear_trend` $\rightarrow$ `M2_penalized_register_spline` $\rightarrow$ `M3_hierarchical_instrument_dynamic` $\rightarrow$ `M4_physical_informed` $\rightarrow$ `M5_spectral_or_modal_specific`.

### 14.3 Families and gates

| Family | Techniques | Mechanism |
|---|---|---|
| `ordinary_baseline_model` | ordinary/ordinario/arco/arco_normal | ordinary excitation |
| `bow_contact_model` | sul_tasto, sul_ponticello | bow-contact point modifies excitation |
| `mute_transfer_model` | con_sordino | mute modifies bridge/body transmission |
| `harmonic_modal_model` | natural_harmonic, artificial_harmonic | nodal touch selects modal participation |
| `multiphonic_component_model` | multiphonic(s) | qualitative only |
| `execution_target_model` | flautando | qualitative only; never routed as sul_tasto |

### 14.4 Harmonic gate semantics (critical)

Two harmonic gate states are represented separately:

- `harmonic_modal_metadata_gate` — selected when modal metadata is incomplete (missing string, harmonic order, sounding pitch, or baseline semantics). `selection_reason_if_chosen = insufficient_harmonic_metadata`.
- `harmonic_modal_acoustic_model_unavailable` — selected when modal metadata is complete but no acoustic calibration exists. `selection_reason_if_chosen = no_harmonic_acoustic_calibration_data`. `model_status = modal_frequencies_generated_acoustic_values_unavailable`.

The `harmonic_modal_metadata_gate` is **only applicable when metadata is incomplete**. When metadata is complete, the gate is rejected with reason `gate_not_applicable_modal_metadata_complete` (this is not a failed requirement — it is a scope declaration).

The engine strictly separates:

- `missing_covariates` (modal geometry that the user must supply),
- `missing_model_components` (in particular, `calibrated_harmonic_descriptor_model`).

The audit fields on the decision expose both `modal_metadata_status` (`complete` / `incomplete`) and `acoustic_calibration_status` (`available` / `unavailable`).

**Status:** **IMPLEMENTED**.

### 14.5 Policy invariants

- Never auto-select the most complex model by default.
- Refuse `M4_physical_informed` without required physical covariates.
- Refuse constant-factor path for harmonic families (`refuse_constant_factor_for_harmonics: true`).
- Refuse `flautando` as `sul_tasto`.
- Numeric assumptions are authorised only when the flag `authorize_numeric_assumption_when_zero_obs` is true; otherwise the fallback is qualitative or NA.

**Status:** **IMPLEMENTED**.

### 14.6 Evidence tier hint

`assess_data_availability` and `select_model` classify cells into an evidence tier for downstream reporting. Tiers:

- `LEVEL_0_UNSUPPORTED`
- `LEVEL_1_ASSUMPTION_ONLY`
- `LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE`
- `LEVEL_2_METADATA_CONSTRAINED`
- `LEVEL_3_PARTIAL_EMPIRICAL`
- `LEVEL_4_MATCHED_EMPIRICAL`

**Status:** **IMPLEMENTED**.

---

## 15. Constant-effect fallback

When no target-technique observations exist (and numeric assumptions are authorised), the bow-contact submodel falls back to a **constant technique effect** carried by an assumption prior.

### 15.1 Formula — constant fallback

**Equation.**

$$
Y_{i, d, t}(p) \;=\; B_{i, d}(p) \cdot \exp(\alpha_t)
$$

$\alpha_t$ is the mean of the corresponding prior (see §17). The `alpha_origin` field records that the coefficient is a `regularization_assumption`, not an empirical fit.

**Symbols.**

| Symbol | Definition |
|---|---|
| $Y_{i,d,t}$ | Technique-level estimate |
| $B_{i,d}$ | Ordinary baseline (from §12) |
| $\alpha_t$ | Constant log-ratio effect for technique $t$ |

**Status:** **IMPLEMENTED_FALLBACK** (`selected_model_id = constant_technique_effect_over_smoothed_baseline`).

### 15.2 Interval type when constant

Constant-effect predictions are marked `prior_dominated = True` and their intervals are **assumption distribution intervals**, not confidence or posterior credible intervals (see §22).

---

## 16. Register-dependent technique model

When technique observations exist, the log-ratio can carry a register-dependent shape term.

### 16.1 Formula — register-dependent multiplicative technique model

**Equation.**

$$
Y_{i, d, t}(p) \;=\; B_{i, d}(p) \cdot \exp\!\bigl(\alpha_t + g_t(p)\bigr)
$$

with $g_t \equiv 0$ when the register shape is not identified. When identified, $g_t$ is either a ridge-regularized linear trend or a penalized cubic B-spline in MIDI, fitted on the log-ratio $\log(y_n / \hat{B}_{i,d}(p_n))$.

**Symbols.**

| Symbol | Definition |
|---|---|
| $\alpha_t$ | Constant log-ratio intercept for technique $t$ |
| $g_t(p)$ | Register-dependent shape (linear or penalized spline) |
| $Y$ | Technique-level EWSD estimate |
| $B$ | Ordinary baseline (§12) |

**Implementation.** `extrapolation/nonlinear/bow_contact_model.py::fit_bow_contact_effect` and `BowContactFit.predict`.

**Assumptions.**

- The multiplicative log-ratio structure is the primary modelling choice; if $g_t$ is not identified, only $\alpha_t$ is retained.
- The technique-level intercept is either estimated from the log-ratios of observed data or drawn from the prior when no observations exist.

**Status:** **IMPLEMENTED**.

### 16.2 Register-shape identification

`shape_mode` is chosen from the `selected_model_id`:

- `constant_technique_effect_over_smoothed_baseline` $\rightarrow$ `constant`
- `regularized_linear_register_trend` $\rightarrow$ `linear`
- `penalized_register_spline` $\rightarrow$ `spline`

`register_shape_identified` is true only for `linear` or `spline`.

**Status:** **IMPLEMENTED**.

---

## 17. Hierarchical model — implemented approximation vs planned Bayesian model

### 17.1 Planned hierarchical model

The **REFERENCE_MODEL** (target formulation) is a hierarchical Bayesian model where technique intercepts and shape terms share partial pooling across instruments and dynamics, with priors:

- $\alpha_t \sim \mathcal{N}(\mu_t^{(\mathrm{prior})}, \sigma_t^{(\mathrm{prior})\,2})$
- Spline coefficients $\boldsymbol{\beta}$ under an RW2 penalty (RW2-style prior).
- $\sigma \sim \mathrm{HalfNormal}(1)$ residual scales for technique and baseline.

Priors are loaded from `configs/extrapolation_priors.yaml`. The `M3_hierarchical_instrument_dynamic` rung is `enabled: false` in the model-selection config.

**Status:** **PLANNED** (hierarchical rung is disabled).

### 17.2 Implemented approximation

What is actually shipped is:

- OLS baseline fit with a second-difference penalty ($\S 12$--$13$).
- Ridge-regularized linear fit on the log-ratio (`_fit_ridge_linear` with $\lambda = 2$).
- Penalized B-spline fit on the log-ratio.
- Optional Bayesian log-ratio spline (see §23), only when PyMC/ArviZ are installed.

**Status:** **IMPLEMENTED_FALLBACK** for the non-Bayesian pathway.

---

## 18. Bow-contact model

Bow-contact techniques (`sul_tasto`, `sul_ponticello`) use the register-dependent multiplicative log-ratio (§16).

### 18.1 Alpha priors (assumptions)

From `configs/extrapolation_priors.yaml`:

- `alpha_t_sul_tasto`: $\mathcal{N}(\text{mean}=-0.12,\ \text{sd}=0.50)$, `activation_status: active`, `source: regularization_assumption`.
- `alpha_t_sul_ponticello`: $\mathcal{N}(\text{mean}=+0.20,\ \text{sd}=0.55)$, `activation_status: active`, `source: regularization_assumption`.
- `sigma_technique_residual`: `HalfNormal(sd=1.0)`.
- `sigma_spline_smooth`: `HalfNormal(sd=1.0)`.

**Assumption identifiers surfaced in exports:**

- `ASSUMP_SUL_TASTO_ALPHA_MINUS_012`
- `ASSUMP_SUL_PONTICELLO_ALPHA_PLUS_020`
- `sul_tasto_and_sul_ponticello_are_not_inverse_transforms`

**Status:** **ASSUMPTION**.

> **Warning.** These centres are **regularization assumptions**, not empirical fits. `sul_tasto` and `sul_ponticello` are **not** inverse transforms of one another (magnitudes deliberately differ).

### 18.2 Fitting logic

`fit_bow_contact_effect` (`extrapolation/nonlinear/bow_contact_model.py`) picks a shape mode from the selected model id:

- If `shape_mode = constant` or no observations exist: $\hat{\alpha}_t$ is the prior mean (`prior_dominated = True`) or the empirical mean log-ratio (`prior_dominated = False` when observations exist).
- If `shape_mode = linear`: ridge-regularized linear trend on the log-ratio.
- If `shape_mode = spline`: penalized cubic B-spline on the log-ratio.

Total log-ratio uncertainty:

$$
\sigma_{\log R} \;=\; \sqrt{\sigma_{\alpha}^{2} + \sigma_{\mathrm{res}}^{2}}
$$

**Status:** **IMPLEMENTED**.

### 18.3 Interval semantics for bow-contact predictions

- When `prior_dominated = True`: `interval_type = assumption_distribution_interval`.
- When `prior_dominated = False`: `interval_type = approximate_predictive_interval_logR`.

**Status:** **IMPLEMENTED**.

---

## 19. Mute model

The mute submodel (`extrapolation/nonlinear/mute_model.py`) applies a log-ratio effect $\alpha_{\mathrm{mute}}$ (optionally with a shape term) to the ordinary baseline.

### 19.1 Formula — dB to log-ratio mapping

**Equation.**

$$
\alpha_{\mathrm{mute}} \;=\; \log\!\bigl(10^{\,-\Delta_{\mathrm{dB}}/10}\bigr)
$$

With the ASSUMPTION `EWSD proportional to power` (`ASSUMP_EWSD_PROPORTIONAL_TO_POWER`), a $\Delta_{\mathrm{dB}}$ dB power reduction on ordinary $\rightarrow$ muted maps to the log-ratio above.

Reference constants (priors, `configs/extrapolation_priors.yaml`):

- Violin: $\Delta_{\mathrm{dB}} \approx 6$ dB $\Rightarrow \alpha_{\mathrm{mute, vln}} \approx \log(10^{-0.6}) \approx -0.691$; prior `alpha_mute_vln` centred at $-0.691151$, sd $= 0.35$.
- Viola: $\Delta_{\mathrm{dB}} \approx 4$ dB $\Rightarrow \alpha_{\mathrm{mute, vla}} \approx -0.461$; prior `alpha_mute_vla` centred at $-0.460517$, sd $= 0.35$.
- Generic (cello/contrabass fallback): `alpha_mute_generic` centred at $-0.25$, sd $= 0.90$, `activation_status: fallback_only`.

**Assumption identifiers surfaced in exports:**

- `ASSUMP_MUTE_ATTENUATION_6DB` (violin)
- `ASSUMP_MUTE_ATTENUATION_4DB` (viola)
- `ASSUMP_MUTE_GENERIC_ALPHA`
- `ASSUMP_EWSD_PROPORTIONAL_TO_POWER`

**Status:** **ASSUMPTION** for the mapping; **IMPLEMENTED_FALLBACK** for how it is applied.

### 19.2 Fitting modes

`fit_mute_effect` selects a `shape_mode` from the model id:

- `qualitative` (`qualitative_or_na_mute`),
- `constant` (`constant_assumption_fallback`),
- `linear` (`scalar_descriptor_approximation_linear`),
- `spline` (`scalar_descriptor_approximation_spline`),
- `spectral` (`spectral_transfer_model`).

Heavy-mute markers (e.g. `heavy_practice`, `weighted`, `sordino_pesado`) are refused from the `standard_performance_orchestral` path.

**Status:** **IMPLEMENTED** for scalar and constant fallbacks; the `spectral_transfer_model` rung requires spectra/LTAS to be present (only accepted, no numerical spectral transfer is coded yet — see §23).

### 19.3 Interval semantics

Same rules as §18.3: prior-dominated mute predictions are labelled `assumption_distribution_interval`.

---

## 20. Harmonic register generator

The harmonic register generator (`extrapolation/nonlinear/harmonic_register.py`) produces sounding pitches from string $\times$ order geometry. **It does not** produce EWSD numbers for those pitches; those cells are `unavailable` (see §21).

### 20.1 Natural harmonics

**Formula.**

$$
f_n \;=\; n \cdot f_{\mathrm{open}}
$$

$$
m_n \;=\; 69 \;+\; 12 \log_{2}\!\left(\frac{f_n}{440}\right)
$$

**Symbols.**

| Symbol | Definition |
|---|---|
| $f_{\mathrm{open}}$ | Sounding frequency of the open string |
| $n$ | Harmonic order (integer $\ge 2$) |
| $f_n$ | Physical partial frequency |
| $m_n$ | Sounding MIDI (floating-point; cents deviation reported) |

**Configuration.** `configs/extrapolation_harmonic_ranges.yaml`:

- `vln`, `vla`: natural orders $\{2, 3, 4, 5, 6, 7, 8\}$; artificial order $4$.
- `vlc`: natural orders $\{2, \dots, 10\}$.
- `cb`: natural orders $\{2, \dots, 12\}$.
- `maximum_sounding_pitch: C8`, `maximum_sounding_midi: 108`.
- `selection_mode: configured_physically_plausible_harmonics`.
- `order_selection_reason: practical_analysis_scope`.

**Status:** **IMPLEMENTED**.

### 20.2 Artificial harmonics

Default order $= 4$, touch interval $= P4$; sounding pitch is approximately $\text{stopped} + 24$ semitones for order $4$:

$$
m_{\mathrm{sounding}} \;=\; m_{\mathrm{stopped}} + \bigl\lfloor 12 \log_{2}(n) + 0.5 \bigr\rfloor,
\quad n = 4 \Rightarrow +24 \text{ semitones}
$$

Configuration policy: `canonical_single_string_assignment` (one canonical stopped–touched pair per sounding pitch; other equivalents are considered redundant for auditing purposes).

**Status:** **IMPLEMENTED**.

### 20.3 Domains

Three explicit domains are surfaced on every harmonic target row and must not be conflated:

1. `physical_harmonic_range` — open strings $\times$ configured orders (computed).
2. `instrument_harmonic_analysis_range` — optional research window per instrument.
3. `user_requested_output_range` — per-run GUI/CLI filter.

**Status:** **IMPLEMENTED**.

### 20.4 Ordinary baseline distance annotation

`annotate_baseline_extrapolation` marks each harmonic sounding pitch as inside/outside the ordinary baseline domain and, if outside, applies a semitone-distance policy:

- Up to `limited_extrapolation_semitones = 3` semitones outside: `limited_out_of_domain_uncertainty_inflated`.
- Up to `physical_or_assumption_semitones = 12`: `requires_physical_spectral_or_explicit_assumption`.
- Beyond that: `default_unavailable_beyond_12_semitones`.

**Status:** **IMPLEMENTED**.

---

## 21. Harmonic model-selection audit

Because the acoustic calibration for harmonics is not implemented, harmonic cells always resolve to one of two gate states:

- `harmonic_modal_metadata_gate`: `selection_reason = insufficient_harmonic_metadata`, `assumption_ids = [ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA]`.
- `harmonic_modal_acoustic_model_unavailable`: `selection_reason = no_harmonic_acoustic_calibration_data`, `assumption_ids = [ASSUMP_HARMONIC_DESCRIPTOR_MODEL_NOT_IMPLEMENTED]`, `model_status = modal_frequencies_generated_acoustic_values_unavailable`.

In both cases:

- `value_kind = unavailable`,
- `fallback_level = no_numeric_fallback`,
- `estimate_mean`, `estimate_median`, `interval_low`, `interval_high` are `None`.

> **Warning.** Harmonic sounding pitches are generated numerically, but their acoustic EWSD values are **not** predicted numerically. Do not read pitch tables as timbre tables.

**Status:** **IMPLEMENTED** for the audit and reporting; the numeric harmonic model is **PLANNED**.

---

## 22. Uncertainty and intervals

### 22.1 Multiplicative log-ratio interval

**Formula.**

$$
L \;=\; B \cdot \exp\!\bigl(\mu_{\log R} - z\,\sigma_{\log R}\bigr),
\qquad
U \;=\; B \cdot \exp\!\bigl(\mu_{\log R} + z\,\sigma_{\log R}\bigr)
$$

with $z = 1.959963984540054$ for a nominal 95 percent level.

**Symbols.**

| Symbol | Definition | Unit |
|---|---|---|
| $B$ | Baseline mean at the target pitch | same as $D$ |
| $\mu_{\log R}$ | Mean of the log-ratio at the target pitch | dimensionless |
| $\sigma_{\log R}$ | Standard deviation of the log-ratio | dimensionless |
| $L, U$ | Interval endpoints on the original scale | same as $D$ |
| $z$ | Standard normal quantile for the requested level | dimensionless |

**Implementation.** `extrapolation/nonlinear/posterior.py::summarize_log_ratio_multiplicative`.

**Status:** **IMPLEMENTED**.

### 22.2 Neutral estimate fields

Every result row carries:

- `estimate_mean`, `estimate_median`, `estimate_sd`;
- `interval_low`, `interval_high`;
- `interval_type` in `{assumption_distribution_interval, approximate_predictive_interval_logR, bayesian_hdi_from_arviz, approximate_additive_interval_original_scale}`.

Bayesian columns (`posterior_mean`, `credible_interval_*`, ...) are **populated only when `bayesian_backend_used = True`**. Otherwise they are `None` in exports.

**Status:** **IMPLEMENTED**.

### 22.3 Assumption distribution interval

When `prior_dominated = True` (typically zero observations and priors carrying the effect), the interval reported is an **assumption distribution interval**, not a classical confidence interval and not a posterior credible interval.

> **Warning.** Assumption distribution intervals reflect the width of the user-supplied prior for $\alpha$, not statistical uncertainty from data. Never label them as posteriors or as confidence intervals.

**Status:** **IMPLEMENTED**.

### 22.4 Legacy additive interval

For non-log paths (constant M0 legacy), the routine emits an additive interval

$$
L \;=\; \mu - z\,\sigma,
\qquad
U \;=\; \mu + z\,\sigma
$$

on the original scale. This is retained for backward compatibility with older audit workbooks; it is **not** the preferred form for log-ratio submodels.

**Status:** **IMPLEMENTED_FALLBACK**.

---

## 23. Optional Bayesian backend

### 23.1 Backend availability

`extrapolation/nonlinear/bayesian_backend.py::check_backend` probes `pymc` and `arviz`. When absent it returns `capability_status = bayesian_backend_unavailable` and the pipeline never fabricates posteriors.

**Status:** **OPTIONAL_BACKEND**.

### 23.2 Bayesian log-ratio spline model

When the backend is available (`pip install -e ".[bayes]"`), the fitted PyMC model is:

$$
\begin{aligned}
\alpha \;&\sim\; \mathcal{N}(0, 1) \\
\boldsymbol{\beta} \;&\sim\; \mathcal{N}\!\Bigl(0,\; \tfrac{1}{\sigma_{\mathrm{smooth}}}\Bigr) \text{ per basis} \\
\text{Potential} \;&\propto\; -\tfrac{1}{2} \bigl\lVert \mathbf{L}\boldsymbol{\beta} \bigr\rVert_{2}^{2} \text{ with } \mathbf{L}\mathbf{L}^{\top} = \mathbf{D}_2^{\top}\mathbf{D}_2 + \varepsilon \mathbf{I} \\
\sigma \;&\sim\; \mathrm{HalfNormal}(1) \\
\mathbf{y} \mid \boldsymbol{\beta}, \alpha, \sigma \;&\sim\; \mathcal{N}\!\bigl(\alpha + \mathbf{B}\boldsymbol{\beta},\; \sigma\bigr)
\end{aligned}
$$

**Status:** **OPTIONAL_BACKEND** (`extrapolation/nonlinear/bayesian_backend.py::fit_bayesian_log_ratio_spline`).

### 23.3 Consequences of an unavailable backend

- `interval_type` remains `approximate_predictive_interval_logR` or `assumption_distribution_interval`.
- `bayesian_backend_used = False`.
- `posterior_*` and `credible_interval_*` fields are set to `None` in exports.
- `Diagnostics` sheet reports `capability_status = bayesian_backend_unavailable`.

> **Warning.** Missing PyMC does not silently degrade to a fake posterior. It degrades to an approximate predictive log-ratio interval that is **explicitly labelled** as such.

**Status:** **IMPLEMENTED**.

---

## 24. Evidence framework

Every predicted cell is tagged with an evidence tier:

| Tier | Meaning |
|---|---|
| `LEVEL_0_UNSUPPORTED` | Technique/family not admissible or no numeric model. |
| `LEVEL_1_ASSUMPTION_ONLY` | Numeric value comes from a user assumption. |
| `LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE` | Qualitative literature attachment; no numeric value. |
| `LEVEL_2_METADATA_CONSTRAINED` | Numeric value constrained by metadata only. |
| `LEVEL_3_PARTIAL_EMPIRICAL` | Numeric value from partial technique observations. |
| `LEVEL_4_MATCHED_EMPIRICAL` | Numeric value from matched empirical observations. |

Assignment logic lives in `extrapolation/nonlinear/model_selection.py::select_model` and in the technique-model fits (bow-contact and mute). Zero observations plus prior-dominated $\alpha \Rightarrow$ `LEVEL_1_ASSUMPTION_ONLY`; six or more observations with an admissible spline $\Rightarrow$ `LEVEL_4_MATCHED_EMPIRICAL`.

**Status:** **IMPLEMENTED**.

---

## 25. Provenance framework

Every result row carries provenance:

- `data_status`: measured / synthetic / mixed / manual entry / unknown.
- `scientific_use`: `prohibited_for_doctoral_evidence` for synthetic rows.
- `source_workbook_path`, `source_workbook_hash`, `source_sheet`, `import_run_id`, `source_row_ids` (list of raw record identifiers).
- `assumption_ids`: `ASSUMP_*` identifiers only. Explanatory strings live in `assumptions_trace`.
- `baseline_record_ids`, `baseline_n_observations`, `baseline_midi_min`, `baseline_midi_max`, `baseline_penalty_lambda`, `baseline_spline_degree`, `baseline_n_knots`.
- `warnings`, `calculation_trace`.
- `sensitivity_status` in `{stable, prior_sensitive, data_limited, outside_baseline_range, not_evaluated}`.

**Status:** **IMPLEMENTED**.

---

## 26. GUI

`string-technique-gui` launches the manual register application (`gui_metadata/extrapolator_app.py`). The GUI enforces a **manual register $\rightarrow$ technique requests** workflow. It is not a browser over legacy metadata tables.

### 26.1 Workflow

1. **Step 1 — Measured register.** Build a note column from `From` to `To` pitches; paste values into the column (European comma accepted). Notes may be edited directly.
2. **Step 2 — Requests.** Tick techniques from `con_sordino`, `sul_tasto`, `sul_ponticello`, `artificial_harmonic`, `natural_harmonic`; optionally set the harmonic sounding range with a `configured_physically_plausible_harmonics` mode; press `Generate from filled register` to produce one request per (note $\times$ technique).
3. **Step 3 — Results.** Press `Run requests`. Results are grouped by technique in the order: `con_sordino`, `sul_tasto`, `sul_ponticello`, harmonics. Export to Excel.

### 26.2 Method combobox

The extrapolation method combobox exposes four values:

- `hierarchical_spline` $\rightarrow$ mapped to `requested_method = automatic` at export.
- `constant` $\rightarrow$ constant-effect fallback (§15).
- `physical_informed_bayesian` $\rightarrow$ Bayesian log-ratio spline when the backend is available; otherwise the approximate log-ratio interval.
- `evidence_only` $\rightarrow$ qualitative-only output (no numeric extrapolation).

### 26.3 Harmonic controls

- `Use physically available harmonic range` checkbox.
- `From` / `To` sounding pitch entries.
- `Mode` combobox with values `configured_physically_plausible_harmonics`, `upper_register_only`, `custom_sounding_range`, `selected_harmonic_orders`.
- Default upper bound: `C8`.

### 26.4 Return to start

A dedicated `Return to start` button in the top bar and in the results tab resets the workflow while preserving the register and the request set for edit-and-re-run cycles.

**Status:** **IMPLEMENTED**.

---

## 27. CLI

Top-level command surface (from `python -m string_technique_model --help`):

```
run, estimate, lookup, gui, collection, baseline, literature,
predict, assumptions, extrapolate, request, nonlinear, stress-test
```

Selected subcommands (see `src/string_technique_model/cli/`):

- `run`, `estimate`, `lookup` — legacy estimation entry points.
- `gui` — launches the manual register GUI.
- `collection register|inspect|validate|import|list|compare` — collection registry.
- `baseline build|inspect|validate|compare-methods` — ordinary baseline utilities.
- `literature inventory|validate|matrix|ledger|scan-corpus|register-source|add-extract|...` — literature layer.
- `predict build|from-ordinary|validate-context|inspect-parameters|explain|sensitivity|validation-status` — legacy evidence-gated prediction.
- `assumptions list|validate|show|activate|deactivate|applicable|audit` — user assumptions.
- `extrapolate grid|fit-baseline|fit-technique|predict|compare|diagnose|export` — the primary extrapolation surface (spline + optional Bayes).
- `request` — note-level requests (measured notes $\rightarrow$ needed notes $\times$ technique).
- `nonlinear fit-baseline|fit-technique|predict|compare|diagnose` — the nonlinear hierarchical extrapolation stack (Phase 1).
- `stress-test acoustics --tier fast|extended|benchmark|all` — scientific acoustics stress runs.

Representative invocations:

```bash
python -m string_technique_model nonlinear diagnose
python -m string_technique_model nonlinear predict \
  --technique sul_ponticello --instrument vln --dynamic pp \
  --research-excel data/research/violin_ordinary.xlsx \
  --export-xlsx outputs/nonlinear_extrapolation_results.xlsx

python -m string_technique_model extrapolate diagnose
python -m string_technique_model extrapolate predict \
  --technique sul_ponticello --instrument vln --dynamic pp

python -m string_technique_model stress-test acoustics --tier fast
```

**Status:** **IMPLEMENTED**.

---

## 28. Configuration

Principal YAML files (`configs/`):

| File | Role |
|---|---|
| `extrapolation_models.yaml` | Spline degree, basis count, penalty $\lambda$, quantity |
| `extrapolation_priors.yaml` | Alpha priors, sigma priors, `sigma_spline_smooth` |
| `extrapolation_model_selection.yaml` | Thresholds, ladder, families, gates, policy |
| `extrapolation_harmonic_ranges.yaml` | Configured orders per instrument, `maximum_sounding_pitch: C8` |
| `extrapolation_targets.yaml` | Target descriptor identifiers |
| `extrapolation_diagnostics.yaml` | Diagnostics thresholds |
| `density_metric.yaml` | Metric identity $\Phi(D)=D$ |
| `model_links.yaml` | Available link functions |
| `acoustic_descriptors.yaml` | Descriptor registry (implemented and unresolved) |
| `analysis_profiles/default_descriptor_v1.yaml` | STFT parameters, weighting, band |
| `technique_ontology.yaml` | Ontology authority |
| `qualitative_acoustic_constraints.yaml` | Qualitative constraint engine |
| `literature_sources.yaml`, `literature_evidence_extracts.yaml`, `literature_parameters.yaml`, `literature_density_mappings.yaml`, `literature_transfers.yaml`, `source_identity_validation.yaml`, `literature_benchmark_cases.yaml`, `literature_conflicts.yaml` | Literature layer |
| `user_assumptions.yaml` | User numerical assumptions (registry empty by default) |
| `measurement_domains.yaml`, `recognition_label_mappings.yaml`, `metric_definitions.yaml`, `metric_conversions.yaml` | Measurement / recognition / metric registries |
| `collections.yaml`, `schemas/*` | Collection adapters |
| `datasets/*` | Dataset stubs (mute datasets, ...) |
| `prediction.yaml`, `prediction_requests.yaml` | Legacy prediction |
| `physical_mechanisms.yaml` | Mechanism catalogue |
| `stress_tolerances.yaml`, `acoustics_stress_tests.yaml` | Stress-test configuration |
| `run.yaml` | Run defaults |

**Status:** **IMPLEMENTED**.

---

## 29. Excel output

`export_nonlinear_workbook` (`extrapolation/nonlinear/export_nonlinear.py`) writes a multi-sheet workbook to `outputs/nonlinear_extrapolation_results.xlsx` by default.

Sheets always present:

| Sheet | Purpose |
|---|---|
| `Methodology` | Selection stages, ladder, config pointers, EWSD honesty statements |
| `Posterior_Summary` | Full row per predicted cell (neutral estimate fields) |
| `All_Results` | Alias of `Posterior_Summary` for GUI compatibility |
| `Note_Level_Results` | Alias of `Posterior_Summary` for older audit filenames |
| `Model_Selection` | Compact selection summary per technique cell |
| `Model_Selection_Audit` | One row per candidate model + rejection reasons |
| `Technique_Effects` | Alpha values, origins, effect kinds, assumption ids |
| `By_Technique` | Cell counts per `technique x instrument x dynamic x model_id` |
| `Diagnostics` | Per-row sigma origin, register-shape identification, prior-domination |
| `Unavailable` | Rows with `value_kind = unavailable` |
| `Run_Summary` | Requested method, exported UTC timestamp, number of assumption intervals, techniques |
| `Model_Comparison` | Optional M0 vs M1 comparison (`compare_models`) |
| `Priors_Used` | Prior specifications with activation status |
| Per-technique sheets | One sheet per technique in the run (name truncated to 31 chars) |

`requested_method = automatic` is written when the caller passes `hierarchical_spline`; the effective control is recorded as `gui_displayed_method` or `cli_method_control`.

**Status:** **IMPLEMENTED**.

---

## 30. Testing and verification

At the document snapshot, `python -m pytest --collect-only -q` reports **482 tests collected** (with `PYTHONPATH=src`). Test categories map to `pytest` markers declared in `pyproject.toml`:

| Marker | Category |
|---|---|
| `mathematical_exact` | Exact algebraic and unit identities |
| `unit_consistency` | Unit conversion consistency |
| `domain_boundary` | Boundary and invalid domain handling |
| `literature_bounded` | Verified literature ranges or categorical claims |
| `literature_directional` | Directional literature claims |
| `measurement_domain` | Measurement-domain separation |
| `physical_plausibility` | Physical plausibility and scope |
| `metamorphic` | Metamorphic relations |
| `adversarial` | Adversarial and malformed inputs |
| `regression` | Regression guards |
| `performance` | Performance and scaling |
| `reproducibility` | Deterministic and seed stability |
| `provenance` | Provenance labelling |
| `assumption_isolation` | User assumptions vs literature |
| `unsupported_extrapolation` | Must refuse unsupported inference |
| `benchmark` | Named benchmark cases |
| `acoustics_stress` | Acoustics stress suite |
| `slow` | Extended-runtime tests |

Notable verification checks:

- Log-exp round-trip identity for the multiplicative interval.
- Interval scaling with baseline: doubling $B$ scales $L$ and $U$ by the same factor.
- Spline recovery on synthetic smooth curves.
- Outside-domain flagging for penalized B-splines.
- Reproducibility across runs with a fixed seed.

> **Warning.** Passing test count is a **software-verification** signal. It does not by itself establish **ecological acoustic validity** for extended-technique EWSD predictions.

**Status:** **IMPLEMENTED**.

---

## 31. Scientific limitations

1. **EWSD acoustic transfer $F(D_1, \dots, D_k)$ is not implemented.** All numeric EWSD outputs for extended techniques rely on either measured scalars (identity $\Phi$) or user-supplied log-ratio priors.
2. **Sul tasto / sul ponticello priors are regularization assumptions**, not empirical fits. They are not inverse transforms.
3. **Mute log-ratio priors assume EWSD proportional to power** and a specific dB attenuation (6 dB violin, 4 dB viola). This does not model spectral shape changes.
4. **Harmonic EWSD values are not predicted.** The generator produces sounding pitches only.
5. **No physical simulation** of the bowed string is provided (no Schelleng boundary, no Woodhouse dynamic model, no bridge admittance model).
6. **No universal technique-to-timbre map** is claimed.
7. **Descriptor coverage is limited.** Loudness, attack time, temporal modulation, bridge mobility, and inter-player variability are unresolved in code.
8. **Instrument imbalance.** Priors are calibrated more tightly for violin/viola than for cello/contrabass; the cello/contrabass mute generic prior has larger sd.
9. **Extrapolation beyond the ordinary baseline domain** is annotated but not silently permitted. Cells beyond 12 semitones of the baseline midi range default to `default_unavailable_beyond_12_semitones`.
10. **Software verification $\ne$ acoustic validity.** Section 30 covers the former; the latter requires empirical calibration campaigns beyond the scope of this commit.

---

## 32. Worked examples (synthetic / illustrative)

> **Warning.** All numbers below are **synthetic / illustrative** and are used only to demonstrate the API and unit handling. They are not measured EWSD values. Any use for doctoral evidence is prohibited (`scientific_use = prohibited_for_doctoral_evidence`).

### 32.1 MIDI to frequency

$$
f(69) \;=\; 440 \cdot 2^{(69 - 69)/12} \;=\; 440 \text{ Hz}
$$

$$
f(60) \;=\; 440 \cdot 2^{(60 - 69)/12} \;\approx\; 261.63 \text{ Hz}
$$

### 32.2 Frequency to MIDI

$$
m(220) \;=\; 69 + 12 \log_{2}(220 / 440) \;=\; 57
$$

### 32.3 Natural harmonic on the violin G string

$G_3$ has $f_{\mathrm{open}} \approx 196.00$ Hz. For $n = 4$:

$$
f_4 \;=\; 4 \cdot 196.00 \;=\; 784.00 \text{ Hz},
\qquad
m_4 \;=\; 69 + 12 \log_{2}(784.00 / 440) \;\approx\; 79.00
$$

Nearest tempered pitch: $G_5$ (MIDI 79).

### 32.4 Artificial harmonic order 4 (touch P4)

Stopped $C_5$ (MIDI 72), touched $F_5$ (MIDI 77), order $= 4$:

$$
m_{\mathrm{sounding}} \;\approx\; 72 + 24 \;=\; 96 \quad (C_7)
$$

### 32.5 Ordinary baseline fit at $p^\star = 72$

Given a fitted violin/mf baseline with intercept $\hat{\beta}_0 = 3.5$ and spline contribution $s(72) = 0.2$ (log-space):

$$
\hat{B}(72) \;=\; \exp(3.5 + 0.2) \;=\; \exp(3.7) \;\approx\; 40.45
$$

### 32.6 Constant-effect fallback for `sul_ponticello`

Using the alpha prior mean $-0.20$... wait, actually the prior for `sul_ponticello` is $+0.20$. With baseline $\hat{B}(72) = 40.45$:

$$
\hat{Y}(72) \;=\; 40.45 \cdot \exp(0.20) \;\approx\; 40.45 \cdot 1.2214 \;\approx\; 49.41
$$

$\sigma_{\alpha} = 0.55$, $\sigma_{\mathrm{res}} = 0$, so $\sigma_{\log R} = 0.55$, $z = 1.95996$:

$$
L \;=\; 40.45 \cdot \exp(0.20 - 1.95996 \cdot 0.55) \;\approx\; 40.45 \cdot \exp(-0.8780) \;\approx\; 16.83
$$

$$
U \;=\; 40.45 \cdot \exp(0.20 + 1.95996 \cdot 0.55) \;\approx\; 40.45 \cdot \exp(1.2780) \;\approx\; 145.11
$$

`interval_type = assumption_distribution_interval`.

### 32.7 Constant-effect fallback for `con_sordino` on violin

$\alpha_{\mathrm{mute, vln}} = \log(10^{-6/10}) \approx -0.691$. With the same baseline:

$$
\hat{Y}(72) \;\approx\; 40.45 \cdot \exp(-0.691) \;\approx\; 40.45 \cdot 0.2512 \;\approx\; 10.16
$$

`assumption_ids = [ASSUMP_MUTE_ATTENUATION_6DB, ASSUMP_EWSD_PROPORTIONAL_TO_POWER]`.

### 32.8 Sul tasto with weak decrease prior

$\alpha_{\mathrm{sul\_tasto}} = -0.12$. Baseline as above:

$$
\hat{Y}(72) \;\approx\; 40.45 \cdot \exp(-0.12) \;\approx\; 40.45 \cdot 0.8869 \;\approx\; 35.87
$$

### 32.9 Harmonic cell (unavailable)

Request: `artificial_harmonic`, violin, pitch $C_7$ (MIDI 96).

- `sounding_pitch = C7`, `sounding_midi = 96`, `harmonic_order = 4`, `string = D` (nearest playable stopped mapping).
- `modal_metadata_status = complete`, `acoustic_calibration_status = unavailable`.
- `selected_model_id = harmonic_modal_acoustic_model_unavailable`.
- `value_kind = unavailable`, `na_reason = no_harmonic_acoustic_calibration_data`, `model_status = modal_frequencies_generated_acoustic_values_unavailable`.
- Numeric fields (`estimate_mean`, `interval_low`, `interval_high`) are `None`.

### 32.10 Model comparison

`compare_models` builds an `M0_constant_legacy` vs `M1_hierarchical_spline` comparison (`extrapolation/nonlinear/comparison.py`). With a synthetic holdout of six rows, one may observe

$$
\mathrm{RMSE}_{M0} \;=\; 4.20, \qquad \mathrm{RMSE}_{M1} \;=\; 2.85 \Rightarrow \mathrm{preferred\_model} = M_1
$$

but the same numbers on a different holdout may prefer $M_0$. The comparison is descriptive, not authoritative.

---

## 33. Glossary and notation

| Symbol / term | Definition |
|---|---|
| $A_4 = 440$ Hz | Reference pitch, hard-coded |
| $m_{\mathrm{ref}} = 69$ | Reference MIDI, hard-coded |
| $m$ | MIDI note number |
| $f$ | Sounding frequency, Hz |
| $c$ | Cents deviation from equal temperament |
| $p$ | MIDI pitch used as covariate for spline fits |
| $B_{i,d}(p)$ | Ordinary baseline function |
| $s_{i,d}(p)$ | Penalized spline term of baseline |
| $\beta_0$ | Baseline intercept (log-space) |
| $\lambda$ | Penalty strength |
| $\mathbf{P} = \mathbf{D}_2^{\top} \mathbf{D}_2$ | Second-difference penalty |
| $\alpha_t$ | Constant log-ratio effect for technique $t$ |
| $g_t(p)$ | Register-dependent shape term |
| $\sigma_{\log R}$ | Log-ratio standard deviation |
| $z$ | Standard normal quantile (about 1.95996 for 95 percent) |
| $\Phi(D)$ | Density metric map, identity here |
| $D$ | Precomputed EWSD acoustic-balanced scalar |
| $D_1, \dots, D_k$ | Spectral descriptors (planned inputs to $F$) |
| $F$ | Not-yet-implemented transfer function to EWSD |
| $\mathrm{HNR}_{\mathrm{mask}}$ | Spectral-mask HNR |
| $C$ | Spectral centroid |
| $V_t(C)$ | Frame-level spectral variance |
| $\mathrm{LTAS}$ | Long-term average power spectrum |
| $\mathrm{dB}_{\mathrm{amp}}$ | Amplitude decibel $= 20 \log_{10}(A_2 / A_1)$ |
| $\mathrm{dB}_{\mathrm{pow}}$ | Power decibel $= 10 \log_{10}(P_2 / P_1)$ |
| EWSD | Precomputed acoustic-balanced density score |
| CDM_TD | Historical short name for EWSD |
| $\mathrm{ASSUMP}\_*$ | Named assumption identifiers surfaced in exports |
| Assumption distribution interval | Interval reflecting user-supplied prior for $\alpha$, not a posterior or confidence interval |
| Approximate predictive log-ratio interval | Interval from $\mu_{\log R}$ and $\sigma_{\log R}$ under normal approximation |
| Register shape identified | True only when the technique effect carries a linear or spline term |
| Prior-dominated | True when the effect is carried by the prior and not by data |
| Software verification | Code computes what the specification says |
| Ecological acoustic validity | Correspondence with real bowed-string acoustics |

---

## Appendix A: Formula inventory

Every formula in the guide is inventoried below with its status tag and code location.

| ID | Section | Formula | Status | Implementation |
|---|---|---|---|---|
| F1 | 8.1 | $f(m) = 440 \cdot 2^{(m-69)/12}$ | IMPLEMENTED | `manual_entry/pitch.py::midi_to_hz` |
| F2 | 8.2 | $m(f) = 69 + 12 \log_2(f/440)$ | IMPLEMENTED | `manual_entry/pitch.py::hz_to_midi` |
| F3 | 8.3 | $c = 1200 \log_2(f_n / f_{\mathrm{ET}})$ | IMPLEMENTED | `extrapolation/nonlinear/harmonic_register.py` |
| F4 | 10.1 | $C = \sum f_k W_k / \sum W_k$ | IMPLEMENTED | `descriptors/centroid.py` |
| F5 | 10.2 | $\hat{\beta}$ OLS on $10\log_{10}(P)$ vs $\log_{10}(f)$ | IMPLEMENTED | `descriptors/slope.py` |
| F6 | 10.3 | $\mathrm{HNR}_{\mathrm{mask}} = 10\log_{10}(E_h/E_n)$ | IMPLEMENTED | `descriptors/hnr.py` |
| F7 | 10.4 | Flux $L_1$ half-wave rectified | IMPLEMENTED | `descriptors/flux.py` |
| F8 | 10.5 | $\mathrm{LTAS}(k) = \frac{1}{T}\sum_t P_t(k)$ | IMPLEMENTED | `descriptors/ltas.py` |
| F9 | 10.6 | $V_t(C) = \frac{1}{T-1} \sum (C_t - \bar{C})^2$ | IMPLEMENTED | `descriptors/variance.py` |
| F10 | 10.7 | $\mathrm{dB}_{\mathrm{amp}} = 20\log_{10}(A_2/A_1)$ | IMPLEMENTED | `descriptors/attenuation.py` |
| F11 | 10.7 | $\mathrm{dB}_{\mathrm{pow}} = 10\log_{10}(P_2/P_1)$ | IMPLEMENTED | `descriptors/attenuation.py` |
| F12 | 10.7 | $A_2/A_1 = 10^{\mathrm{dB}/20}$ | IMPLEMENTED | `descriptors/attenuation.py` |
| F13 | 10.7 | $P_2/P_1 = 10^{\mathrm{dB}/10}$ | IMPLEMENTED | `descriptors/attenuation.py` |
| F14 | 11.1 | $\Phi(D) = D$ | IMPLEMENTED_FALLBACK | `density/metric.py::DensityMetric.phi` |
| F15 | 11.2 | $D \stackrel{?}{=} F(D_1, \dots, D_k)$ | REFERENCE_MODEL / PLANNED | not implemented; `_EWSD_TRANSFER_FUNCTIONS = {}` |
| F16 | 12.1 | $\log B_{i,d}(p) = \beta_0 + s_{i,d}(p)$, $B = \exp(\cdot)$ | IMPLEMENTED | `extrapolation/nonlinear/baseline.py::fit_ordinary_baseline` |
| F17 | 13.2 | $\hat{\boldsymbol{\beta}} = \arg\min \lVert \mathbf{y} - \mathbf{B}\boldsymbol{\beta} \rVert^2 + \lambda \boldsymbol{\beta}^\top \mathbf{P} \boldsymbol{\beta}$ | IMPLEMENTED | `extrapolation/nonlinear/splines.py::fit_penalized_bspline` |
| F18 | 13.2 | $\mathbf{P} = \mathbf{D}_2^\top \mathbf{D}_2$ | IMPLEMENTED | `extrapolation/nonlinear/splines.py::second_difference_penalty_matrix` |
| F19 | 15.1 | $Y = B \cdot \exp(\alpha_t)$ | IMPLEMENTED_FALLBACK | `bow_contact_model.py` constant branch |
| F20 | 16.1 | $Y = B \cdot \exp(\alpha_t + g_t(p))$ | IMPLEMENTED | `bow_contact_model.py::BowContactFit.predict` |
| F21 | 18.1 | $\alpha_{\mathrm{sul\_tasto}} = -0.12$ | ASSUMPTION | `configs/extrapolation_priors.yaml::alpha_t_sul_tasto` |
| F22 | 18.1 | $\alpha_{\mathrm{sul\_pont}} = +0.20$ | ASSUMPTION | `configs/extrapolation_priors.yaml::alpha_t_sul_ponticello` |
| F23 | 19.1 | $\alpha_{\mathrm{mute}} = \log(10^{-\Delta_{\mathrm{dB}}/10})$ | ASSUMPTION + IMPLEMENTED_FALLBACK | `mute_model.py::_db_to_log_ratio` |
| F24 | 19.1 | $\alpha_{\mathrm{mute, vln}} \approx -0.691$ | ASSUMPTION | `configs/extrapolation_priors.yaml::alpha_mute_vln` |
| F25 | 19.1 | $\alpha_{\mathrm{mute, vla}} \approx -0.461$ | ASSUMPTION | `configs/extrapolation_priors.yaml::alpha_mute_vla` |
| F26 | 20.1 | $f_n = n \cdot f_{\mathrm{open}}$ | IMPLEMENTED | `extrapolation/nonlinear/harmonic_register.py` |
| F27 | 20.1 | $m_n = 69 + 12 \log_2(f_n/440)$ | IMPLEMENTED | `extrapolation/nonlinear/harmonic_register.py` |
| F28 | 20.2 | Artificial order-4 offset $\approx +24$ semitones | IMPLEMENTED | `extrapolation/nonlinear/harmonic_register.py` |
| F29 | 22.1 | $L = B \exp(\mu - z\sigma)$, $U = B \exp(\mu + z\sigma)$, $z \approx 1.95996$ | IMPLEMENTED | `posterior.py::summarize_log_ratio_multiplicative` |
| F30 | 22.4 | Additive interval $\mu \pm z\sigma$ | IMPLEMENTED_FALLBACK | `posterior.py::summarize_frequentist` |
| F31 | 23.2 | Bayesian log-ratio spline: $\alpha, \boldsymbol{\beta}, \sigma$ priors + RW2 potential + Gaussian likelihood | OPTIONAL_BACKEND | `bayesian_backend.py::fit_bayesian_log_ratio_spline` |
| F32 | 12.3 | $\hat{\sigma}_{\mathrm{res}} = \sqrt{\frac{1}{\nu}\sum (y - \hat{y})^2}$ | IMPLEMENTED | `extrapolation/nonlinear/baseline.py` |

Formula count: **32** distinct entries.

---

## Appendix B: Code-to-documentation traceability matrix

| Guide section | Module | Symbol / function | Configuration | Tests |
|---|---|---|---|---|
| 8 Pitch registry | `manual_entry/pitch.py` | `midi_to_hz`, `hz_to_midi` | — | `tests/manual_entry/test_pitch.py` |
| 10 Descriptor backend | `descriptors/*.py` | `compute_spectral_centroid`, `compute_spectral_slope`, `compute_hnr`, `compute_flux`, `compute_ltas`, `compute_frame_spectral_variance`, `compute_partials` | `configs/acoustic_descriptors.yaml`, `configs/analysis_profiles/default_descriptor_v1.yaml` | `tests/descriptors/*` |
| 10.7 Attenuation | `descriptors/attenuation.py` | `amplitude_ratio_to_db`, `power_ratio_to_db`, `db_to_amplitude_ratio`, `db_to_power_ratio` | — | `tests/descriptors/test_attenuation.py` |
| 11 Density metric | `density/metric.py` | `DensityMetric.phi` | `configs/density_metric.yaml` | `tests/density/test_metric.py` |
| 12 Baseline | `extrapolation/nonlinear/baseline.py` | `fit_ordinary_baseline`, `BaselineFit.predict` | `configs/extrapolation_models.yaml` | `tests/extrapolation/test_baseline.py` |
| 13 Splines | `extrapolation/nonlinear/splines.py` | `fit_penalized_bspline`, `second_difference_penalty_matrix`, `predict_bspline`, `make_knots` | — | `tests/extrapolation/test_splines.py` |
| 14 Model selection | `extrapolation/nonlinear/model_selection.py` | `assess_data_availability`, `select_model`, `select_register_model` | `configs/extrapolation_model_selection.yaml` | `tests/extrapolation/test_model_selection*.py` |
| 15--16, 18 Bow contact | `extrapolation/nonlinear/bow_contact_model.py` | `fit_bow_contact_effect`, `BowContactFit.predict` | `configs/extrapolation_priors.yaml` | `tests/extrapolation/test_bow_contact*.py`, `tests/extrapolation/test_posterior.py` |
| 19 Mute | `extrapolation/nonlinear/mute_model.py` | `fit_mute_effect`, `MuteFit.predict`, `_db_to_log_ratio` | `configs/extrapolation_priors.yaml` | `tests/extrapolation/test_mute_model.py` |
| 20 Harmonic register | `extrapolation/nonlinear/harmonic_register.py` | `generate_natural_harmonic_targets`, `generate_artificial_harmonic_targets`, `annotate_baseline_extrapolation` | `configs/extrapolation_harmonic_ranges.yaml` | `tests/extrapolation/test_harmonic_*` |
| 21 Harmonic gate | `extrapolation/nonlinear/model_selection.py` (harmonic branch), `prediction.py` | `harmonic_modal_metadata_gate`, `harmonic_modal_acoustic_model_unavailable` | `configs/extrapolation_model_selection.yaml` | `tests/extrapolation/test_model_selection_integration.py` |
| 22 Intervals | `extrapolation/nonlinear/posterior.py` | `summarize_log_ratio_multiplicative`, `summarize_frequentist`, `apply_posterior_to_result` | — | `tests/extrapolation/test_posterior.py` |
| 23 Bayesian backend | `extrapolation/nonlinear/bayesian_backend.py` | `check_backend`, `fit_bayesian_log_ratio_spline` | — (extra `[bayes]`) | `tests/extrapolation/test_bayesian_backend.py` |
| 24 Evidence | `extrapolation/nonlinear/domain.py` (`EvidenceTier`), `model_selection.py` | tier assignment | — | `tests/extrapolation/test_model_selection*.py` |
| 25 Provenance | `extrapolation/nonlinear/prediction.py::_provenance_from_rows`, `domain.py::ExtrapolationResult` | provenance fields | — | `tests/extrapolation/test_export_nonlinear.py` |
| 26 GUI | `gui_metadata/extrapolator_app.py`, `register_grid.py`, `register_builder.py` | `NarrowExtrapolatorApp` | `configs/extrapolation/provisional_density_effects_v1.yaml`, harmonic ranges | manual test |
| 27 CLI | `cli/__init__.py`, `cli/nonlinear.py`, `cli/extrapolation.py`, `cli/prediction.py` | `main`, `run_nonlinear_command`, `run_extrapolation_command` | — | `tests/cli/*` |
| 29 Excel | `extrapolation/nonlinear/export_nonlinear.py` | `export_nonlinear_workbook` | — | `tests/extrapolation/test_export_nonlinear.py` |
| 30 Testing | `tests/*` | pytest markers | `pyproject.toml [tool.pytest.ini_options]` | — |

---

## Appendix C: Cross-links to other documents

- Metadata entry GUI: [`docs/METADATA_ENTRY_GUI.md`](METADATA_ENTRY_GUI.md).
- Nonlinear extrapolation user guide: [`docs/NONLINEAR_EXTRAPOLATION.md`](NONLINEAR_EXTRAPOLATION.md).
- Narrow extrapolation GUI notes: [`docs/NARROW_EXTRAPOLATION_GUI.md`](NARROW_EXTRAPOLATION_GUI.md).
- Narrow extrapolation reference: [`docs/NARROW_EXTRAPOLATION.md`](NARROW_EXTRAPOLATION.md).
- Note-level requests: [`docs/NOTE_LEVEL_REQUESTS.md`](NOTE_LEVEL_REQUESTS.md).
- Acoustics stress testing: [`docs/ACOUSTICS_STRESS_TESTING.md`](ACOUSTICS_STRESS_TESTING.md).

Mermaid sources: [`docs/technical_guide_assets/`](technical_guide_assets/).

---

## Appendix D: Production instructions, Phase-4 prediction, and literature sources

This appendix documents companion packages that remain part of the repository but are
**not** the primary nonlinear Excel pipeline documented in §§12–29.

### D.1 Relative bow–bridge position $\beta$

**Equation.**

$$
\beta = \frac{d_{\mathrm{bow-bridge}}}{L_{\mathrm{speaking}}}
$$

**Symbols.**

| Symbol | Meaning | Unit |
|---|---|---|
| $d_{\mathrm{bow\text{-}bridge}}$ | Distance from bow contact to bridge | m |
| $L_{\mathrm{speaking}}$ | Speaking length of the string | m |
| $\beta$ | Relative contact position | dimensionless |

**Implementation.** `production/bow_contact.py::compute_beta`.

**Assumptions.** The technique label alone does **not** determine $\beta$, bow force, or bow velocity. Missing physical covariates must remain missing.

**Status:** **IMPLEMENTED** as a production helper; **Not currently implemented** as an automatic covariate inference path into the nonlinear EWSD model (the M4 physical-informed rung remains gated on explicit covariates).

### D.2 Compositional production and migration

- `production/migration.py::migrate_legacy_technique_record` converts a flat `technique` string into a `ProductionInstruction`.
- `production/harmonics.py::validate_harmonic_interval_order` validates allowed touch-interval $\leftrightarrow$ order pairs.
- `production/mute.py::normalize_mute_mass` normalises mute-mass metadata without inventing a mass from the bare label `con sordino`.

**Status:** **IMPLEMENTED**.

### D.3 Phase-4 evidence-gated prediction helpers

These APIs live under `prediction/` and operate on density scalars with explicit
operation and link functions. They do **not** replace the nonlinear register
extrapolator.

| Symbol | Module | Role |
|---|---|---|
| `apply_operation` | `prediction/operations.py` | Multiplicative / additive / log-additive density operations; refuses silent dB-as-density shortcuts |
| `link_forward` | `prediction/links.py` | Identity / log / logit / probit links |
| `resolve_activate_user_assumptions` | `prediction/modes.py` | Separates `evidence_only` mode from assumption-authorised numeric mode |
| `predict_from_ordinary` | `prediction/from_ordinary.py` | Ordinary $\rightarrow$ technique prediction under activated parameters |
| `resolve_applicability` | `applicability/resolver.py` | Unified applicability resolution |
| `QualitativeConstraintEngine` | `constraints/engine.py` | Qualitative-only constraints (no EWSD inventing) |
| `resolve_user_assumptions` | `assumptions/activation.py` | User assumptions are not literature-validated evidence |
| `load_source_identity_registry` | `literature/source_identity.py` | Source-identity validation |
| `compute_descriptor` | `descriptors/engine.py` | Descriptor dispatch |
| `DensityMetric` | `density/metric.py` | Identity $\Phi(D)=D$ |

Configuration files referenced by this layer include `prediction.yaml`,
`model_links.yaml`, `user_assumptions.yaml`, `qualitative_acoustic_constraints.yaml`,
`literature_sources.yaml`, `literature_evidence_extracts.yaml`,
`source_identity_validation.yaml`, and `measurement_domains.yaml`.

Numerical technique-to-EWSD literature parameters remain **inactive**
(`n_active_density_parameters == 0`). Absence of a local extract must not be read
as absence of specialised literature.

**Status:** **IMPLEMENTED** as infrastructure; density-parameter activation remains inactive by design.

### D.4 Literature source identifiers (examples)

Curated identifiers in `configs/literature_sources.yaml` include, among others:

- `MEYER_ACOUSTICS`
- `SRC_SCHOONDERWALDT_2009`
- `SRC_EVANGELISTA_FREIRE_2025`

These identifiers are provenance handles. They do **not** by themselves activate
numeric EWSD transforms.

### D.5 Value-kind vocabulary (reminder)

Excel and result rows use `value_kind` values such as
`assumption_based_extrapolation`, `extrapolated`, `unavailable`, and
`qualitative_only`. Assumption-based numeric cells must remain labelled as
assumption-based; they are never re-labelled as matched empirical evidence.

---

*End of Technical Guide.*
