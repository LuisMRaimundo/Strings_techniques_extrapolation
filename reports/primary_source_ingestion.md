# Primary source ingestion report

**Package extract version:** `0.4.0-primary-source-ingestion`  
**Date:** 2026-07-23  
**Scope:** All `verified_local_source` PDFs in the archive corpus (articles + books)

## Summary

Fourteen new **qualitative / mechanism / constraint** extracts were appended for peer-reviewed articles and bowed-string book chapters. **No EWSD density parameters were activated.** Numerical values in Evangelista (2025) and standardized regression coefficients in Schoonderwaldt (2009) remain **inactive** for density prediction.

| Source ID | New extracts | EWSD activation |
|---|---:|---|
| `SRC_SCHOONDERWALDT_2009` | 3 | No |
| `SRC_EVANGELISTA_FREIRE_2025` | 3 | No |
| `SRC_FALLOWFIELD_TEMPO_MULTIPHONICS` | 2 | No |
| `SRC_LOSTANLEN_ANDEN_LAGRANGE_2018` | 1 | No |
| `SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE` | 1 | No |
| `SRC_FLETCHER_ROSSING_1991` | 2 | No |
| `SRC_ROSSING_SCIENCE_STRING_INSTRUMENTS_2010` | 2 | No |
| `MEYER_ACOUSTICS` | 0 (14 prior curator-package extracts unchanged) | No |
| `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART` | 0 (18 prior SOA extracts unchanged) | No |

**Combined extract count after ingestion:** 46 (32 prior + 14 new).

---

## Per-source coverage

### `SRC_SCHOONDERWALDT_2009`

- **PDF:** `literature/corpus/articles/schoonderwaldt_2009_violinists_sound_palette.pdf` (14 pp.)
- **Variables supported (qualitative):** `relative_bow_bridge_distance_beta`, bow force, bow velocity, spectral centroid (string-velocity domain), pitch flattening
- **Extract IDs:** `EV_SCHOONDERWALDT_BETA_DEF_001`, `EV_SCHOONDERWALDT_DOMAIN_SEP_001`, `EV_SCHOONDERWALDT_STDREG_WARNING_001`
- **Constraints:** Centroid derived from string velocity / compensated bridge-force estimates — **not** radiated audio (`measurement_domain_id: string_velocity_at_bow`). Standardized regression β on z-scored variables = relative importance only; not portable equations.
- **Numerical portability:** Table I coefficients and fc maps are **not** activated for EWSD.
- **Limitations:** Monochord + bowing machine; violin-only; Helmholtz-focused subset.

### `SRC_EVANGELISTA_FREIRE_2025`

- **PDF:** `literature/corpus/articles/evangelista_freire_2025_heavy_violin_practice_mutes.pdf` (7 pp.)
- **Variables supported (qualitative):** mute mass, mute category (performance / light practice / heavy practice), LTAS, loudness (sones), intensity reduction (%)
- **Extract IDs:** `EV_EVANGELISTA_MASS_INSUFFICIENT_001`, `EV_EVANGELISTA_NO_MASS_ATTENUATION_LAW_001`, `EV_EVANGELISTA_NO_EWSD_001`
- **Constraints:** Mass, rigidity, shape, material, and bridge contact jointly determine outcome; **no universal attenuation = f(mass)** above ~35 g functional limit. LTAS/loudness are radiated-audio descriptors only.
- **Numerical portability:** Table 1 mass/loudness/% rows **not** ingested into `configs/datasets/evangelista_freire_2025_mute_table.yaml` (still `metadata_stub`, empty rows).
- **Limitations:** Two violins; glissando protocol; Zenodo companion external/unresolved.

### `SRC_FALLOWFIELD_TEMPO_MULTIPHONICS`

- **PDF:** `literature/corpus/articles/fallowfield_2020_cello_multiphonics_tempo.pdf` (19 pp.)
- **Variables supported (qualitative):** touching position ratio, multiphonic partial clusters, bow side — **schema pointer only**
- **Extract IDs:** `EV_FALLOWFIELD_MULTIPHONIC_DEF_001`, `EV_FALLOWFIELD_SCHEMA_PTR_001`
- **Constraints:** Multiphonics ≠ natural/artificial/half harmonics or double stops; no invented fingerings or pitch sets.
- **Numerical portability:** None for EWSD; Cello Map repository referenced, not transcribed here.
- **Limitations:** Cello-only; outside legacy 4×4 evidence matrix (`technique: null`, `evidence_scope: multiphonic`).

### `SRC_LOSTANLEN_ANDEN_LAGRANGE_2018`

