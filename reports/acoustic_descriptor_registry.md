# Acoustic descriptor registry

**Config:** `configs/acoustic_descriptors.yaml` (`0.3.0-pdf-soa-descriptors`)

Registry is separate from EWSD metric definitions. Every descriptor currently reports `implemented: false` and `formula_status: unresolved_in_this_repository`.

Included IDs: spectral centroid, spectral slope, HNR, spectral flux, temporal modulation, attack time, loudness, fundamental salience, upper-partial energy ratio, partial salience, pitch-component count, frame-level spectral variance, absolute attenuation, bridge mobility, inter-player variability.

**EWSD compatibility:** incompatible unless an explicit activated mapping exists. No descriptor formula is claimed as implemented.
