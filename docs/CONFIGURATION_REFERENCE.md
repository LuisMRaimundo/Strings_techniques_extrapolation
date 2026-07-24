# Configuration Reference

The behaviour of the string technique density model is governed by the YAML
files under `configs/`. This reference lists the key files, their principal
fields, and the runtime effect of each field.

Only fields with a documented purpose in the current code base are listed.
Fields with no impact on runtime behaviour are omitted.

## `configs/extrapolation_model_selection.yaml`

Deterministic thresholds and admissible-model ladder consumed by
`src/string_technique_model/extrapolation/nonlinear/model_selection.py`.

### `thresholds`

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `min_distinct_pitches_for_linear` | int | `3` | Minimum distinct pitches required to admit a linear register trend. |
| `min_distinct_pitches_for_spline` | int | `6` | Minimum distinct pitches required to admit a penalized spline. |
| `min_pitch_span_semitones_for_spline` | int | `12` | Minimum register span in semitones for the spline to be admissible. |
| `min_observations_for_linear` | int | `3` | Minimum observations for a linear trend. |
| `min_observations_for_spline` | int | `6` | Minimum observations for a spline fit. |
| `min_design_rank_ratio` | float | `0.85` | Heuristic identifiability threshold (rank / n_basis). |

### `complexity_ladder`

Ascending list of complexity classes:
`M0_constant_effect`, `M1_regularized_linear_trend`,
`M2_penalized_register_spline`, `M3_hierarchical_instrument_dynamic`,
`M4_physical_informed`, `M5_spectral_or_modal_specific`. The selection
engine never jumps directly to the top of the ladder; it picks the highest
class the data actually identify.

### `families`

Each entry declares:

- `techniques` — list of technique identifiers covered by the family.
- `mechanism` — informative physical mechanism.
- `preferred_quantity_domain` — list of acceptable target quantity classes.
- `required_covariates` and `optional_covariates` — audit lists surfaced
  in the `Model_Selection_Audit` sheet.
- `required_physical_covariates_for_M4` — additional gate on the physical
  ladder rung.
- `required_model_components_for_numeric` — model components (not
  covariates) that must be registered before numeric extrapolation.
- `ladder` — ordered list of model rungs (`model_id`, `complexity`,
  `requires`, optional `enabled`, `marks`, and role).

The five families currently declared are `ordinary_baseline_model`,
`bow_contact_model`, `mute_transfer_model`, `harmonic_modal_model`,
`multiphonic_component_model`, and `execution_target_model`. Flautando is
declared as `execution_target_model` and is intentionally **not** routed
to `sul_tasto`.

### `policy`

| Field | Effect |
|-------|--------|
| `never_select_most_complex_by_default` | Forbids automatic selection of the highest rung. |
| `require_predictive_gain_for_upgrade` | Reserved for the model comparison stage. |
| `authorize_numeric_assumption_when_zero_obs` | When `false`, mute/bow rungs fall back to qualitative / NA rather than to the constant assumption. |
| `refuse_physical_informed_without_covariates` | Requires physical covariates before admitting the `M4` rung. |
| `refuse_constant_factor_for_harmonics` | Prevents copying an ordinary constant onto harmonics. |
| `refuse_flautando_as_sul_tasto` | Prevents silent flautando routing. |

## `configs/extrapolation_harmonic_ranges.yaml`

Consumed by
`src/string_technique_model/extrapolation/nonlinear/harmonic_register.py`.

### `defaults`

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `selection_mode` | string | `configured_physically_plausible_harmonics` | Global default mode. |
| `maximum_sounding_pitch` | pitch | `C8` | Global sounding-pitch ceiling. |
| `maximum_sounding_midi` | int | `108` | MIDI equivalent of the ceiling. |
| `artificial_default_order` | int | `4` | Default artificial-harmonic order. |
| `artificial_touch_interval` | string | `P4` | Touch interval for the default order (`P4→4`, `M3→5`, `m3→6`, `P5→3`). |
| `artificial_configuration_policy` | string | `canonical_single_string_assignment` | Only canonical single-string assignments are enumerated. |
| `retain_excluded_by_analysis` | bool | `false` | If `true`, keep analysis-excluded rows in the export. |
| `order_selection_reason` | string | `practical_analysis_scope` | Provenance label written on generated targets. |
| `limited_extrapolation_semitones` | int | `3` | Warning threshold for baseline out-of-range extrapolation. |
| `physical_or_assumption_semitones` | int | `12` | Larger tolerance used for physical/assumption-based interpolation. |

