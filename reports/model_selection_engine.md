# Model selection engine

## Principle

```text
model = f(mechanism, target_quantity, available data, evidence tier)
```

Two stages: (1) scientifically admissible candidates; (2) data-ceiling choice on the complexity ladder. Never auto-select the most complex model.

## Config

`configs/extrapolation_model_selection.yaml` — thresholds and family ladders are explicit and tunable.

## Families

| Family | Techniques | Example selection with zero tech obs |
|--------|------------|--------------------------------------|
| bow_contact_model | sul_tasto, sul_ponticello | `constant_technique_effect_over_smoothed_baseline` / `no_target_technique_observations` |
| mute_transfer_model | con_sordino | `constant_assumption_fallback` (not spectral) |
| harmonic_modal_model | harmonics | `harmonic_modal_metadata_gate` / `harmonic_modal_acoustic_model_unavailable` → NA |
| execution_target_model | flautando | qualitative/NA (not sul_tasto) |
| multiphonic_component_model | multiphonics | qualitative/NA |

## Ladder

M0 constant → M1 linear → M2 spline → M3 hierarchical → M4 physical-informed → M5 spectral/modal

Physical-informed bow contact is **rejected** when `beta` (etc.) is missing.

## Export

Sheet `Model_Selection` in `outputs/nonlinear_extrapolation_results.xlsx`.
