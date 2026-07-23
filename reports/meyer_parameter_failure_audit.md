# Meyer parameter failure audit

Parameter: `MEYER_VLN_HARMONIC_DYNAMIC_RANGE`  
Date: 2026-07-23

## Diagnosis

**Primary cause: schema mismatch (A), not missing scientific links.**

The parameter ledger already contains valid foreign keys:

| Field | Value |
|---|---|
| `parameter_id` | `MEYER_VLN_HARMONIC_DYNAMIC_RANGE` |
| `source_ids` | `[MEYER_ACOUSTICS]` |
| `evidence_ids` | `[EV_MEYER_VLN_HARMONIC_DYNAMIC_RANGE]` (renamed from `EV_MEYER_VLN_HARM_001`) |
| `density_mapping_status` | `indirect_proxy` |
| `active_for_density_prediction` | `false` |
| `operation_type` | `validity_bound` |
| `numerical_scale` | `decibel_power` |
| `reported_value` / `unit` | `20.0` / `dB` |

The legacy validator in `src/string_technique_model/provenance.py` required duplicated fields on the parameter row:

- `source_id` (singular)
- `full_citation`
- `extraction_method`

Those fields correctly live on `LiteratureSource` and `EvidenceExtract`, not on every parameter.

## Source-registry record

| Field | Value |
|---|---|
| `source_id` | `MEYER_ACOUSTICS` |
| `full_citation` | present (curator-package placeholder text) |
| `authors` | `Meyer, J.` |
| `title` | present |
| `year` | `null` |
| `journal_or_publisher` | `null` |
| `local_file_path` | `literature/corpus/metadata/meyer_acoustics_curator_extraction.md` |
| `evidence_status` | `pending_local_source` |

No deposited book PDF under `literature/corpus/books/`. Source is **not** `verified_local_source`.

## Evidence-extract record

| Field | Value |
|---|---|
| `evidence_id` | `EV_MEYER_VLN_HARMONIC_DYNAMIC_RANGE` |
| `source_id` | `MEYER_ACOUSTICS` |
| `instrument` / `technique` | `vln` / `artificial_harmonic` |
| `page_start`–`page_end` | `108`–`109` |
| `canonical_variable_name` | `dynamic_range` |
| `reported_value` | `20.0` |
| `original_unit` | `dB` |
| `extraction_method` | `curator_package` |
| `density_mapping_status` | `indirect_proxy` |
| `curator_verification_status` | `validated` (curator package entry) |

## Missing / inconsistent schema items

1. Validator expected singular `source_id` / embedded `full_citation` / embedded `extraction_method`.
2. Parameter correctly uses plural `source_ids` / `evidence_ids`.
3. Legacy `validate_all_parameters()` raised on inactive candidates, crashing unrelated prediction/run pipelines.
4. No invented Meyer ISBN/year/publisher was available; source remains pending.

## Corrective action

1. Implement relational `resolve_parameter_provenance(parameter, source_registry, evidence_registry)`.
2. Validate via resolved citations and extraction methods; reject empty/placeholder strings.
3. Keep parameter inactive for density (`indirect_proxy`).
4. Strict-mode failure only for **required active** parameters with unresolved provenance.
5. Inactive/indirect failures → activation-failure ledger, not hard crash.
