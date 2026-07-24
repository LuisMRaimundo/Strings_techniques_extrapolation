# Collection inventory: custom_test_collection

- Display name: Synthetic custom test collection
- Collection type: `measured`
- Measured or estimated: `measured`
- Format: `csv`
- Enabled: True
- Default roles: ['baseline', 'descriptive_comparison']
- Metric definition: `ewsd_v1`
- Files found: 1
- Raw rows: 11
- Canonical rows: 10

## Source paths

- `E:\PYTHON CODES\CÓDIGOS FINAIS - GIT HUB\Strings_Techniques_Extrapolation\tests\fixtures\synthetic\custom_test_collection.csv`

## Source columns

- `sample_code`
- `source_instrument`
- `execution_mode`
- `note_label`
- `midi_number`
- `dyn_label`
- `acoustic_density_result`
- `metric_code`
- `room_tag`
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

- Instruments: ['cb', 'vla', 'vlc', 'vln']
- Techniques: ['ordinary', 'sul_ponticello', 'sul_tasto']
- Dynamics: ['ff', 'mf', 'pp']
- Pitch range: ['A4', 'E1']
- Metric definitions: ['ewsd_v1', 'not_a_real_metric']
- Missing density values: 1
- Duplicate record_ids: 1

## Validation

- Schema OK: True
- Errors: []
- Warnings: ["Unsupported instruments outside project scope (retained only in rejection report): ['Banjo']", '1 duplicate record_id values.']
- Details: `{"allowed_instruments": ["cb", "vla", "vlc", "vln"], "n_unsupported_instruments": 1, "unsupported_instruments": ["Banjo"], "duplicate_record_ids": 1, "duplicate_ids": ["CTC-001"], "unmapped_techniques": 0, "n_missing_density": 1, "n_density_present": 10}`

## Identity

- Distinct collection_id values: ['custom_test_collection']

## Notes

Phase-1 synthetic fixture with deliberately non-standard column names and intentional defects.
