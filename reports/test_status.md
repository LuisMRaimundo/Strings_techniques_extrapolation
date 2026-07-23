# Test status

**Date:** 2026-07-23  
**Focus:** Archive identity validation + primary-source ingestion (incl. Meyer / Fletcher–Rossing / Rossing 2010)

## Latest focused run

```text
tests/test_source_identity_validation.py
tests/test_primary_source_ingestion.py
tests/test_prediction_modes_and_assumptions_cli.py
tests/test_multiphonics_measurement_recognition.py
tests/test_user_assumptions_and_from_ordinary.py
→ 35 passed
```

## Full suite

`253 passed, 8 warnings` after fixing `test_12_source_verification_required` for Meyer’s upgrade to `verified_local_source`.

## Scientific gate

- Active EWSD density parameters: **0**
- User assumptions: inactive by default; dual activation gate enforced