### `harmonic_register.<instrument>.{natural,artificial}`

Per-instrument geometry:

- `orders` — configured harmonic orders enumerated by the generator.
- `configured_order_min` / `configured_order_max` — informational bounds.
- `touch_interval` — artificial touch interval used to derive the order.
- `maximum_sounding_pitch` — instrument-specific sounding ceiling.
- `configuration_policy` — string enumeration policy identifier.

### `instrument_harmonic_analysis_range`

Per-instrument analysis window (per `natural_harmonic` and
`artificial_harmonic`). Targets outside this window are labelled
`excluded_by_analysis_range` or `excluded_by_analysis_scope`, never
`impossible`.

## `configs/extrapolation_priors.yaml`

Priors and regularization anchors consumed by the nonlinear pipeline
(`src/string_technique_model/extrapolation/nonlinear/priors.py`).

Every entry has:

- `prior_id` — stable identifier.
- `parameter` — one of `alpha_t`, `alpha_mute`, `sigma`, `sigma_smooth`,
  `sigma_baseline`.
- `family` — `normal`, `half_normal`, etc.
- `mean`, `sd`, `lower`, `upper` — distribution parameters.
- `activation_status` — `active`, `inactive`, or `fallback_only`.
- `source` — either `regularization_assumption`, `user_assumption`,
  `weakly_informative`, or `rw2_spline_prior`.
- `notes` — explanatory text propagated to the exported `Priors_Used`
  sheet.

Notable priors:

| Prior ID | Parameter | Purpose |
|----------|-----------|---------|
| `alpha_t_sul_tasto` | `alpha_t` | Weak decrease tendency (regularization). |
| `alpha_t_sul_ponticello` | `alpha_t` | Weak increase tendency (regularization). |
| `alpha_mute_vln` | `alpha_mute` | User-assumption mapping of a ~6 dB power reduction; requires EWSD ∝ power. |
| `alpha_mute_vla` | `alpha_mute` | User-assumption mapping of a ~4 dB power reduction. |
| `alpha_mute_generic` | `alpha_mute` | Fallback prior for cello/contrabass. |
| `sigma_technique_residual` | `sigma` | Residual scale for bow-contact log-ratio. |
| `sigma_mute_residual` | `sigma` | Residual scale for mute log-ratio. |
| `sigma_spline_smooth` | `sigma_smooth` | Smoothness scale for the spline coefficients. |
| `sigma_baseline_residual` | `sigma_baseline` | Ordinary baseline residual scale. |

`alpha_t_sul_tasto` and `alpha_t_sul_ponticello` are intentionally
asymmetric; the two techniques are **not** modelled as inverses.

## `configs/extrapolation_models.yaml`

Registry of extrapolation model shells:

- `models[].model_id` — `M0_constant_legacy`, `M1_hierarchical_spline`,
  `M1_bayesian`, `M2_harmonic_stub`.
- `models[].method` — one of the four method names shared with the CLI.
- `models[].submodel_ids` — component submodels.
- `models[].enabled` — global on/off switch.

The `baseline` block sets `spline_degree`, `n_basis`, `penalty_lambda`,
`log_transform`, and `quantity` for the ordinary baseline fit.

The `technique_submodels` block declares one entry per technique with
`submodel_id`, `model_family`, `min_observations`, and `prior_ids`.

## `configs/density_metric.yaml`

Canonical metric definition (see also
[TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)):

- `name` — `EWSD_score_acoustic_balanced`.
- `formula` — the identity Φ(D) = D.
- `mathematical_domain` — real, non-negative.
- `units` — dimensionless Stage-3 acoustic-balanced score.
- `input_representation` — precomputed scalar; band/partial energy vectors
  accepted only if a spectrum-aware backend is registered.
