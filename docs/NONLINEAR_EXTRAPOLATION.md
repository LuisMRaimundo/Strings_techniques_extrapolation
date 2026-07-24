# Nonlinear Hierarchical Extrapolation (Specialist Companion)

This document is the specialist companion to
[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md). It describes the nonlinear
hierarchical extrapolator, the model selection engine, the harmonic
target generator, the honest estimate columns, and the priors as they
are actually implemented in the repository.

For long-form formulas and complete provenance policies, defer to the
technical guide.

## Where it lives

- Package: `src/string_technique_model/extrapolation/nonlinear/`
- CLI: `python -m string_technique_model nonlinear …` and
  `python -m string_technique_model extrapolate …`
- Configuration:
  `configs/extrapolation_model_selection.yaml`,
  `configs/extrapolation_models.yaml`,
  `configs/extrapolation_priors.yaml`,
  `configs/extrapolation_harmonic_ranges.yaml`.

## Model selection engine

Model selection is executed by
`src/string_technique_model/extrapolation/nonlinear/model_selection.py`
in two stages:

1. Build the **scientifically admissible** candidate set from the family
   ladder and the required covariates.
2. Choose the **data ceiling** on the ladder — never automatically pick
   the most complex rung.

The ladder is `M0 → M1 → M2 → M3 → M4 → M5`
(`M0_constant_effect`, `M1_regularized_linear_trend`,
`M2_penalized_register_spline`, `M3_hierarchical_instrument_dynamic`,
`M4_physical_informed`, `M5_spectral_or_modal_specific`).

Families currently implemented:

| Family | Techniques |
|--------|------------|
| `ordinary_baseline_model` | ordinary, ordinario, arco, arco_normal |
| `bow_contact_model` | sul_tasto, sul_ponticello |
| `mute_transfer_model` | con_sordino |
| `harmonic_modal_model` | natural_harmonic, artificial_harmonic |
| `multiphonic_component_model` | multiphonics, multiphonic |
| `execution_target_model` | flautando |

Every result exports `selected_model_id`, `selection_reason`,
`candidate_model_ids`, `rejected_model_ids`, `fallback_level`,
`missing_covariates`, `missing_model_components`,
`modal_metadata_status`, and `acoustic_calibration_status`. See
[EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md).

## Register enrichment (harmonics)

Harmonic techniques do **not** copy ordinary chromatic pitches. Instead,
`src/string_technique_model/extrapolation/nonlinear/harmonic_register.py`
enumerates:

- Natural harmonics as `open_string × configured_order` combinations,
  producing sounding frequencies `n · f₀` and their nearest tempered
  labels.
- Artificial harmonics from the configured touch interval (`P4 → order 4`,
  `M3 → 5`, `m3 → 6`, `P5 → 3`), subject to the
  `canonical_single_string_assignment` policy.

The sounding-pitch ceiling is `C8` by default, per
`configs/extrapolation_harmonic_ranges.yaml`. The generator distinguishes
targets that are outside the analysis window
(`target_status=excluded_by_analysis_range`) from targets that are
physically unavailable; the analysis-excluded rows are never labelled
“impossible”.

Selection then operates on the **enriched** register. For harmonic rows,
if the modal metadata is complete but no calibrated acoustic model is
registered, the selection engine chooses
`harmonic_modal_acoustic_model_unavailable` and the exporter records
`na_reason=no_harmonic_acoustic_calibration_data`. If the modal metadata
is incomplete, the gate `harmonic_modal_metadata_gate` is chosen and
`na_reason=insufficient_harmonic_metadata`.

## Formulas at a glance

The formulas below are summarised for orientation. Full derivations,
notation, and provenance live in
[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).

### Ordinary baseline

$$
\log B_{i,d}(p) = \beta_0 + s_{i,d}(p)
$$

where `s` is a penalized B-spline on MIDI. Dynamics are treated as
categorical ordinal (`pp < mf < ff`), not equally-spaced numbers.

### Technique log-ratio (bow contact / mute scalar)

$$
\log R_{t,i,d}(p) = \alpha_t + u_{t,i} + v_{t,d} + g_{t,i}(p)
$$

$$
Y_{t,i,d}(p) = B_{i,d}(p) \cdot \exp\!\bigl(\log R_{t,i,d}(p)\bigr)
$$

