# Nonlinear hierarchical extrapolation (Phase 1)

## Goal

Replace the primary model

\[
Y_t(p) = k_t \times Y_{\mathrm{ord}}(p)
\]

with a register-dependent log-ratio model conditioned on ordinary baselines, technique family, and evidence tier. The constant-factor model remains as **M0** (null / legacy).

## Model selection engine

```text
model = f(physical mechanism, target quantity, available data, evidence tier)
```

Implemented in `model_selection.py` + `configs/extrapolation_model_selection.yaml`.

1. Build the **admissible** set (scientific gates + covariates).
2. Choose the **data ceiling** on the ladder — never auto-pick the most complex model.

Ladder: `M0 constant → M1 linear → M2 spline → M3 hierarchical → M4 physical → M5 spectral/modal`.

| Family | Techniques |
|--------|------------|
| `bow_contact_model` | sul tasto, sul ponticello |
| `mute_transfer_model` | con sordino |
| `harmonic_modal_model` | natural/artificial harmonics |
| `execution_target_model` | flautando (not routed to sul tasto) |
| `multiphonic_component_model` | multiphonics |

Each result exports `selected_model_id`, `selection_reason`, `candidate_model_ids`, `rejected_model_ids`, `fallback_level`, `missing_covariates`, etc.

## Equations

### Ordinary baseline

\[
\log B_{i,d}(p) = \beta_0 + s_{i,d}(p)
\]

with \(s\) a penalized B-spline on MIDI. Dynamics are categorical ordinal (`pp < mf < ff`), not equally spaced numbers.

### Technique (bow contact / mute scalar)

\[
\log R_{t,i,d}(p) = \alpha_t + u_{t,i} + v_{t,d} + g_{t,i}(p)
\]

\[
Y_{t,i,d}(p) = B_{i,d}(p)\,\exp(\log R_{t,i,d}(p))
\]

**Honesty rule:** when `target_technique_observations = 0` (or fewer than needed to identify a register curve), \(g_t(p)=0\) and the result is labeled

`constant_technique_effect_over_smoothed_baseline`

not `M1_hierarchical_spline`. Fields `register_shape_identified=false`, `shape_source=constant_effect`, `g_t_active=false` are exported. \(\alpha_t\) is marked `regularization_assumption` or `user_assumption` with `alpha_origin`.

Intervals use the log-\(R\) scale:

\[
L=B\exp(\mu-z\sigma),\quad U=B\exp(\mu+z\sigma).
\]

### Mute

Spectral transfer \(A_m(f)\) is the scientific target. Phase 1 implements a **scalar descriptor approximation** (`model_reduction = scalar_descriptor_approximation`) when only EWSD scalars exist.

### Harmonics

Phase 2 stub: numeric NA; no constant factor on ordinary.

## Submodels

| Family | Module | Techniques |
|--------|--------|------------|
| Bow contact | `bow_contact_model.py` | sul_tasto, sul_ponticello |
| Mute | `mute_model.py` | con_sordino (standard performance) |
| Harmonic | `harmonic_model.py` | stub only |

## EWSD

`EWSD_score_acoustic_balanced` is modelled as an **observed scalar** via log-ratio (`observed_scalar_direct_model`). This is **not** a validated \(F(D_1,\ldots,D_k)\). When a transfer function is registered, EWSD should be computed from posterior descriptor samples.

## Evidence tiers

`LEVEL_0` … `LEVEL_4` gate language and minimum uncertainty. Unsupported / unresolved cells return NA.

## Bayesian backend

Optional: `pip install -e ".[bayes]"` (PyMC, ArviZ, patsy). Without it:

```
capability_status = bayesian_backend_unavailable
```

No fake Bayesian approximation is substituted.

## CLI

```bash
python -m string_technique_model extrapolate diagnose
python -m string_technique_model extrapolate fit-baseline --instrument vln --dynamic pp
python -m string_technique_model extrapolate fit-technique --technique sul_ponticello --instrument vln
python -m string_technique_model extrapolate predict --technique sul_ponticello --instrument vln --method hierarchical_spline
python -m string_technique_model extrapolate compare --technique sul_ponticello --instrument vln
```

Alias under `nonlinear …` remains available.

## Worked example (conceptual)

**Violin / pp / ordinary baseline → sul ponticello / spectral-score EWSD / sparse evidence**

1. Fit \(B_{\mathrm{vln},\mathrm{pp}}(p)\) on measured ordinary notes.
2. With no matched SP observations, activate prior `alpha_t_sul_ponticello` (wide, positive tendency).
3. Predict \(Y = B \exp(\alpha)\) with large approximate SD.
4. Mark `prior_dominated=True`, `evidence_tier=LEVEL_2`, export to `outputs/nonlinear_extrapolation_results.xlsx`.

## Limits

- Not acoustically validated by test passage alone.
- No automatic β / force / velocity invention from labels or dynamics.
- No silent instrument transfer (vln ↛ cb).
- Heavy practice mute refused.
- Multiphonics deferred.
