# Literature alignment matrix

Generated: 2026-07-23T17:54:15.271370+00:00

Benchmark source validation ok: **True**

| test ID | source | DOI | domain | claim type | expected | result | scope |
|---------|--------|-----|--------|------------|----------|--------|-------|
| BM_SCHOONDERWALDT_BETA_DEFINITION | SRC_SCHOONDERWALDT_2009 | 10.3813/AAA.918221 | string_velocity_at_bow | exact | {'relation': 'beta_equals_distance_over_speaking_length'} | not_run_in_matrix_writer | within |
| BM_SCHOONDERWALDT_DOMAIN_NONEQUIV | SRC_SCHOONDERWALDT_2009 | 10.3813/AAA.918221 | string_velocity_at_bow | non_equivalence | {'relation': 'centroids_not_automatically_equivalent_across_ | not_run_in_matrix_writer | scope/qualitative |
| BM_SCHOONDERWALDT_STDREG_NOT_PORTABLE | SRC_SCHOONDERWALDT_2009 | 10.3813/AAA.918221 | string_velocity_at_bow | unsupported_for_numerical_test | {'relation': 'standardized_regression_coefficients_are_relat | not_run_in_matrix_writer | scope/qualitative |
| BM_EVANGELISTA_MUTE_CATEGORIES | SRC_EVANGELISTA_FREIRE_2025 | 10.1051/aacus/2025029 | radiated_audio | categorical_distinction | {'relation': 'mute_categories_remain_distinct; mass_alone_in | not_run_in_matrix_writer | scope/qualitative |
| BM_EVANGELISTA_NO_MASS_ATTENUATION_LAW | SRC_EVANGELISTA_FREIRE_2025 | 10.1051/aacus/2025029 | radiated_audio | unsupported_for_numerical_test | {'relation': 'no_universal_attenuation_equals_f_mass'} | not_run_in_matrix_writer | scope/qualitative |
| BM_FALLOWFIELD_MULTIPHONIC_DISTINCT | SRC_FALLOWFIELD_TEMPO_MULTIPHONICS | 10.1017/S0040298219000974 | unresolved | categorical_distinction | {'relation': 'multiphonic_distinct_from_single_harmonic_and_ | not_run_in_matrix_writer | scope/qualitative |
| BM_LOSTANLEN_RECOGNITION_NOT_EWSD | SRC_LOSTANLEN_ANDEN_LAGRANGE_2018 | 10.1145/3273024.3273036 | radiated_audio | unsupported_for_numerical_test | {'relation': 'recognition_confidence_is_not_ewsd'} | not_run_in_matrix_writer | scope/qualitative |
| BM_STOWELL_TERMINOLOGY_ONLY | SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE | 10.1017/CCOL9780521390330.008 | unresolved | applicability_only | {'relation': 'historical_terminology_not_numerical_acoustics | not_run_in_matrix_writer | scope/qualitative |
| BM_SOA_SECONDARY_NO_EWSD_ACTIVATION | SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART | — | unresolved | unsupported_for_numerical_test | {'relation': 'secondary_synthesis_must_not_activate_ewsd'} | not_run_in_matrix_writer | scope/qualitative |
| BM_PHYSICS_ORACLE_HARMONIC_P4 | first_principles_analytical_identity | — | unresolved | exact | {'relation': 'f_n = n * f_0', 'f_n_hz': 880, 'production_api | aligned | within |

## Warnings

_None._
