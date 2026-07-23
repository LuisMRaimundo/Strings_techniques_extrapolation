# String Technique Density Model

Literature-informed estimation of acoustic density for extended bowed-string techniques.

**Phase 1:** generic multi-collection ingestion and metric compatibility.  
**Phase 2:** ordinary-bowing baseline engine.  
**Phase 3:** specialised-literature evidence framework (auditable; curated package + local corpus).  
**Phase 4:** evidence-gated prediction engine (Monte Carlo). Numerical EWSD technique parameters remain **inactive** until activated mappings exist — predictions therefore typically return NA.

**v0.3:** compositional production instructions, expanded technique ontology, acoustic-descriptor registry, qualitative constraint layer, and integration of the local secondary synthesis *State of the Art on String Timbral and Articulatory Techniques* (author/year unresolved in the PDF). See `CHANGELOG.md`.

Absence of evidence in the local corpus must not be interpreted as
evidence of absence in the specialised literature.

## Strict instrument domain

Only orchestral bowed strings are in scope:

- `vln` (violin)
- `vla` (viola)
- `vlc` (cello / violoncello)
- `cb` (double bass / contrabass)

Aliases are exact matches only (case-insensitive, trimmed). No fuzzy matching.
Out-of-scope instruments are written to
`outputs/rejected/<collection_id>_rejected_records.csv` and are **excluded** from
`outputs/imported/<collection_id>.parquet` unless `--include-invalid-records` is set.

See `configs/instrument_domain.yaml` and `configs/technique_ontology.yaml`.

## Production instructions (v0.3)

The flat `technique` column remains a **legacy compatibility label**. Combined states
(e.g. artificial harmonic + sul ponticello + mute) are represented by
`ProductionInstruction` (`string_technique_model.production`). Migrate with:

```python
from string_technique_model.production import migrate_legacy_technique_record
prod = migrate_legacy_technique_record(legacy_row_dict)
```

Flautando is **not** auto-mapped to sul tasto. On-bridge and afterlength bowing are
outside the tasto–ponticello continuum. Mute mass prefers `mute_mass_g`.

## Dependencies / Parquet

- Python `>=3.10`
- Parquet via `pyarrow` is **mandatory** for collection import outputs. Missing engines fail once in preflight with an actionable message (`pip install 'pyarrow>=14.0,<20'`).
- Prediction may write CSV if Parquet fails, with an explicit warning.

## Quick start (Windows)

```bat
run.bat
```

```bat
python -m pip install -e ".[dev]"
python -m string_technique_model collection list
python -m string_technique_model literature build-all
python -m string_technique_model predict from-ordinary --instrument vln --dynamic mf
```

### Ordinary → techniques

Default (evidence-backed numerical parameters inactive):

```bat
python -m string_technique_model predict from-ordinary --instrument vln --dynamic mf
```

Writes ordinary baseline densities, **NA** technique EWSD estimates, and qualitative tendencies under `outputs/predictions/from_ordinary/`.

User numerical assumptions live in `configs/user_assumptions.yaml` and stay **inactive** unless you both:

1. pass `--activate-user-assumptions`, and  
2. set `active_for_density_prediction: true` on specific assumptions.

Assumption-based rows are labelled `result_basis=user_assumption`, list `assumption_ids_used`, and are **never** marked literature-validated or evidence-based.

## Literature corpus

Place local PDFs/texts under:

```text
literature/corpus/books/
literature/corpus/articles/
literature/corpus/theses/
literature/corpus/reports/
literature/corpus/metadata/
```

Registered secondary synthesis:

- `literature/corpus/reports/string_timbral_articulatory_state_of_art.pdf`
- source id `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`

PDF presence alone does **not** activate EWSD parameters. Secondary-synthesis
numerical figures require primary-source verification before numerical activation.

The legacy 4×4 instrument×technique evidence matrix is a **compatibility view**;
scientific authority is the compositional ontology + qualitative constraints.

## Tests / lint / types

```bat
python -m pytest -q
python -m ruff check src tests
python -m mypy src/string_technique_model
```

## Reports

- `reports/pdf_integration_audit.md`
- `reports/pdf_evidence_ingestion_report.md`
- `reports/technique_ontology_report.md`
- `reports/acoustic_descriptor_registry.md`
- `reports/qualitative_constraints_report.md`
- `reports/schema_migration_report.md`
- `reports/literature_gaps.md`
- `reports/test_status.md`
