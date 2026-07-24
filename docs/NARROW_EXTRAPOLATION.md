# Narrow extrapolator (priority 1)

> **Status.** This document describes the **legacy narrow grid** pipeline
> (`string-technique-model extrapolate grid`). Harmonic register generation and
> the nonlinear hierarchical extrapolator are documented in
> [NONLINEAR_EXTRAPOLATION.md](NONLINEAR_EXTRAPOLATION.md) and
> [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md). The statement below that harmonics
> are “deferred” applies **only** to this legacy grid path; the primary GUI and
> nonlinear package generate modal harmonic targets (acoustic EWSD for harmonics
> remains unavailable).

Auditable pipeline for missing technique×instrument×dynamic acoustic metadata,
using measured ordinary baselines plus a curated literature-evidence table.

## Scope

**In scope**

| Transformation | Mute |
|---|---|
| ordinario → sul tasto | off |
| ordinario → sul ponticello | off |
| ordinario → standard con sordino | orchestral/performance mute |

Instruments: `vln`, `vla`, `vlc`, `cb`  
Dynamics: `pp`, `mf`, `ff`

**Out of scope (first model)**  
multiphonics, heavy practice mutes, flautando, on-bridge, afterlength bowing.

**Deferred (priority 2)**  
artificial harmonics, natural harmonics.

## Inputs

1. **Measured ordinary baselines (preferred)** — Spectral_Analyser  
   `compiled_density_metrics_research.xlsx` → sheet `Spectral_Density_Metrics` → column  
   `EWSD_score_acoustic_balanced`  
   Listed in `configs/extrapolation/orchidea_ordinary_manifest_v1.yaml` (default root `D:/CORDAS/Orchidea`).  
   Example:  
   `D:/CORDAS/Orchidea/ORCH_Vln/Violin/ordinario/ORCH_arco_Vln_pp/_Sustains/analysis_results/compiled_density_metrics_research.xlsx`
2. **Fallback** — `data/baselines/{violin,viola,cello,double_bass}_ordinary_cdm.json` if research Excels are missing
3. **Literature evidence** — `configs/extrapolation/literature_evidence_v1.yaml`
4. **Target grid** — `configs/extrapolation/target_grid_v1.yaml`

Research Excel values are **measured** ordinary baselines only. They are **not** used as invented EWSD transforms for sul tasto / sul ponticello / con sordino.

## Policy

- Do **not** numerically extrapolate `EWSD_score_acoustic_balanced` for techniques until a validated formula/component mapping exists. Technique EWSD cells are `unavailable` with an explicit `na_reason`.
- Ordinary EWSD means are emitted as `measured` reference rows.
- Mute attenuation (dB power) is instrument-specific literature-bounded where curated (e.g. violin ~6 dB, viola ~4 dB); cello/bass remain `unavailable`. Never apply mute dB as an EWSD multiplier.
- Spectral components (centroid, slope, HNR, flux, frame-centroid variance, upper-partial energy) use technique-specific qualitative or unavailable evidence — no universal multiplier.
- Insufficient evidence → `NA` / `unavailable` with reason; do not invent numbers.

## Output

Excel workbook with sheets:

- `Extrapolation_Results` — full auditable cell table
- `Run_Summary`
- `Measured_Baseline` / `Literature_Bounded` / `Qualitative_Only` / `Unavailable_NA`

Each cell includes instrument, technique, dynamic, target_quantity, value, bounds, unit, value_kind, evidence_status, source, source_page, measurement_domain, extrapolation_method, baseline_record_ids, uncertainty, measured_or_extrapolated, assumptions_used, warnings (plus mute_state, evidence_id, baseline_ewsd_mean, na_reason).

## CLI

```bash
python -m string_technique_model extrapolate
python -m string_technique_model extrapolate --research-excel path/to/compiled_density_metrics_research.xlsx
python -m string_technique_model extrapolate --output outputs/extrapolation/my_run.xlsx
```

Default output: `outputs/extrapolation/narrow_priority1_extrapolation.xlsx`
