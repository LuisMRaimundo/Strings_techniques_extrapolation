# Scientific Limitations

This document enumerates the limitations of the current implementation.
It is intentionally candid and is intended to be cited from doctoral or
peer-reviewed texts to demarcate the scope of the model.

## 1. Sparse targets

The nonlinear pipeline is designed for **sparse observational settings**
in which measured technique observations are absent or few. When the
target technique has zero observations, the pipeline degrades gracefully:

- The register curve `g_t(p)` is deactivated
  (`register_shape_identified=false`, `shape_source=constant_effect`,
  `g_t_active=false`).
- The result is labelled `constant_technique_effect_over_smoothed_baseline`
  rather than any higher rung of the ladder.
- The technique offset `α_t` is marked `regularization_assumption` or
  `user_assumption` via `alpha_origin`.

Interval widths in this regime are `assumption_distribution_interval`,
not classical confidence or credible intervals.

## 2. EWSD is identity-only

The metric module implements

$$
\Phi(D) = D
$$

where `D` is a precomputed EWSD acoustic-balanced scalar. **No spectrum
→ EWSD transform is registered in this repository**, so the software
does not recompute EWSD from spectra. Numerical technique-to-EWSD
mappings are **inactive**
(`n_active_density_parameters == 0`).

## 3. Mute dB → EWSD is an explicit assumption

The mute submodel expresses `α_mute` as `log(10^(dB/10))` for
instrument-specific dB values from the priors registry (`~6 dB` for
violin, `~4 dB` for viola; cello and contrabass use a loose fallback).
This mapping **requires** the assumption that EWSD is proportional to
power, which is not established in the local corpus. Consequently:

- Mute rows are labelled `alpha_origin=user_assumption`.
- The pipeline never treats mute mass, mute category, or mute material as
  a numerical multiplier without an activated assumption.
- Spectral transfer `A_m(f)` is the correct scientific target and is
  currently **not implemented**; the code falls back to a scalar
  descriptor approximation (`scalar_descriptor_approximation`).

## 4. `A_m(f)` is not implemented

The mute transfer model does not compute a frequency-dependent transfer
function. When the required spectral inputs are absent, the pipeline
selects the `scalar_descriptor_approximation` rung and marks
`model_reduction=scalar_descriptor_approximation` on the output. The
spectral transfer rung (`spectral_transfer_model`) requires
`has_spectra_or_ltas=true`; it is admissible only when spectra are
supplied.

## 5. Harmonic modal frequencies ≠ acoustic descriptors

Harmonic modal frequencies (sounding pitches from
`n · f₀` and open-string × order enumeration) are **implemented** and
exported as full geometry columns (see
[DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md)). What remains
**not implemented** is a calibrated harmonic descriptor model that maps
these modal frequencies to a numerical EWSD or descriptor value.

Two harmonic gates therefore coexist:

- `harmonic_modal_metadata_gate` — modal geometry is incomplete;
  `na_reason=insufficient_harmonic_metadata`.
- `harmonic_modal_acoustic_model_unavailable` — modal geometry is
  complete, but no calibrated harmonic descriptor model exists;
  `na_reason=no_harmonic_acoustic_calibration_data`; the row is marked
  `modal_frequencies_generated_acoustic_values_unavailable`.

No spectral EWSD formula for harmonics is invented.

## 6. Violin-centric literature

The specialised literature layer is heavily violin-centric. Instrument
transfer is refused by default:

- `configs/instruments.yaml` records `transfer_policy: "Violin parameters
  must not be silently reused."` for `vla`, `vlc`, and `cb`.
- The `predict` CLI requires `--allow-transfer` to enable transfer, and
  transfer-based rows are labelled accordingly.

Cello and contrabass mute figures remain `unavailable` in the local
corpus, with a wide fallback prior `alpha_mute_generic` used only as a
last resort.

## 7. Priors are not literature-measured coefficients

The `α_t` priors for `sul_tasto` and `sul_ponticello` are **weak
regularization centers**, not literature-fitted coefficients. Their
magnitudes are deliberately different (the two techniques are **not**
inverses). This is documented in
`configs/extrapolation_priors.yaml`.

## 8. No fake Bayesian inference

If PyMC / ArviZ are not installed, the diagnostic backend reports
`bayesian_backend_unavailable` and the pipeline continues with the
penalized-fit approximation. **No pseudo-posterior samples are
substituted**. Bayesian-only columns are cleared on export when the
Bayesian backend did not actually run.

## 9. `EWSD F(D₁, …, D_k)` unresolved

There is no validated `F(D₁, …, D_k)` that composes descriptor scalars
into EWSD. The metric is modelled as an observed scalar via a direct
log-ratio (`observed_scalar_direct_model`) in the nonlinear pipeline.
Any composition into EWSD requires registering a transfer function; none
is provided in this repository.

## 10. No synthetic acoustic validation

Synthetic signals used in the stress-testing suite are numerical
fixtures. They are **not perceptually equivalent** to bowed-string
recordings, and passing the stress suite does not constitute acoustic
validation. See [ACOUSTICS_STRESS_TESTING.md](ACOUSTICS_STRESS_TESTING.md).

## 11. No real-audio validation in the public repository

The local repository does **not** ship a real-audio validation corpus.
The `predict validation-status` command reports whether an external
validation has been claimed.

## 12. Flautando is not sul tasto

Flautando is explicitly declared as `execution_target_model` and is
never auto-routed to `sul_tasto`. Only qualitative / NA outputs are
emitted (`configs/extrapolation_model_selection.yaml`).

## 13. Multiphonics are qualitative only

The `multiphonic_component_model` ladder returns
`multiphonic_qualitative_only` (`value_kind=qualitative_only`). No
numerical multiphonic simulator is implemented.

## 14. Descriptor scope

Several descriptors are declared with
`formula_status: unresolved_in_this_repository`, including
`DESC_TEMPORAL_MODULATION`, `DESC_ATTACK_TIME`, `DESC_LOUDNESS`,
`DESC_FUNDAMENTAL_SALIENCE`, `DESC_UPPER_PARTIAL_ENERGY_RATIO`,
`DESC_BRIDGE_MOBILITY`, and `DESC_INTER_PLAYER_VARIABILITY`. These
return `unavailable` regardless of input.

## 15. Windows console limitations

The `request` subcommand help contains a Unicode right-arrow (`→`).
On consoles that use the legacy `cp1252` code page this character is
transcoded to `?` or an escape sequence. This is cosmetic; the command
itself functions correctly. Set `chcp 65001` and
`PYTHONIOENCODING=utf-8` to restore the glyph.

## Related documents

- [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) — complete technical reference.
- [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) — model
  selection and equations.
- [CONFIGURATION_REFERENCE.md](CONFIGURATION_REFERENCE.md) — thresholds
  and policy switches.
- [DATA_SCHEMA_REFERENCE.md](DATA_SCHEMA_REFERENCE.md) — status
  enumerations.
- [USER_GUIDE.md](USER_GUIDE.md) — doctoral checklist before citing an
  exported value.
