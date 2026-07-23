# Phase 2 audit — ordinary-bowing baseline engine (pre-implementation)

Date: 2026-07-23  
Scope: baseline selection, alignment, compatibility, pooling (no special-technique prediction).

## Summary

Before Phase 2, ordinary baselines were assembled ad hoc in `baselines.py` plus
`collections/pooling.py`. That path filtered techniques loosely, reused pooling
keys centred on pitch *names*, and did not export eligibility ledgers, alignment
reports, provenance ledgers, or deterministic baseline run manifests. Legacy
JSON browse helpers remain outside the import/baseline scientific path.

---

## Issues

### B1 — Ad hoc ordinary filter in `build_baseline_table`

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/baselines.py` |
| Function / line | `build_baseline_table` (~ordinary filter) |
| Current behaviour | Keeps `ordinary` / `ordinary_arco`, else falls back to the full frame |
| Scientific risk | Non-ordinary or mixed techniques can enter a “baseline” silently |
| Proposed correction | Strict eligibility (`technique == ordinary` + status fields); export exclusions |
| Implementation status | **Fixed** (`baseline/eligibility.py`) |

### B2 — Fixed two-role pooling config shape

| Field | Detail |
|-------|--------|
| File | `configs/run.yaml` |
| Function / line | `run.pooling` block |
| Current behaviour | Simple `enabled` / `method` / `weights`; no alignment key or eligibility policy |
| Scientific risk | Incomplete, non-traceable baseline runs |
| Proposed correction | Full `run.baseline` block (alignment key, compatibility, value statuses, etc.) |
| Implementation status | **Fixed** (`configs/run.yaml` `run.baseline`) |

### B3 — Pooling key defaults use pitch *name*

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/collections/canonical.py` |
| Function / line | `POOLING_KEY_DEFAULT` |
| Current behaviour | Aligns on `pitch_name_sounding` among other fields |
| Scientific risk | Enharmonic / naming drift; double-bass sounding/written confusion |
| Proposed correction | Primary acoustic key = `pitch_midi_sounding` via configurable alignment key |
| Implementation status | **Fixed** (`baseline/alignment.py`; MIDI primary key) |

### B4 — Soft user-weight normalisation

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/collections/pooling.py` |
| Function / line | `_pool_group` / `user_weighted_mean` |
| Current behaviour | Missing/zero weights fall back to equal weights |
| Scientific risk | Silent reweighting hides configuration errors |
| Proposed correction | Strict validation; refuse invalid weight maps |
| Implementation status | **Fixed** (`baseline/weighted.py`) |

### B5 — Method name `equal_mean` vs `equal_collection_mean`

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/collections/pooling.py` |
| Function / line | `POOLING_METHODS` |
| Current behaviour | Uses `equal_mean` |
| Scientific risk | Spec mismatch / ambiguous CLI |
| Proposed correction | Support `equal_collection_mean` (keep alias) |
| Implementation status | **Fixed** (`equal_collection_mean` + alias) |

### B6 — No baseline eligibility / exclusion export

| Field | Detail |
|-------|--------|
| File | (absent) |
| Function / line | n/a |
| Current behaviour | Ineligible rows dropped without ledger |
| Scientific risk | Silent discard of observations |
| Proposed correction | `eligible_for_baseline`, reasons, `excluded_baseline_records.csv` |
| Implementation status | **Implemented** |

### B7 — No alignment table / alignment report

| Field | Detail |
|-------|--------|
| File | (absent) |
| Function / line | n/a |
| Current behaviour | No cell inventory before pooling |
| Scientific risk | Unmatched / duplicate cells invisible |
| Proposed correction | `alignment_table.parquet` + `baseline_alignment_report.md` |
| Implementation status | **Implemented** |

### B8 — No observation fingerprints for duplicates

