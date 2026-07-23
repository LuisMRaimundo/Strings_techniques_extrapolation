# Current prediction-engine audit (Phase 4 pre-implementation)

Date: 2026-07-23  
Scope: special-technique density prediction readiness after Phase 3 literature package.

## Existing prediction-related files

| Path | Role |
|---|---|
| `src/string_technique_model/estimate.py` | Legacy `estimate_cell`; name-based ratio product |
| `src/string_technique_model/pipeline.py` | Legacy run/lookup calling `estimate_cell` with raw YAML parameters |
| `src/string_technique_model/density/metric.py` | `Phi` identity on EWSD scalar |
| `configs/density_metric.yaml` | Metric definition (`Phi(D)=D`) |
| `src/string_technique_model/literature/activation.py` | Strict density activation gate (0 active) |
| `src/string_technique_model/literature/package_ingestion.py` | Curated package authority |
| `outputs/literature/active_parameters.csv` | Empty (correct) |
| `reports/literature_parameter_validation.md` | 9 candidates, 0 active |

No `prediction/` or `models/` packages existed before Phase 4.

## Hidden coefficients

- None active in runtime for special techniques.
- Explicit prohibited placeholder: `PROHIBITED_SUL_PONT_DENSITY_RATIO_1_25` (`1.25`) in `configs/literature_parameters.yaml`.

## Generic multipliers

- Legacy `estimate.py` multiplies any parameter whose name contains `ratio` / `effect` / `delta`.
- This bypasses operation type, density mapping, and activation gate.
- **Correction:** disable name-based routing; only activated ledger parameters with explicit `operation_type` may affect predictions.

## Unsupported assumptions

- Meyer dB level/dynamic/mute values are `indirect_proxy` — must not become density coefficients.
- Sul ponticello / sul tasto mechanisms supported without numerical density parameters.
- Cross-instrument transfers lack equations; default disabled.

## Source-specific logic

- No IOWA/ORCHIDEA special-case prediction branches.
- Meyer values are config-linked and inactive for density.

## Missing applicability checks (legacy)

- Legacy estimator matches only instrument + technique.
- Does not use mute type, harmonic order/type, pitch range, dynamic, string, or metric definition.

## Missing uncertainty propagation (legacy)

- Ordinary baseline SD/SE/quantiles not sampled.
- Transfer / conversion / applicability uncertainty absent.
- Unavailable uncertainty filled as `0.0` for sample SD when `n_draws==1`.

## Proposed corrections (Phase 4)

1. New evidence-gated `prediction/` + `models/` packages.
2. Legacy `run`/`estimate`/`lookup` route through the gate or refuse numerical prediction.
3. Metric-only backend activates only `direct_same_metric` / `approved_explicit_metric_mapping`.
4. Spectrum-aware backend refuses unless spectral representation is supplied.
5. Sixteen instrument–technique model configurations; NA when no active parameters.
6. Monte Carlo with SHA-256 cell seeds; never invent coefficients.

## Implementation status (pre-Phase-4)

| Component | Status |
|---|---|
| Collection ingestion | Complete |
| Ordinary baseline | Complete |
| Literature evidence package | Complete |
| Activation gate | Complete (0 active density params) |
| Technique prediction engine | Missing → implemented in Phase 4 |
| External validation workflow | Not run |
| Sensitivity analysis | Missing → scaffolding in Phase 4 |
