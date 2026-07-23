# Phase 3 audit — specialised-literature evidence layer (pre-implementation)

Date: 2026-07-23  
Scope: corpus registry, evidence matrix, parameter provenance for  
`{vln,vla,vlc,cb} × {artificial_harmonic,sul_ponticello,sul_tasto,con_sordino}`.  
No technique-density prediction in this phase.

## Local corpus findings

| Asset class | Finding |
|-------------|---------|
| PDF / DOCX / BibTeX / RIS under project | **None found** (`literature/`, `data/literature/` absent) |
| `configs/literature_sources.yaml` | Bibliographic stubs; most lack local PDFs and page-level extracts |
| `configs/literature_parameters.yaml` | `parameters: []` — correctly inactive |
| Density metric | `configs/density_metric.yaml` — EWSD acoustic-balanced scalar; formula unresolved for recomputation |
| Ordinary baseline schema | Phase 2 long table — ordinary only; not technique evidence |

---

## Issues

### L1 — Incomplete Schoonderwaldt citation

| Field | Detail |
|-------|--------|
| File | `configs/literature_sources.yaml` |
| Current reference | Vague “Acta Acustica / related studies”; DOI null |
| Completeness | **incomplete_reference** |
| Scientific problem | Cannot support parameters without complete citation + located passage |
| Corrective action | Mark incomplete; separate export; no extracts |
| Implementation status | **Fixed** |

### L2 — Schelleng 1973 complete citation but no local PDF

| Field | Detail |
|-------|--------|
| File | `configs/literature_sources.yaml` / `SRC_SCHELLENG_1973` |
| Current reference | JASA 53(1) 26–41; DOI present |
| Completeness | Bibliographically complete; **not locally available** |
| Scientific problem | Claiming quantitative/qualitative support without reading violates Phase 3 rules |
| Corrective action | `bibliographically_verified_but_not_locally_available`; no active extracts |
| Implementation status | **Fixed** |

### L3 — Schelleng 1974 Sci. Am. qualitative only, no local PDF

| Field | Detail |
|-------|--------|
| File | `configs/literature_sources.yaml` / `SRC_SCHELLENG_1974_SCI_AM` |
| Completeness | Citation fields present; local content unread |
| Scientific problem | Qualitative adjectives must not become coefficients |
| Corrective action | Same as L2; no numerical parameters |
| Implementation status | **Fixed** |

### L4 — IOWA / ORCHIDEA as ordinary baselines only

| Field | Detail |
|-------|--------|
| File | `configs/literature_sources.yaml` |
| Scientific problem | Ordinary audio collections are not technique-parameter literature |
| Corrective action | `excluded` for technique evidence layer (baseline role only) |
| Implementation status | **Fixed** |

### L5 — Hold-out measured techniques forbidden for literature parameters

| Field | Detail |
|-------|--------|
| File | `SRC_TD_MEASURED_HOLD_OUT` |
| Scientific problem | Using hold-out as literature evidence leaks validation data |
| Corrective action | `excluded` from literature parameter construction |
| Implementation status | **Fixed** |

### L6 — Empty parameters list is correct but unstructured for Phase 3 ledger

| Field | Detail |
|-------|--------|
| File | `configs/literature_parameters.yaml` |
| Scientific problem | Need full ledger schema, unresolved/prohibited rows, density mapping |
| Corrective action | Expand schema; keep **no active** parameters |
| Implementation status | **Implemented** |

### L7 — No sixteen-cell evidence matrix

| Field | Detail |
|-------|--------|
| File | (absent) |
| Scientific problem | Cannot audit which of 16 cells are estimable |
| Corrective action | Generate matrix with honest NA grades |
| Implementation status | **Implemented** |

### L8 — Provenance helper predates extract/matrix rules

| Field | Detail |
|-------|--------|
| File | `src/string_technique_model/provenance.py` |
| Scientific problem | Incomplete vs Phase 3 operation_type / numerical_scale / density_mapping |
| Corrective action | Literature package validation supersedes for Phase 3; keep estimate path inactive |
| Implementation status | **Extended** (`literature/validation.py`) |

### L9 — No invented DOI / pages allowed

| Field | Detail |
|-------|--------|
| File | several stubs |
| Scientific problem | Temptation to “complete” citations inventively |
| Corrective action | Null fields remain null; incomplete export separate |
| Implementation status | **Enforced** |

---

## Correct scientific posture for this snapshot

Because no verified local specialised literature PDFs with curated page-level
extracts exist in the repository:

- **zero** sources have `evidence_status = verified_local_source` for technique acoustics;
- **zero** active numerical technique parameters;
- all **sixteen** instrument–technique cells are **NA / not_estimable_from_current_evidence**;
- gaps are **critical** for every cell that would be needed for prediction.
