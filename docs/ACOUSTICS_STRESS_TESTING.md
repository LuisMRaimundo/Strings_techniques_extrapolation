# Acoustics stress testing

Dedicated guide for the scientific stress-testing package.

## Purpose

Determine whether implemented acoustic calculations behave correctly, remain physically plausible under extreme inputs, stay reproducible, and refuse unsupported extrapolation beyond the verified bibliography.

## Architecture

| Component | Path |
|-----------|------|
| Descriptor backend | `src/string_technique_model/descriptors/` |
| Analysis profiles | `configs/analysis_profiles/` |
| Generators | `src/string_technique_model/testing/signal_generators.py` |
| Oracles | `src/string_technique_model/testing/literature_oracles.py` |
| Benchmarks A–J | `src/string_technique_model/testing/reference_cases.py` |
| Metamorphic helpers | `src/string_technique_model/testing/metamorphic_checks.py` |
| Tolerances | `configs/stress_tolerances.yaml` |
| Literature cases | `configs/literature_benchmark_cases.yaml` |
| Suite config | `configs/acoustics_stress_tests.yaml` |
| Pytest suite | `tests/acoustics_stress/` |
| Runner | `python -m string_technique_model.testing.stress_runner` |

## How to run

```bash
# Fast tier (default CI)
python -m string_technique_model stress-test acoustics --tier fast

# Full acoustics stress
pytest tests/acoustics_stress -q
python -m string_technique_model stress-test acoustics --tier all
```

## Report categories (separate totals)

| Total | Meaning |
|-------|---------|
| scope-safeguard tests | Unsupported descriptors / refused extrapolations |
| numerical descriptor tests | `mathematical_exact` + `metamorphic` |
| literature-alignment tests | `literature_bounded` |
| real-audio tests | Local verified audio (currently **absent**) |

Scope wording: **descriptor unavailable — scope safeguard passed**.  
These are **not** numerical acoustic validation.

## Markers

See `pyproject.toml` `[tool.pytest.ini_options].markers` — including `acoustics_stress`, `mathematical_exact`, `literature_bounded`, `measurement_domain`, `assumption_isolation`, `unsupported_extrapolation`, `benchmark`, `slow`.

## Interpreting failures

| Classification | Meaning |
|----------------|---------|
| aligned | Matches implemented exact relation or verified categorical claim |
| aligned_within_tolerance | Within FFT/window-derived tolerance |
| qualitatively_aligned | Directional/rank claim only |
| not_comparable | Domain/setup mismatch — not a silent numerical failure |
| outside_source_scope | Extrapolation beyond paper |
| source_data_insufficient | Paper lacks portable numeric / unresolved analysis settings |
| contradicted | Genuine disagreement under comparable conditions |

## Synthetic signal limitations

Fixtures are **numerical only**. They are not perceptually equivalent to bowed-string recordings.

## Real-audio validation

**Absent** in the local repository. Do not download corpora without explicit instruction. Optional dataset adapters only.

## EWSD

When no validated mapping exists, numerical technique EWSD remains **NA**. Descriptors must not be relabelled as EWSD.
