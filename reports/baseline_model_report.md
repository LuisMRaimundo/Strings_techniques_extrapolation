# Baseline model report

Model: \(\log B_{i,d}(p)=\beta_0+s_{i,d}(p)\) with penalized cubic B-splines on MIDI.

- Dynamics categorical ordinal (not linear spacing).
- Outside observed MIDI: `outside_baseline_range`, increased uncertainty.
- No cross-instrument baseline invention.
- Fit entry point: `fit_ordinary_baseline` / CLI `extrapolate fit-baseline`.
