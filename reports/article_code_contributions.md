# Article ↔ code contributions map

**Date:** 2026-07-23  
**Purpose:** Trace verified primary PDFs to package variables, schemas, and explicit non-mappings (no invented EWSD).

---

## Schoonderwaldt (2009) — `SRC_SCHOONDERWALDT_2009`

| Article concept | Code / config touchpoint | Contribution type |
|---|---|---|
| Relative bow–bridge distance β | `BowContactInstruction.relative_bow_bridge_distance_beta`; `compute_beta()` | Variable definition aligned |
| Bow force, bow velocity | `BowingConditions.force_n`, `velocity_m_s` | Production instruction fields |
| Spectral centroid (string-velocity domain) | `measurement_domain_id: string_velocity_at_bow` on extract | **Domain separation** — not `radiated_audio` |
| Standardized regression coefficients | Extract warning only | **Not** portable to EWSD |
| Schelleng diagram / pitch flattening | Qualitative constraints engine (future); no numeric ledger | Mechanism note |

**Extracts:** `EV_SCHOONDERWALDT_BETA_DEF_001`, `EV_SCHOONDERWALDT_DOMAIN_SEP_001`, `EV_SCHOONDERWALDT_STDREG_WARNING_001`

---

## Evangelista & Freire (2025) — `SRC_EVANGELISTA_FREIRE_2025`

| Article concept | Code / config touchpoint | Contribution type |
|---|---|---|
| Mute categories: performance / light practice / heavy practice | `MuteCategory` literals: `performance_mute`, `light_practice`, `heavy_practice` (+ legacy aliases) | Taxonomy expansion |
| Mute mass (g) | `MuteInstruction.mute_mass_g`; `normalize_mute_mass()` | Field present; table rows empty |
| LTAS, loudness (sones), intensity % | `configs/datasets/evangelista_freire_2025_mute_table.yaml` (stub); `configs/analysis_profiles/evangelista_freire_2025_ltas.yaml` | **Not** EWSD |
| Nonlinear mass–attenuation limit | Qualitative extract + tests | **Prohibits** attenuation = f(mass) |

**Extracts:** `EV_EVANGELISTA_MASS_INSUFFICIENT_001`, `EV_EVANGELISTA_NO_MASS_ATTENUATION_LAW_001`, `EV_EVANGELISTA_NO_EWSD_001`

**Explicit non-mapping:** Loudness/LTAS/intensity reductions → EWSD density parameters.

---

## Fallowfield (TEMPO) — `SRC_FALLOWFIELD_TEMPO_MULTIPHONICS`

| Article concept | Code / config touchpoint | Contribution type |
|---|---|---|
| Multiphonic ≠ harmonics | `MultiphonicInstruction`; `assert_distinct_from_harmonics()` | Schema + validation |
| Touching position, partial clusters | `MultiphonicInstruction.touching_position_ratio`, `expected_pitch_components` | Fields only — **no curated pitch rows** |
| Cello Map / smartphone charts | `related_technique_note` on extract | External repository pointer |

**Extracts:** `EV_FALLOWFIELD_MULTIPHONIC_DEF_001`, `EV_FALLOWFIELD_SCHEMA_PTR_001`

---

## Lostanlen, Andén & Lagrange (2018) — `SRC_LOSTANLEN_ANDEN_LAGRANGE_2018`

| Article concept | Code / config touchpoint | Contribution type |
|---|---|---|
| Extended IPT recognition (SOL) | `TechniqueRecognitionResult`; `claims_ewsd` guard | Recognition-only |
| Sul pont / sul tast / mute labels in taxonomy | `recognition` module; internal ontology `unresolved` | Label vocabulary — not density |

**Extract:** `EV_LOSTANLEN_RECOGNITION_ONLY_001`

**Explicit non-mapping:** Classification confidence → EWSD.

---

## Stowell — Cambridge Companion excerpt — `SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE`

| Article concept | Code / config touchpoint | Contribution type |
|---|---|---|
| sul ponticello, sulla tastiera, col legno | `BowContactCategory`; historical notes | Terminology only |
| Vibrato, scordatura, harmonics (historical) | Ontology docs; no numeric params | Performance-practice context |

**Extract:** `EV_STOWELL_TERMINOLOGY_001`

---

## Fletcher & Rossing (1991) — `SRC_FLETCHER_ROSSING_1991`

| Book section | Code / config touchpoint | Contribution type |
|---|---|---|
| §2.10 Bowed string (pp. 45–47) | Generic bowed-string constraints | Helmholtz / stick-slip mechanism |
| Ch. 10 Bowed string instruments (pp. 235–283) | `generic_bowed_string_physics` directness | Bridge, body, radiation context |

**Extracts:** `EV_FLETCHER_ROSSING_HELMHOLTZ_001`, `EV_FLETCHER_ROSSING_CH10_BOWED_001`

**No technique-specific EWSD** from book deposit alone.

---

## Rossing (2010) edited volume — `SRC_ROSSING_SCIENCE_STRING_INSTRUMENTS_2010`

| Chapter | Pages (verified TOC) | Contribution type |
|---|---|---|
| Ch. 12 Bowed Strings | 197–208 | Family-wide bowed-string overview |
| Ch. 13 Violin | 209–244 | Body modes, bridge, radiation — qualitative |

**Extracts:** `EV_ROSSING2010_CH12_BOWED_001`, `EV_ROSSING2010_CH13_VIOLIN_001`

---

## Meyer (2009) — `MEYER_ACOUSTICS`

| Topic | Existing package artifacts | EWSD |
|---|---|---|
| Artificial harmonics | 4 mechanism + 4 instrument level extracts | No |
| Sul ponticello / sul tasto / mute | Mechanism extracts | No |
| dB dynamic ranges | `indirect_proxy` extracts | **No** — not density multipliers |

14 prior extracts in `literature_evidence_extracts.yaml`; PDF deposited and identity-verified; page-level primary re-verification pending for full promotion from `curator_package`.

---

## Secondary synthesis (not primary, listed for completeness)

**`SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`** — 18 extracts; relays Evangelista/Elie numerics with `secondary_synthesis_requires_primary_verification`. Must not substitute for primaries above.

---

## Cross-cutting rules enforced in code/tests

1. **Measurement domains** — `configs/measurement_domains.yaml`; Schoonderwaldt centroid ≠ radiated audio.
2. **Mute mass** — informative, not a universal attenuation law (Evangelista tests).
3. **Multiphonics** — distinct from harmonics; no invented fingerings.
4. **Recognition** — `TechniqueRecognitionResult.claims_ewsd is False`.
5. **Density gate** — `n_active_density_parameters == 0` after literature rebuild.

---

## Tests added

`tests/test_primary_source_ingestion.py`:

- Schoonderwaldt measurement-domain separation and standardized-regression warning
- Evangelista nonlinear mute / no mass→attenuation law / no EWSD from LTAS
- Primary ingestion does not activate density parameters
- `MuteCategory` additive aliases (`performance_mute`, `light_practice`, `heavy_practice`)
