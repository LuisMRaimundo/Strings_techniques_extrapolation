# Changelog

## 0.3.1 — Ordinary→technique workflow + user assumption registry (2026-07-23)

### Added
- `predict from-ordinary`: load ordinary CDM/baseline (e.g. violin full register at mf) and forecast specialised techniques.
- Default outputs: ordinary densities + qualitative tendencies + NA EWSD estimates (evidence path inactive).
- Separate user assumption registry (`configs/user_assumptions.yaml`) with units, scope, uncertainty, provenance, operation/link compatibility.
- Dual activation gate: run flag `--activate-user-assumptions` **and** per-assumption `active_for_density_prediction: true`.
- Assumption-based rows labelled `result_basis=user_assumption`, list `assumption_ids_used`, and never marked literature-validated or evidence-based.

## 0.3.0 — PDF state-of-the-art integration (2026-07-23)

### Added
- Structured `ProductionInstruction` schema (harmonics, bow contact, mute, bowing, performance context) with deterministic legacy migration.
- Versioned technique ontology (`configs/technique_ontology.yaml`) replacing hard-coded sixteen-cell scientific authority.
- Acoustic-descriptor registry (`configs/acoustic_descriptors.yaml`), separate from EWSD metrics; no formulas claimed as implemented.
- Qualitative acoustic constraint engine (`configs/qualitative_acoustic_constraints.yaml`); never emits EWSD numbers.
- Four analytical-level schemas: production, acoustic descriptors, perceptual organization, textural function.
- Unified applicability resolver shared by literature and prediction layers.
- Local registration of *State of the Art on String Timbral and Articulatory Techniques…* with page-located secondary-synthesis extracts.
- Parquet engine preflight with a single actionable failure for collection imports.
- Honest spectrum-aware capability states (`schema_only` / `unavailable` vs numerical transform).

### Changed
- Artificial-harmonic allowed orders include 6 (minor-third → sixth partial); interval/order consistency validated (P4→4, M3→5, m3→6, P5→3).
- `bow_position_ratio` deprecated in favour of `relative_bow_bridge_distance_beta` (documented numerator/denominator).
- Mute mass normalized to `mute_mass_g`; standard vs heavy practice mutes remain distinct.
- Numerical operations apply in declared spaces (additive density difference in density space; log-difference only for log link).
- Transfer uncertainty SD must come from config; hidden `0.1` default removed.
- Legacy 4×4 evidence matrix retained and labeled as compatibility view.
- README updated: Phase-4 prediction exists; numerical EWSD technique parameters remain inactive.

### Not implemented (deliberately)
- Universal density coefficients for sul ponticello / sul tasto / con sordino / harmonics.
- Activation of PDF-cited numerical mute figures (5–13 dB; ~35 g) as EWSD parameters without primary verification.
- Numerical spectrum → EWSD transform.
- Fitted multidimensional timbre function T(β, force, velocity, …).
