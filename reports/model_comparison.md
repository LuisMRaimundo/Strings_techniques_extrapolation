# Model comparison (M0 / M1 / M2)

| Model | Role |
|-------|------|
| M0 | Constant / provisional density factor (legacy null) |
| M1 | Hierarchical log-ratio + penalized spline (Phase 1 primary) |
| M2 | Physical-informed Bayesian when covariates + `[bayes]` available |

CLI: `extrapolate compare`. Without matched technique hold-outs, status=`insufficient_for_comparison` (expected for sparse registers).