- **PDF:** `literature/corpus/articles/lostanlen_anden_lagrange_2018_extended_playing_techniques.pdf` (10 pp.)
- **Variables supported:** technique recognition labels (SOL dataset taxonomy)
- **Extract ID:** `EV_LOSTANLEN_RECOGNITION_ONLY_001`
- **Constraints:** Recognition / query-by-example only; classification confidence ≠ acoustic certainty; **no EWSD mapping**.
- **Numerical portability:** None.
- **Limitations:** MIR benchmark on SOL; not a physical acoustics primary for density.

### `SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE`

- **PDF:** `literature/corpus/books/stowell_cambridge_companion_technique_performing_practice.pdf` (21 pp.)
- **Variables supported:** historical terminology (sul ponticello, sulla tastiera, col legno, tremolo)
- **Extract ID:** `EV_STOWELL_TERMINOLOGY_001`
- **Constraints:** Performance-practice / notation history only; no acoustic measurements.
- **Numerical portability:** None.
- **Limitations:** Partial excerpt; mislabelled legacy filename resolved in `source_identity_validation.yaml`.

### `SRC_FLETCHER_ROSSING_1991`

- **PDF:** `literature/corpus/books/fletcher_rossing_1991_physics_of_musical_instruments.pdf` (628 pp.)
- **Variables supported (qualitative):** bowed-string motion, Helmholtz motion, bridge impedance, body modes, sound radiation
- **Extract IDs:** `EV_FLETCHER_ROSSING_CH10_BOWED_001` (pp. 235–283), `EV_FLETCHER_ROSSING_HELMHOLTZ_001` (§2.10, pp. 45–47)
- **Constraints:** Generic bowed-string physics; sul ponticello / sul tasto not indexed as separate techniques in Ch. 10.
- **Numerical portability:** Book-level equations not transcribed into parameter ledger.
- **Limitations:** Textbook breadth; technique-specific timbral claims require page-level follow-up.

### `SRC_ROSSING_SCIENCE_STRING_INSTRUMENTS_2010`

- **PDF:** `literature/corpus/books/rossing_2010_science_of_string_instruments.pdf` (466 pp.)
- **Variables supported (qualitative):** bowed strings (Ch. 12), violin body/bridge/radiation (Ch. 13)
- **Extract IDs:** `EV_ROSSING2010_CH12_BOWED_001` (pp. 197–208), `EV_ROSSING2010_CH13_VIOLIN_001` (pp. 209–244)
- **Constraints:** Edited volume; deposit activates qualitative mechanism support only.
- **Numerical portability:** Chapter-level; no density coefficients.
- **Limitations:** Multi-author volume; mute / sul pont / sul tasto need chapter-specific curation beyond this pass.

### `MEYER_ACOUSTICS`

- **PDF:** `literature/corpus/books/meyer_2009_acoustics_and_the_performance_of_music.pdf` (446 pp.)
- **Status:** 14 prior curator-package extracts unchanged (`extraction_method: curator_package`).
- **Variables:** artificial harmonics, sul ponticello, sul tasto, con sordino — mix of qualitative mechanisms and **indirect_proxy** dB level bounds.
- **EWSD activation:** No. dB figures are not density multipliers.
- **Limitations:** Prior extracts await page-level re-verification against deposited PDF for full primary status.

### `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`

- **PDF:** `literature/corpus/reports/string_timbral_articulatory_state_of_art.pdf` (20 pp.)
- **Status:** 18 SOA extracts from prior ingestion; secondary synthesis — **must not** activate EWSD.
- **Not a substitute** for cited primaries (Evangelista, Elie, etc.).

---

## Files affected

| File | Change |
|---|---|
| `configs/literature_evidence_extracts.yaml` | +14 extracts; version bump |
| `src/string_technique_model/production/models.py` | `MuteCategory` additive aliases |
| `src/string_technique_model/production/migration.py` | Mute type alias map |
| `src/string_technique_model/constraints/engine.py` | Legacy mute flattening uses new categories |
| `tests/test_primary_source_ingestion.py` | New focused tests |
| `reports/article_code_contributions.md` | New |
| `reports/primary_source_ingestion.md` | This report |

## Production / bow model fields

`BowContactInstruction` and `BowingConditions` already expose `relative_bow_bridge_distance_beta`, `bow_bridge_distance_m`, `speaking_length_m`, and `force_n` (bow force). No schema changes required for bowing fields.

## EWSD activation gate

**Confirmed inactive:** `build_literature_layer(dry_run=True)` reports `n_active_density_parameters == 0` after ingestion.
