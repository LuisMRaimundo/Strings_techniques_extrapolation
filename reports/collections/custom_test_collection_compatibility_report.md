# Compatibility report: custom_test_collection

- Target / comparison metric: `ewsd_v1`
- Status: `unknown`
- Reason: Same metric_definition_id.; Unknown metric_definition_id: not_a_real_metric
- Records: 11
- Required conversion: None
- Uncertainty introduced: None
- Allowed operations: ['import', 'validate', 'compare', 'export_canonical']
- Prohibited operations: ['silent_minmax', 'silent_zscore', 'silent_rescale', 'silent_unit_conversion', 'silent_average', 'missing_to_zero']

## Per-metric status

```json
{
  "ewsd_v1": "identical",
  "not_a_real_metric": "unknown"
}
```

## Notes

Equal metric *names* do not imply compatible metrics. Compatibility is
determined only by `metric_definition_id` entries in
`configs/metric_definitions.yaml` and explicit conversions in
`configs/metric_conversions.yaml`.
