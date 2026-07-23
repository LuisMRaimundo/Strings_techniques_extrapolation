# Schema migration report

## Version

- Production schema: `production_instruction_v1`
- Ontology: `0.3.0-pdf-soa-ontology`
- Literature package: `0.3.0-pdf-soa-package`
- Prediction config: `0.3.0-pdf-soa-prediction`

## Legacy → ProductionInstruction

`migrate_legacy_technique_record(dict)` maps:

| Legacy `technique` | Result |
|---|---|
| ordinary | ordinary_stopped + ordinario + mute off |
| artificial_harmonic | left-hand artificial_harmonic; optional bow/mute preserved |
| sul_tasto / sul_ponticello | bow category; mute on if mute_type present |
| con_sordino | mute on; category from mute_type or unresolved (never silent orchestral default) |
| flautando | `timbre_execution_target=flautando` (not sul_tasto); warning |

Warnings are recorded in `migration_warnings`. Tabular export via `production_to_tabular` uses scalars only.

## Field deprecations

- `bow_position_ratio` → prefer `relative_bow_bridge_distance_beta` (semantics documented)
- `mute_mass` string → prefer `mute_mass_g` after `normalize_mute_mass`

## Compatibility

Existing collections with flat `technique` labels continue to import. The flat column is no longer the authoritative representation of combined production states.
