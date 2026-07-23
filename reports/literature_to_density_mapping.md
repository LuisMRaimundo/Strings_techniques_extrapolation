# Literature → density metric mapping

Project metric: EWSD acoustic-balanced scalar (`configs/density_metric.yaml`).

Sound level, centroid, brightness, spectral slope, and harmonic count are **not** automatically treated as density.

| source_variable | mapping_status | notes |
|---|---|---|
| EWSD_score_acoustic_balanced | direct_same_metric | Same scalar family as project Phi when definition IDs match. |
| dynamic_range | indirect_proxy | Dynamic range in dB constrains level, not EWSD density. |
| global_sound_power_change | indirect_proxy | Mute/level dB changes are acoustic level effects, not density multipliers. |
| sound_pressure_level | incompatible_variable | Never treat SPL as density. |
| sound_power_level | incompatible_variable | Never treat SWL as density. |
| frequency_dependent_spectral_redistribution | qualitative_constraint_only | Supported mechanism; no numeric density transfer function in package. |
| upper_partial_attenuation | qualitative_constraint_only | Sul tasto mechanism; numeric TF unavailable. |
| spectral_centroid | indirect_proxy | Centroid ≠ density. |
| harmonic_radiation_offset_vs_violin | indirect_proxy | Relative level comparison only. |
| harmonic_level_lower_bound | indirect_proxy | Level floor constraint only. |