Honesty rule: when `target_technique_observations = 0` (or fewer than
required for identifiability), `g_t(p) = 0` and the result is labelled
`constant_technique_effect_over_smoothed_baseline` — not
`M1_hierarchical_spline`. The fields
`register_shape_identified=false`, `shape_source=constant_effect`, and
`g_t_active=false` are exported.

### Intervals

Intervals are computed on the log-`R` scale:

$$
L = B \cdot \exp(\mu - z\,\sigma), \qquad U = B \cdot \exp(\mu + z\,\sigma).
$$

`interval_type` is `assumption_distribution_interval` whenever the fit
is dominated by the prior. Genuine Bayesian credible intervals are
emitted only when `bayesian_backend_used=True`.

### Mute

The spectral transfer `A_m(f)` is the scientific target and is currently
not implemented. When only scalar EWSD is available the pipeline selects
the `scalar_descriptor_approximation` rung and marks
`model_reduction=scalar_descriptor_approximation`.

### Harmonics

Modal frequencies and sounding pitches are generated (see above); the
acoustic descriptor mapping remains **numerically NA**. No spectral EWSD
formula for harmonics is invented.

## Honest estimate fields

Every result exposes two families of columns:

- **Neutral estimate columns** (`estimate_mean`, `estimate_median`,
  `estimate_sd`, `interval_low`, `interval_high`, `interval_type`,
  `interval_formula`). These are always populated when the pipeline
  produces a numerical value.
- **Bayesian-only columns** (`posterior_mean`, `posterior_median`,
  `posterior_sd`, `credible_interval_low`, `credible_interval_high`,
  `credible_interval_probability`, `log_ratio_mean`, `log_ratio_sd`,
  `probability_above_ordinary`). These are **cleared to `None` on
  export** whenever `bayesian_backend_used=False`.

Doctoral reports should quote the neutral columns unless the Bayesian
backend was explicitly enabled and produced a valid sample.

## Evidence tiers

`LEVEL_0_UNSUPPORTED` through `LEVEL_4_MATCHED_EMPIRICAL` gate the
language and the minimum admissible uncertainty. Unsupported cells
return `value_kind=unavailable` with a reason string.

## Bayesian backend

The Bayesian backend is optional and requires
`pip install -e ".[bayes]"` (PyMC, ArviZ, patsy). Without it,
`nonlinear diagnose` reports `capability_status=bayesian_backend_unavailable`
and the pipeline uses the penalized-fit approximation. No pseudo-Bayesian
inference is substituted.

## CLI

```bat
python -m string_technique_model nonlinear diagnose
python -m string_technique_model nonlinear fit-baseline --instrument vln --dynamic pp
python -m string_technique_model nonlinear fit-technique --technique sul_ponticello --instrument vln --dynamic pp
python -m string_technique_model nonlinear predict --technique sul_ponticello --instrument vln --dynamic pp --method hierarchical_spline
python -m string_technique_model nonlinear compare --technique sul_ponticello --instrument vln --dynamic pp
```

The `extrapolate {fit-baseline, fit-technique, predict, compare,
diagnose, export}` commands are aliases; `extrapolate grid` remains the
legacy narrow priority-1 grid extrapolator (see
[NARROW_EXTRAPOLATION.md](NARROW_EXTRAPOLATION.md)).

## Priors

The priors registry (`configs/extrapolation_priors.yaml`) provides:

- `alpha_t_sul_tasto` and `alpha_t_sul_ponticello` — asymmetric,
  regularization-only centres.
- `alpha_mute_vln` and `alpha_mute_vla` — user-assumption priors mapping
  ~6 dB and ~4 dB power reductions via `log(10^(-dB/10))`.
- `alpha_mute_generic` — loose fallback for cello and contrabass.
- Half-normal scales for residuals and spline smoothness.

Priors are consumed by the exporter and written to the `Priors_Used`
sheet with their `activation_status`.

## Limits

- No acoustic validation from test passages alone.
- No silent instrument transfer (`vln ↛ cb`).
- No spectral `A_m(f)`; no numeric harmonic EWSD; no numeric
  multiphonics.
- No pseudo-Bayesian sampling when the backend is unavailable.
- Flautando is not `sul_tasto`.

## Related documents

- [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) — full formulas and provenance
  policies.
- [EXCEL_OUTPUT_REFERENCE.md](EXCEL_OUTPUT_REFERENCE.md) — output columns
  and sheets.
- [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) — row and result
  schema.
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — thresholds
  and priors.
- [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md) — honest scope
  statement.
- [GLOSSARY.md](GLOSSARY.md) — symbols and acronyms.
