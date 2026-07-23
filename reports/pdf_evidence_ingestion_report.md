# PDF evidence ingestion report

**Package version:** `0.3.0-pdf-soa-package`  
**Ingestion date:** 2026-07-23  
**Source ID:** `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`  
**Local file:** `literature/corpus/reports/string_timbral_articulatory_state_of_art.pdf` (20 pages; SHA256 verified at ingestion)

## Registered source

| Field | Value |
|---|---|
| `source_type` | `secondary_synthesis_state_of_the_art_review` |
| `evidence_status` | `verified_local_source` |
| `evidence_class` | `secondary_synthesis` |
| `author_year_status` | `unresolved` (author and date not stated in supplied PDF) |
| `not_substitute_for_cited_primaries` | `true` |
| `instruments_covered` | vln, vla, vlc, cb |

The source was added at the top of `configs/literature_sources.yaml`. All existing Meyer and bibliographic sources were retained unchanged.

## Evidence extracts appended

**18 new extracts** were appended to `configs/literature_evidence_extracts.yaml` under source `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`:

| Category | Count | Extract IDs |
|---|---:|---|
| Cross-cutting / harmonics | 6 | `EV_SOA_NONINVARIANT_001`, `EV_SOA_HARM_MECH_001`, `EV_SOA_HARM_GLISS_HALF_001`, `EV_SOA_HARM_MULTIPHONIC_001`, `EV_SOA_HARM_NOTATION_001`, `EV_SOA_HARM_INSTRUMENT_001` |
| Sul tasto | 3 | `EV_SOA_ST_MECH_001`, `EV_SOA_ST_FLAUTANDO_001`, `EV_SOA_ST_TEXTURE_001` |
| Sul ponticello | 1 | `EV_SOA_SP_MECH_001` |
| Con sordino | 4 | `EV_SOA_MUTE_MECH_001`, `EV_SOA_MUTE_MOBILITY_001`, `EV_SOA_MUTE_HEAVY_001`, `EV_SOA_MUTE_NO_TRANSFER_001` |
| Synthesis / gaps | 2 | `EV_SOA_CHAIN_LEVELS_001`, `EV_SOA_GAPS_001` |
| Prohibition notes | 2 | `EV_SOA_PROHIBITED_DENSITY_001`, `EV_SOA_PROHIBITED_NUMERICAL_001` |

All extracts carry:

- `curator_verification_status: validated`
- `evidence_class: secondary_synthesis`
- `extraction_method: pdf_page_verified`
- Page-level location fields (`page_start` / `page_end`, `section_title`)

**Numerical extracts (inactive):**

- `EV_SOA_MUTE_MOBILITY_001` — violin bridge mobility ~5–13 dB, ~1–2.5 kHz (Elie et al. cited via synthesis)
- `EV_SOA_MUTE_HEAVY_001` — heavy practice mute mass threshold ~35 g (Evangelista & Freire 2025 cited via synthesis)

Both numerical extracts set `numerical_activation_status: secondary_synthesis_requires_primary_verification` and `density_mapping_status: incompatible_variable`. **`active_for_density_prediction` was not set on any extract or parameter.**

## Corpus manifest

`literature/corpus/metadata/corpus_manifest.yaml` was updated to include the verified PDF with relative path, checksum, size, and `page_count: 20`, associated with `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`.

## EWSD activation

**No EWSD density activation occurred.** The literature layer rebuild confirms zero active density parameters from this ingestion. Secondary synthesis extracts support qualitative mechanism and conditional-tendency records only; numerical values relayed from primary studies remain inactive pending direct primary-source verification.

## Unresolved metadata

Author name and publication year were **not invented**. They remain `null` / `author_year_status: unresolved` because the supplied PDF does not state them.

## Prior package totals (unchanged Meyer extracts)

Meyer curator-package extracts (`MEYER_ACOUSTICS`): **14** (unchanged).  
**Combined extract count after ingestion:** 32.
