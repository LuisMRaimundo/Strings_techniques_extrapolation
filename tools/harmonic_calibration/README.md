# Violin harmonic acoustic calibration

Unlocks STE `no_harmonic_acoustic_calibration_data` by building **measured EWSD**
tables from local audio (Philharmonia, McGill, Orchidea), then wiring a
`calibrated_harmonic_descriptor_model`.

## Why existing Philharmonia `compiled_density_metrics.xlsx` is insufficient

1. **Scale mismatch** — older Philharmonia CDM values are ~0.02–0.4; Textural Density /
   STE ordinary tables use Zenodo-scale CDM/EWSD (~5–100).
2. **Type collapse** — mf sustains mixed natural + artificial into note folders without
   preserving technique labels.
3. **Not Stage-3 EWSD** — missing `EWSD_score_acoustic_balanced` research export.

## Audio inventory (catalogued)

| Collection | Technique | Dynamics | Unique notes (deduped batch) |
|---|---|---|---|
| Orchidea | artificial_harmonic | mf | 29 |
| Philharmonia | artificial_harmonic | mf | 20 |
| Philharmonia | natural_harmonic | mf, p | 11 / 10 |
| McGill | artificial / natural | mf (assumed) | 13 / 9 |
| Philharmonia / Orchidea | ordinario | pp…ff | baseline for ratios |

Catalog: `data/harmonic_calibration/violin_harmonic_audio_catalog.csv`

## Pipeline

```bash
# 1) Catalog
python tools/harmonic_calibration/catalog_violin_harmonic_sources.py

# 2) Stage note-deduplicated batches (hardlinks)
python tools/harmonic_calibration/stage_harmonic_audio_batches.py

# 3) Spectral_Analyser Stage 1–3 (example: Orchidea art harm pilot)
cd ".../Spectral_Analyser"
python run_orchestrator.py --audio-dir ".../data/harmonic_calibration/batches/orchidea_artificial_harmonic_mf" --pattern "*.wav" --main-output ".../data/harmonic_calibration/ssa_outputs/orchidea_artificial_harmonic_mf"
```

Expected artefact: `compiled_density_metrics_research.xlsx` with
`EWSD_score_acoustic_balanced`.

## Status (2026-07-24)

- Catalog + staged batches: done.
- **Orchidea artificial_harmonic mf SSA Stage 1–3: done** (29 notes).
  - Measured CSV: `data/harmonic_calibration/measured/orchidea_artificial_harmonic_mf.csv`
- **STE calibrated descriptor model: enabled**
  - `configs/extrapolation_model_selection.yaml` → `harmonic_modal_frequency_with_descriptor_priors.enabled: true`
  - Lookup: `harmonic_calibration_table.py` + `harmonic_model.py`
  - Artificial harmonics with measured notes now emit numeric `estimate_mean`
  - Natural harmonics remain NA until natural tables are processed
- Measured tables merged (55 unique instrument×technique×dynamic×note keys):
  - artificial mf: 31 (Orchidea + Philharmonia + McGill)
  - natural mf: 15; natural p: 9
- Philharmonia quirks: B6 (art) and D#6 (nat p) skipped — SSA stale-schema guard

## Next STE / TD steps

1. Finish Philharmonia/McGill SSA exports into `measured/*.csv` (auto-merged by loader).
2. Re-export Violin Excel; regenerate TD `violin_art_harm` / add `violin_nat_harm`.

## Provenance policy

- Holdout `violin_artificial_harmonic.json` remains **external validation only**.
- New Philharmonia / McGill / Orchidea EWSD tables are the calibration corpus.
- Uncertainty stays **high** until multi-dynamic coverage is complete (pp/mf/ff).