| Field | Detail |
|-------|--------|
| File | (absent for baseline) |
| Function / line | n/a |
| Current behaviour | Exact duplicate imports can inflate *n* |
| Scientific risk | Inflated sample size / false precision |
| Proposed correction | SHA-256 observation fingerprints; collapse exact import duplicates |
| Implementation status | **Implemented** (`baseline/duplicates.py`) |

### B9 — No baseline provenance ledger / run manifest

| Field | Detail |
|-------|--------|
| File | (absent) |
| Function / line | n/a |
| Current behaviour | Pooling result lacks per-record effective weights and deterministic run ID |
| Scientific risk | Non-reproducible / non-auditable baselines |
| Proposed correction | Ledger + `run_manifest.json` with SHA-256 run ID (no timestamp in ID) |
| Implementation status | **Implemented** |

### B10 — Legacy JSON baselines browse path

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/data_io.py` |
| Function / line | JSON loaders under `data/baselines` |
| Current behaviour | Browse/GUI helper for precomputed JSON midpoints |
| Scientific risk | Confusion with measured collections if treated as import source |
| Proposed correction | Keep as browse-only; scientific baseline uses registry + parquet imports |
| Implementation status | **Acceptable** (document; do not hard-code in baseline engine) |

### B11 — IOWA / ORCHIDEA naming in registry (not code branches)

| Field | Detail |
|-------|--------|
| File | `configs/collections.yaml` |
| Function / line | `legacy_iowa_orchidea_midpoint` entry |
| Current behaviour | Honest `pooled_derived` midpoint collection |
| Scientific risk | If split into fictional IOWA/ORCHIDEA rows, invents measurements |
| Proposed correction | Keep single collection; mark `measured_or_estimated=pooled_derived` in baseline |
| Implementation status | **Preserve** in Phase 2 |

### B12 — Technique estimation still present (out of Phase 2 scope)

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/estimate.py`, `pipeline.py` |
| Function / line | technique estimation scaffolding |
| Current behaviour | Later-phase estimation; literature params empty → not estimable |
| Scientific risk | Accidental special-technique values if wired into baseline |
| Proposed correction | Baseline CLI/package must not call estimation; tests assert no special techniques in baseline outputs |
| Implementation status | **Guard in Phase 2** |

### B13 — Fixed dynamic vocabulary in older lookup CLI

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/cli.py` |
| Function / line | `lookup` `--dynamic` choices `pp/mf/ff` |
| Current behaviour | Restricts interactive lookup |
| Scientific risk | Incomplete dynamics for later phases (not baseline build) |
| Proposed correction | Baseline uses full canonical dynamics from run config |
| Implementation status | **Baseline path independent** |

### B14 — Hierarchical / RE invents within-variance when missing

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/collections/pooling.py` |
| Function / line | hierarchical branch (~within variance fallback) |
| Current behaviour | Uses `1/n` when variance missing |
| Scientific risk | False precision for singleton replicates |
| Proposed correction | Explicit `insufficient_variance_information` when required; document approximation for hierarchical default |
| Implementation status | **Tightened** (`insufficient_variance_information` + equal-mean fallback) |

---

## Fixed assumptions inventory

| Assumption | Location | Status |
|------------|----------|--------|
| IOWA/ORCHIDEA code branches | none in baseline path | OK |
| Fixed two-collection design | run.yaml lists one baseline ID | generalize |
| Precomputed midpoint as measured | registry marks derived | reinforce `pooled_derived` |
| Fixed filenames in pooling | none | OK |
| Fixed metric columns in pooling | density_value + metric_definition_id | keep generic |
| Fixed notes/dynamics grid fill | none in pooling | keep missing as missing |

---

## Planned package layout (Phase 2)

```
src/string_technique_model/
  baseline/
    eligibility.py, alignment.py, duplicates.py, single_collection.py,
    pooling.py, equal_collection.py, weighted.py, robust.py,
    meta_analysis.py, hierarchical.py, reliability.py, provenance.py,
    outputs.py, manifest.py, pipeline.py
  metrics/
    compatibility.py, conversions.py
  cli/
    baseline.py
```
