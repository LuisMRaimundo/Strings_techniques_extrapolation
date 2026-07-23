# Collection inventory: custom_lab_01

- Display name: Custom Laboratory Collection 01
- Collection type: `measured`
- Measured or estimated: `measured`
- Format: `csv`
- Enabled: True
- Default roles: ['baseline']
- Metric definition: `ewsd_v1`
- Files found: 1
- Raw rows: 60
- Canonical rows: 60

## Source paths

- `C:\Users\lmr20\Desktop\Extrapolação de ponticelo, sord, suç tasto\data\collections\custom_lab_01\results.csv`

## Source columns

- `sample_identifier`
- `instr`
- `playing_mode`
- `sounding_note`
- `midi_sounding`
- `dyn`
- `string`
- `acoustic_density`
- `density_unit`
- `filename`
- `__source_file`

## Canonical columns

- `record_id`
- `collection_id`
- `collection_display_name`
- `collection_type`
- `source_file`
- `source_sheet`
- `source_table`
- `source_row`
- `instrument`
- `technique`
- `pitch_name_written`
- `pitch_midi_written`
- `pitch_name_sounding`
- `pitch_midi_sounding`
- `fundamental_hz`
- `string_name`
- `dynamic`
- `articulation`
- `performer_id`
- `instrument_id`
- `mute_type`
- `mute_material`
- `mute_mass`
- `harmonic_type`
- `harmonic_order`
- `stopped_pitch_name`
- `stopped_pitch_midi`
- `touched_pitch_name`
- `touched_pitch_midi`
- `density_value`
- `density_unit`
- `metric_definition_id`
- `metric_version`
- `analysis_window_id`
- `normalisation_id`
- `frequency_range_id`
- `measured_or_estimated`
- `missingness_status`
- `provenance`
- `import_timestamp_utc`
- `schema_mapping_version`
- `transformations_applied`
- `conversions_applied`
- `validation_warnings`
- `schema_validity_status`
- `metric_compatibility_status`
- `metadata_completeness_score`
- `provenance_completeness_score`
- `collection_quality_grade`
- `usable_as_baseline`
- `usable_for_pooling`
- `usable_for_calibration`
- `usable_for_validation`
- `usable_for_prediction`
- `missing_by_design_fields`
- `comparability_grade`
- `instrument_mapping_status`
- `technique_mapping_status`
- `original_instrument_label`
- `exclusion_reason`

## Content summary

- Instruments: ['vlc', 'vln']
- Techniques: ['ordinary']
- Dynamics: ['ff', 'mf', 'pp']
- Pitch range: ['A#3', 'G4']
- Metric definitions: ['ewsd_v1']
- Missing density values: 0
- Duplicate record_ids: 0

## Validation

- Schema OK: True
- Errors: []
- Warnings: []
- Details: `{"allowed_instruments": ["cb", "vla", "vlc", "vln"], "n_unsupported_instruments": 0, "unmapped_techniques": 0, "n_missing_density": 0, "n_density_present": 60}`

## Identity

- Distinct collection_id values: ['custom_lab_01']

## Notes

Example user collection with non-standard column names.
