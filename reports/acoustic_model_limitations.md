# Acoustic model limitations (stress-test view)

Generated: 2026-07-23T17:54:15.190369+00:00

- EWSD is precomputed $\Phi(D)=D$; not recomputed from audio.
- Active literature density parameters: **0**.
- Implemented acoustic descriptors: `DESC_SPECTRAL_CENTROID`, `DESC_SPECTRAL_SLOPE`, `DESC_HNR`, `DESC_SPECTRAL_FLUX`, `DESC_FRAME_SPECTRAL_VARIANCE`, `DESC_LTAS`, `DESC_PARTIAL_SALIENCE`, `DESC_PITCH_COMPONENT_COUNT`, `DESC_ABSOLUTE_ATTENUATION`.
- Unsupported descriptors (scope safeguard only): `DESC_TEMPORAL_MODULATION`, `DESC_ATTACK_TIME`, `DESC_LOUDNESS`, `DESC_FUNDAMENTAL_SALIENCE`, `DESC_UPPER_PARTIAL_ENERGY_RATIO`, `DESC_BRIDGE_MOBILITY`, `DESC_INTER_PLAYER_VARIABILITY`.
- Harmonic sounding frequency $f_n=n f_0$: first-principles oracle; not a ProductionInstruction auto-fill.
- Schelleng boundary: **not implemented**.
- Mute attenuation $= f(\mathrm{mass})$: **refused**.
- Cross-domain centroid equivalence: **refused** (`not_comparable`).
- Secondary synthesis must not activate EWSD.
- Real-audio validation: **absent** (no local verified audio; no ecological-validity claim).
