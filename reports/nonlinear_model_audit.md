# Nonlinear model audit (Phase 1)

## Implemented

- M0 constant factor retained as null/legacy only (`density_effects` / method=`constant`).
- M1 hierarchical log-ratio + penalized B-splines for bow contact and mute scalar.
- Ordinary baseline per instrument × dynamic on MIDI (log scale).
- Evidence tiers LEVEL_0–LEVEL_4; prior-dominated flag.
- Optional PyMC backend; honest `bayesian_backend_unavailable` without `[bayes]`.
- Harmonics: Phase 2 stub (numeric NA).
- Excel audit workbook export.

## Not claimed

- Acoustic validation of numeric EWSD predictions.
- Validated descriptor→EWSD transfer \(F\).
- Full spectral mute \(A_m(f)\).
- Physical β / force / velocity inference from labels.
- Multiphonics.

## Acceptance mapping

| Criterion | Status |
|-----------|--------|
| Constant model not primary | Yes (M0 only) |
| Register nonlinearity when data support | Yes (spline on log R) |
| Complexity shrinks with sparse data | Yes (no spline if n<3) |
| Wider intervals with less evidence | Yes (prior SD / residual) |
| Distinct technique families | Yes |
| Harmonics ≠ attenuated ordinary | Yes (NA stub) |
| Diagnostics exported | Yes |
| Unidentifiable → NA | Yes |
| Prior-dominated marked | Yes |
