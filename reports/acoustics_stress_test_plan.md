# Acoustics stress test plan

Generated: 2026-07-23T17:54:15.169339+00:00

## Principles

1. Exact mathematical tests for implemented equations.
2. Literature-bounded tests only from identity-verified sources.
3. Qualitative/metamorphic tests for directional/non-equivalence claims.
4. Negative/scope tests for unsupported extrapolation.
5. Scope-safeguard passes for unimplemented descriptors are **not** numerical validation.

## Tiers

- Fast: `pytest -m "acoustics_stress and not slow and not benchmark"`
- Full: `pytest tests/acoustics_stress -q` or `pytest -m acoustics_stress`
- Benchmarks: `pytest -m benchmark`

## Worked benchmarks A–J

| ID | Name | Status |
|----|------|--------|
| A | beta_exact | `implemented` |
| B | artificial_harmonic_sounding_frequency | `physics_oracle_only_production_api_absent` |
| C | interval_order_contradiction | `implemented` |
| D | spectral_centroid_sine | `implemented` |
| E | spectral_centroid_two_tone | `implemented` |
| F | hnr_monotonicity | `implemented` |
| G | mute_categories_distinct | `implemented_scope` |
| H | measurement_domain_mismatch | `implemented_scope` |
| I | evidence_only_ewsd_na | `implemented` |
| J | user_assumption_mode | `implemented_with_empty_default_registry` |

## Implemented descriptors

`DESC_SPECTRAL_CENTROID`, `DESC_SPECTRAL_SLOPE`, `DESC_HNR`, `DESC_SPECTRAL_FLUX`, `DESC_FRAME_SPECTRAL_VARIANCE`, `DESC_LTAS`, `DESC_PARTIAL_SALIENCE`, `DESC_PITCH_COMPONENT_COUNT`, `DESC_ABSOLUTE_ATTENUATION`

## Unsupported descriptors (scope safeguard only)

`DESC_TEMPORAL_MODULATION`, `DESC_ATTACK_TIME`, `DESC_LOUDNESS`, `DESC_FUNDAMENTAL_SALIENCE`, `DESC_UPPER_PARTIAL_ENERGY_RATIO`, `DESC_BRIDGE_MOBILITY`, `DESC_INTER_PLAYER_VARIABILITY`

## Synthetic signals

Deterministic fixtures in `testing/signal_generators.py`.
Not perceptually equivalent to real bowed-string sounds.

## Real-audio validation

**Absent** — no verified local audio corpus accompanies articles/datasets;
no silent downloads; optional dataset adapters only.

## Report categories

- infrastructure tests
- mathematical exact tests
- implemented descriptor tests
- literature comparisons
- measurement-domain exclusions
- real-audio tests
- unsupported descriptors (scope safeguard)
