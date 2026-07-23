# Quality report: custom_test_collection

- Schema OK: True
- Errors: []
- Warnings: ["Unsupported instruments outside project scope (retained only in rejection report): ['Banjo']", '1 duplicate record_id values.']

## Summary

```json
{
  "n_records": 11,
  "schema_validity_counts": {
    "valid": 9,
    "valid_with_missing_metadata": 1,
    "invalid": 1
  },
  "metric_compatibility_counts": {
    "identical": 9,
    "unknown": 2
  },
  "quality_grade_counts": {
    "A": 8,
    "NA": 2,
    "B": 1
  },
  "usable_as_baseline": 8,
  "usable_for_pooling": 8,
  "usable_for_validation": 9,
  "mean_metadata_completeness": 0.9740181818181817,
  "mean_provenance_completeness": 0.5713999999999999,
  "usable_for_calibration": 8,
  "usable_for_prediction": 8,
  "instrument_mapping_counts": {
    "mapped": 10,
    "unsupported_instrument": 1
  }
}
```

## Details

```json
{
  "allowed_instruments": [
    "cb",
    "vla",
    "vlc",
    "vln"
  ],
  "n_unsupported_instruments": 1,
  "unsupported_instruments": [
    "Banjo"
  ],
  "duplicate_record_ids": 1,
  "duplicate_ids": [
    "CTC-001"
  ],
  "unmapped_techniques": 0,
  "n_missing_density": 1,
  "n_density_present": 10
}
```
