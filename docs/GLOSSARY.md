# Glossary

This glossary defines symbols, acronyms, and terminology used across the
documentation and the source code. It also highlights commonly confused
term pairs.

## Symbols

| Symbol | Meaning |
|--------|---------|
| $D$ | Precomputed EWSD acoustic-balanced scalar. |
| $\Phi(D)$ | Canonical metric map; the current implementation uses $\Phi(D) = D$. |
| $B_{i,d}(p)$ | Ordinary baseline value for instrument $i$, dynamic $d$, at MIDI pitch $p$. |
| $s_{i,d}(p)$ | Penalised B-spline register curve on MIDI. |
| $\beta_0$ | Baseline intercept on the log scale. |
| $\alpha_t$ | Technique log-ratio offset (regularization or user assumption). |
| $u_{t,i}$, $v_{t,d}$ | Random effects for instrument $i$ and dynamic $d$ within technique $t$. |
| $g_{t}(p)$ | Register-dependent technique curve; deactivated when no target observations exist. |
| $\log R_{t,i,d}(p)$ | Technique log-ratio at pitch $p$. |
| $Y_{t,i,d}(p)$ | Technique prediction $B \cdot \exp(\log R)$. |
| $A_m(f)$ | Frequency-dependent mute transfer function (currently not implemented). |
| $n$ | Harmonic order. |
| $f_0$ | Fundamental frequency of an open string. |
| $n \cdot f_0$ | Sounding frequency of a natural harmonic. |
| $\beta$ | Bow contact position ratio $\text{bridge distance} / \text{speaking length}$. |

## Acronyms

| Acronym | Expansion |
|---------|-----------|
| EWSD | Equal-Weighted Spectral Density (acoustic-balanced scalar) — see `configs/density_metric.yaml`. |
| CDM | Combined Density Metric (legacy Stage-1 column name; explicitly **not** EWSD). |
| SSA | Sustained Signal Analyser (upstream pipeline). |
| SPL | Sound Pressure Level. |
| LTAS | Long-Term Average Spectrum. |
| HNR | Harmonic-to-Noise Ratio (spectral-mask variant only in this repository). |
| STFT | Short-Time Fourier Transform. |
| FFT | Fast Fourier Transform. |
| MIDI | Standard note numbering. |
| GUI | Graphical User Interface. |
| CLI | Command-Line Interface. |
| YAML | Data serialisation format used for configuration files. |
| CRI | Credible Interval (Bayesian). |
| RW2 | Second-order random walk prior on spline coefficients. |
| B-spline | Basis-spline used for the register curve. |
| M0, M1, …, M5 | Rungs of the model complexity ladder. |
| SRC_* | Prefix of literature source identifiers. |
| ASSUMP_* | Prefix of user assumption identifiers. |

## Instrument codes

| Code | Instrument |
|------|------------|
| `vln` | Violin |
| `vla` | Viola |
| `vlc` | Violoncello (cello) |
| `cb` | Double bass (contrabass) |

## Dynamics

| Code | Meaning |
|------|---------|
| `pp` | Pianissimo |
| `mf` | Mezzo forte |
| `ff` | Fortissimo |

## Confused-term pairs

| Term A | Term B | Distinction |
|--------|--------|-------------|
| EWSD | CDM | EWSD is the current acoustic-balanced Stage-3 score; CDM is the legacy Stage-1 label and is **not** EWSD. |
| `estimate_mean` | `posterior_mean` | The neutral column is always populated; the Bayesian column is populated only when the Bayesian backend actually ran. |
| Credible interval | Assumption distribution interval | The former requires a Bayesian sample; the latter reports the width of the assumption/regularization distribution and is emitted otherwise. |
| Confidence interval | Credible interval | The pipeline never emits classical confidence intervals; it emits either credible or assumption-distribution intervals. |
| `missing_covariates` | `missing_model_components` | Covariates are input fields absent from the data; model components are back-end capabilities (for example a calibrated harmonic descriptor model) that must be registered. |
| `harmonic_metadata_complete=false` | Acoustic calibration unavailable | The former means the modal geometry is incomplete (gate: `harmonic_modal_metadata_gate`); the latter means the geometry is complete but no calibrated acoustic model exists (gate: `harmonic_modal_acoustic_model_unavailable`). |
| Sul tasto | Flautando | Flautando is not routed to sul tasto; it is declared as `execution_target_model`. |
| Sul tasto | Sul ponticello (as inverses) | The two techniques are **not** modelled as inverses; priors are intentionally asymmetric. |
| Ordinary baseline | Constant technique effect | The baseline is a penalized spline on MIDI; a constant technique effect is applied only when the register curve cannot be identified. |
| `hierarchical_spline` (GUI) | `automatic` (Excel `requested_method`) | The GUI label maps to `requested_method=automatic` in exports so that automatic selection is visible. |
| `spectral_slope` in `dB_per_decade_log10Hz` | `dB_per_harmonic` | The implemented descriptor uses `dB_per_decade_log10Hz` via `spectral_slope_logfreq_db_linreg_v1`. `dB_per_harmonic` is a different definition; do not conflate the two. |
| `assumption_ids` (`ASSUMP_*`) | `assumptions_trace` | Only stable identifiers go in `assumption_ids`; free-form prose goes in `assumptions_trace`. |
| Descriptor value | EWSD value | Descriptors are `incompatible_without_activated_mapping` with EWSD; do not relabel a descriptor as EWSD. |
| Analysis exclusion | Physical impossibility | The generator explicitly avoids calling analysis-excluded rows “impossible”; the field is `excluded_by_analysis_scope`. |
| dB | sones | dB is an acoustic level; sones is a psychoacoustic loudness unit. `DESC_LOUDNESS` remains `unresolved_in_this_repository`. |
| Bridge mobility | SPL | Bridge mobility is a mechanical descriptor; SPL is an acoustic level. `DESC_BRIDGE_MOBILITY` is unresolved. |

## Model IDs of interest

| Model ID | Purpose |
|----------|---------|
| `M0_constant_legacy` | Legacy provisional density effects. |
| `M1_hierarchical_spline` | Log baseline spline + technique log-ratio submodels. |
| `M1_bayesian` | PyMC log-ratio spline when the backend is available. |
| `M2_harmonic_stub` | Harmonic extrapolation stub (deferred). |
| `harmonic_modal_metadata_gate` | Gate: modal metadata incomplete. |
| `harmonic_modal_acoustic_model_unavailable` | Gate: metadata complete but no calibrated harmonic descriptor model. |
| `harmonic_modal_frequency_with_descriptor_priors` | Deferred numeric rung. |
| `constant_technique_effect_over_smoothed_baseline` | Constant effect over a smoothed ordinary baseline. |
| `scalar_descriptor_approximation_linear` / `_spline` | Mute scalar approximation rungs. |
| `spectral_transfer_model` | Full spectral transfer (requires spectra). |

## Selection reasons of interest

| Reason | Meaning |
|--------|---------|
| `insufficient_harmonic_metadata` | Emitted by the metadata gate. |
| `no_harmonic_acoustic_calibration_data` | Emitted by the acoustic calibration gate. |
| `no_target_technique_observations` | Emitted when a bow contact family falls back to the constant effect. |
| `excluded_by_analysis_scope` | Emitted by the harmonic register generator. |

## Related documents

- [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md)
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md)
- [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)
- [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md)
- [SCIENTIFIC_LIMITATIONS.md](SCIENTIFIC_LIMITATIONS.md)
