# Harmonic instrument acceptance gaps

**Generated:** 2026-07-24  
**Scope:** Violin / viola / cello natural and artificial harmonics in Strings Techniques Extrapolation (STE), with Textural Density (TD) module alignment.

## Acceptance status by module

| Module | Status | Evidence |
|---|---|---|
| Violin artificial (`violin_art_harm` / STE art) | `accepted_with_limited_coverage` | Unique measured sounding pitches at **mf**: **31** (McGill / Orchidea / Philharmonia). No silent violin→other transfer. |
| Violin natural (`violin_nat_harm` / STE nat) | `accepted_with_limited_coverage` | Unique measured pitches: **mf = 15**, **p = 9**. |
| Viola artificial (`viola_art_harm`) | `accepted_with_limited_coverage` | Unique measured pitches at **mf**: **35** (Orchidea + McGill), provenance-validated; GUI numeric only where resolver accepts. |
| Viola natural (`viola_nat_harm`) | `implemented_but_uncalibrated` | Modal register may generate pitches; acoustic EWSD = `NA` / `unsupported`. |
| Cello artificial (`cello_art_harm`) | `implemented_but_uncalibrated` | Modal only; no measured table. |
| Cello natural (`cello_nat_harm`) | `implemented_but_uncalibrated` | Modal only; no measured table. |

Do **not** mark viola/cello globally accepted because modal pitch generation succeeds.

## What is accepted

- Instrument isolation: viola/cello requests never consume violin calibration by default.
- Source-priority resolver with candidate audit (exact → same-collection dynamic transfer → multi-collection measured → optional interpolation → optional cross-instrument → `NA`).
- Collection-aware dynamic transfer  
  \(H_{d_2}(p)=H_{d_1}(p)\,O_{d_2}(p)/O_{d_1}(p)\)  
  with gates (same instrument, collection, processing version, quantity/domain, same note, valid ordinary pair). Pooled register-mean ordinary baseline is forbidden.
- Coverage manifests under `data/harmonic_calibration/manifests/`.
- Excel sheets: `Harmonic_Coverage`, `Harmonic_Source_Selection`, `Dynamic_Transfers`, `Unsupported_Harmonic_Targets`.
- GUI: **Reload calibration data** and **Show calibration status**.

## What remains provisional

- Dynamic transfer in interactive GUI runs when ordinary rows lack matching `collection` / SSA version (session ordinary without collection tags cannot pass gates).
- Violin/TD workbook modules that historically copied mf→pp/ff without transfer gates (TD violin modules still carry identical triples from earlier export; STE no longer fabricates that path).
- Viola Philharmonia natural-harmonic audio exists in batches but has **no** accepted measured CSV (SSA/schema omissions).

## Missing data by instrument

| Instrument | Artificial | Natural | Notes |
|---|---|---|---|
| Violin | mf measured (31 unique); other dynamics via gated transfer only | mf (15), p (9); ff/pp etc. gated | Limited register coverage vs full modal set |
| Viola | mf measured (35 unique) | **unavailable** | Natural SSA not accepted into measured tables |
| Cello | **unavailable** | **unavailable** | Audio catalog may exist; no measured EWSD tables |

## Missing collections and dynamics

- Violin art: no dedicated pp/ff measured harmonic tables (transfer only with compatible ordinary anchors).
- Violin nat: no ff measured table; p only Philharmonia.
- Viola art: mf only (Orchidea, McGill); no Philharmonia art table in measured set.
- Viola nat / cello art / cello nat: all dynamics missing.

## Unsupported targets (policy)

- Any target with `support_class = unsupported` → `estimate_mean = NA`.
- Cross-instrument transfer: **disabled by default**.
- Interpolation inside register: **disabled by default**.
- Pooled ordinary fallback: **disabled by default**.

## Tests and manifests required for acceptance

Required tests (present):

- `test_viola_harmonic_calibration.py`
- `test_cello_harmonic_calibration.py`
- `test_cross_instrument_transfer_blocked.py`
- `test_harmonic_dynamic_transfer.py`
- `test_harmonic_collection_gates.py`
- `test_harmonic_source_priority.py`
- `test_harmonic_coverage_manifest.py`
- `test_harmonic_collection_provenance.py`
- `test_harmonic_export_e2e.py`

Manifests (present):

- `coverage_violin_harmonics.csv`
- `coverage_viola_harmonics.csv`
- `coverage_cello_harmonics.csv`

Counts must be confirmed from canonical measured tables (not hard-coded expectations alone).
