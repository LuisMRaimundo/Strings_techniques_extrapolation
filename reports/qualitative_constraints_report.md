# Qualitative constraints report

**Config:** `configs/qualitative_acoustic_constraints.yaml`  
**Engine:** `string_technique_model.constraints.QualitativeConstraintEngine`

Constraints encode PDF-backed conditional tendencies (increase/decrease/redistribute/destabilize/variable) with required contextual variables and `numerical_prediction_allowed: false`.

Coverage includes sul tasto (upper partials, centroid, attack, bow-noise prominence), sul ponticello (upper partials, fundamental salience at extremes, spectral variance, unstable multiple-slip noise), standard and heavy mutes (mobility/brilliance/loudness; violin mobility numerical status requires primary verification), and harmonics/multiphonics (modal reorganization; no universal density direction).

Requesting density prediction from the engine returns `numerical_prediction_not_allowed`.
