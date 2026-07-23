# Posterior diagnostics

Frequentist Phase 1 path reports:

- `approximate_frequentist` / `approximate_interval_from_penalized_fit`
- `prior_dominated`
- outside-baseline flags

Bayesian path (optional PyMC/ArviZ) records R-hat, ESS, divergences when backend available. Without backend: `bayesian_backend_unavailable` — no fake MCMC.