- `upstream_identifiers` — upstream pipeline identifiers used only for
  provenance.
- `placeholder` — must remain `false`.

## `configs/acoustic_descriptors.yaml`

Descriptor registry (schema and implementation status). Every entry has:

- `descriptor_id`, `name`, `definition`, `formula_status`.
- `units` — canonical units (for example `Hz`, `dB`, `dB_per_decade_log10Hz`).
- `amplitude_power_convention`, `temporal_aggregation`, `valid_domain`.
- `interpretation_limits` — free-form note (always warns that descriptors
  are not EWSD).
- `ewsd_compatibility` — always `incompatible_without_activated_mapping`
  unless an activation is registered.
- `value_kind` — `scalar`, `vector`, or `scalar_or_vector`.
- `implemented` — boolean.
- `method_id` — required for implemented descriptors.
- `analysis_profile_id` — links to `configs/analysis_profiles/`.

The default analysis profile is `PROFILE_DEFAULT_DESCRIPTOR_V1`, defined
in `configs/analysis_profiles/default_descriptor_v1.yaml`.

Descriptors with implementation status `unresolved_in_this_repository`
(`DESC_TEMPORAL_MODULATION`, `DESC_ATTACK_TIME`, `DESC_LOUDNESS`,
`DESC_FUNDAMENTAL_SALIENCE`, `DESC_UPPER_PARTIAL_ENERGY_RATIO`,
`DESC_BRIDGE_MOBILITY`, `DESC_INTER_PLAYER_VARIABILITY`) return `unavailable`.

## `configs/analysis_profiles/`

| File | Purpose |
|------|---------|
| `default_descriptor_v1.yaml` | Default STFT/FFT parameters, window function, hop size, and dB conventions for descriptors. Selected by descriptor entries via `analysis_profile_id: PROFILE_DEFAULT_DESCRIPTOR_V1`. |
| `evangelista_freire_2025_ltas.yaml` | Analysis profile matching the reference LTAS methodology used in literature benchmarks. |

## `configs/instruments.yaml`

Per-instrument physical metadata:

- `open_string_tuning` (or `open_string_tuning_sounding` for `cb`).
- `written_range_midi`, `sounding_range_midi`, `written_equals_sounding`.
- `ordinary_table_span` — canonical register for ordinary tables.
- `approximate_string_length_m`, `bridge_resonances_hz`,
  `air_resonance_hz`, `high_frequency_rolloff` — currently
  `status: unsupported_pending_local_literature_extraction`.
- `technique_valid_ranges` — per-technique sounding span or
  `not_estimable_without_instrument_specific_evidence`.
- `transfer_policy` — for `vla`, `vlc`, and `cb`, records the rule that
  violin parameters must not be silently reused.

## Other referenced configuration files

The following files are used by adjacent subsystems and are documented
individually in the [technical guide](TECHNICAL_GUIDE.md):

- `configs/technique_ontology.yaml` — technique vocabulary and
  interval–order map.
- `configs/qualitative_acoustic_constraints.yaml` — qualitative
  constraint definitions.
- `configs/literature_*.yaml` — literature sources, extracts, transfers.
- `configs/measurement_domains.yaml` — measurement domain registry.
- `configs/user_assumptions.yaml` — user numerical assumption registry.
- `configs/source_identity_validation.yaml` — source identity validation
  rules.
- `configs/prediction.yaml` — prediction pipeline parameters.
- `configs/model_links.yaml` — link definitions for the operation pipeline.
- `configs/stress_tolerances.yaml`, `configs/acoustics_stress_tests.yaml`,
  `configs/literature_benchmark_cases.yaml` — stress-testing configuration
  (see [ACOUSTICS_STRESS_TESTING.md](ACOUSTICS_STRESS_TESTING.md)).

## Editing conventions

- Preserve `schema_version` fields; several loaders check them.
- Keep boolean flags explicit (`true` / `false`) rather than YAML shortcuts.
- Backup files with the `.bak` extension are ignored by the loaders and are
  created automatically by the `assumptions activate` / `deactivate`
  commands.
