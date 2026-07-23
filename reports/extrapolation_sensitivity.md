# Extrapolation sensitivity

Sensitivity axes configured for audit:

- prior width (`alpha_t_*`, mute dB proxies)
- spline knots / penalty λ
- presence/absence of technique observations
- outside MIDI domain
- EWSD mapping status (`observed_scalar_direct_model`)

Statuses: `stable` | `prior_sensitive` | `data_limited` | `outside_baseline_range` | `structurally_unidentified` (NA path).

With zero local technique data, results are typically `prior_sensitive` / prior-dominated — expected.
