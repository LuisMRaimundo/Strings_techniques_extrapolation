# User assumption registry

**Config:** `configs/user_assumptions.yaml`  
**Kind:** `user_numerical_assumptions`  
**Literature-validated:** **false** (always)

## Separation rule

User assumptions are never literature parameters. Prediction outputs that use them must be labelled `assumption_based` and must not be labelled `evidence_based` or `literature_validated`.

## Activation gate (dual)

Assumptions remain inactive unless **both**:

1. Run mode is `evidence_plus_user_assumptions` / CLI `--activate-user-assumptions`
2. The individual entry has `active_for_density_prediction: true`

Default mode is `evidence_only`.

## CLI

```text
python -m string_technique_model assumptions list
python -m string_technique_model assumptions validate
python -m string_technique_model assumptions show ASSUMPTION_ID
python -m string_technique_model assumptions activate ASSUMPTION_ID
python -m string_technique_model assumptions deactivate ASSUMPTION_ID
python -m string_technique_model assumptions applicable --instrument vln --technique sul_ponticello
python -m string_technique_model assumptions audit
```

## Current registry contents

The registry ships with **no active numerical examples**. Commented template entries document the required schema (value, unit, operation, spaces, links, uncertainty, scope, rationale).

See also: `reports/assumption_audit.md`.
