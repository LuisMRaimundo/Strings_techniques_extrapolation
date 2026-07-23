# Current collection coupling audit

Date: 2026-07-23  
Phase: 1 — Generic collection ingestion and metric compatibility

## Honest data status

The repository's ordinary CDM baselines in `data/baselines/*_ordinary_cdm.json`
carry metric label `EWSD_score_acoustic_balanced_midpoint_IOWA_ORCH`.

**Finding:** Separate measured IOWA and ORCHIDEA ordinary-metric tables are **not**
present as independent source corpora. Flat CSVs previously placed under
`data/collections/iowa` and `data/collections/orchidea` were **duplicated exports
of the same midpoint table** (created by `scripts/export_collection_csvs.py`).
They must **not** be treated as independent measured collections.

**Correction:** Register a single honest collection:

- `collection_id: legacy_iowa_orchidea_midpoint`
- `collection_type: pooled_derived`
- `measured_or_estimated: derived`

Do not split the midpoint into fictional per-source records.

## Coupling inventory

| File path | Line / function | Hard-coded behaviour | Why it blocks generic ingestion | Proposed correction | Changed / retained |
|---|---|---|---|---|---|
| `configs/data_schema.yaml` (pre-fix) | `source_collection.enum` | Restricted to iowa/orchidea/pooled | Rejects arbitrary collection_id | Open string `collection_id` | **Changed** |
| `configs/density_metric.yaml` (pre-fix) | `formula` | Named IOWA/ORCHIDEA midpoint in Phi text | Couples metric identity to collections | Collection-agnostic Phi; historical note only | **Changed** |
| `configs/collections.yaml` (pre-fix) | entries `iowa`, `orchidea` | Presented fabricated duplicates as measured | Falsely implies separate sources | Disabled/removed; use `legacy_iowa_orchidea_midpoint` | **Changed** |
| `scripts/export_collection_csvs.py` | loops `iowa`, `orchidea` | Writes duplicate CSVs from midpoint | Encourages false splitting | Rewrite to export only honest legacy + fixtures | **Changed** |
| `data/baselines/*.json` | `metric` field | `…_midpoint_IOWA_ORCH` | Legacy label | Retain as source of legacy collection; do not invent split | **Retained** (data) |
| `src/.../data_io.py` | `INSTRUMENT_FILE_MAP`, `HOLDOUT_FILE_MAP` | Fixed JSON filenames | Bypasses registry | Document as GUI-legacy only; not used by import | **Retained** (isolated) |
| `src/.../pipeline.py` (pre-fix) | `hash(...)` | Non-stable seeds | Breaks reproducibility | `stable_uint32` / `stable_seed` | **Changed** |
| `src/.../collections/schema_map.py` (pre-fix) | wall-clock timestamp in rows | Non-deterministic parquet | Breaks repeated-import equality | Timestamp in sidecar meta only | **Changed** |
| `configs/literature_sources.yaml` | `SRC_IOWA_MIS`, `SRC_ORCHIDEA` | Bibliographic register | OK if not used as loaders | Retain as citations only | **Retained** |
| Estimation modules | — | No `if collection_id == "iowa"` branches found | — | Keep free of collection-name branches | **Verified** |

## Fixed source_mode

| Item | Status |
|---|---|
| Current `configs/run.yaml` | Uses `run.baseline_collection_ids` (no `source_mode`) |
| Legacy outputs under `outputs/run_*` | May still mention `source_mode: pooled` as artefacts |

## Phase 1 scope reminder

Import, mapping, validation, compatibility, provenance, deterministic export only.
No technique acoustic models.
