# PDF integration audit

**Source:** *State of the Art on String Timbral and Articulatory Techniques: Harmonics, Sul Tasto, Sul Ponticello, and Con Sordino* (20 pages; local synthesis; author/year not stated in PDF).  
**Registered as:** `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`  
**Local file:** `literature/corpus/reports/string_timbral_articulatory_state_of_art.pdf`  
**Audit date:** 2026-07-23

## 1. Concepts already represented

| PDF concept | Current representation | Notes |
|---|---|---|
| Four legacy technique labels | `artificial_harmonic`, `sul_tasto`, `sul_ponticello`, `con_sordino` | Flat mutually exclusive `technique` field |
| Artificial harmonics metadata | order, stopped/touched pitches, interval optional | Order set `[2,3,4,5]`; sixth partial missing |
| Natural vs artificial distinction (flag) | `distinguish_natural_vs_artificial` | Natural not a first-class left-hand regime |
| Flautando ≠ sul tasto | `equate_flautando: false`; mapping forbids auto-map | Good; flautando still not a typed execution target |
| Mute type required for con sordino | `require_mute_type` | Types under-specified vs PDF taxonomy |
| No universal density multipliers | parameters inactive; prohibited ratios present | Scientifically correct stance |
| Qualitative Meyer package | extracts + mechanisms | Separate secondary synthesis now required |
| Instrument domain vln/vla/vlc/cb | hard-coded | Matches PDF scope |
| Evidence activation gate | literature + prediction layers | Duplicated applicability logic |

## 2. Concepts represented incompletely

- Bow contact as verbal categories (poco/molto) without continuum vs measured β.
- Ambiguous `bow_position_ratio` (numerator/denominator undocumented).
- Mute mass as free string/float without unit normalization.
- Standard vs heavy practice mute distinguished in prose config but not as controlled enum.
- Harmonic glissandi, half harmonics, multiphonics absent as regimes.
- On-bridge and afterlength/behind-bridge collapsed into sul ponticello continuum if used.
- Combinations (e.g. muted sul-ponticello harmonic) not representable without losing components.
- Perceptual/textural functions mixed into technique/effect language.
- Acoustic descriptors conflatable with EWSD via informal mapping statuses.
- Ensemble / inter-player dispersion metadata sparse.
- Spectrum-aware backend advertised while `transform_spectrum` raises `NotImplementedError`.

## 3. Structurally impossible in prior schema

- Non-exclusive combination of left-hand regime + bow contact + mute + articulation.
- Separate excitation regions (speaking string / on bridge / afterlength).
- Four analytical levels as typed objects.
- Configurable ontology beyond fixed 4×4 = 16 models.
- β computed from measured lengths with contradiction checks.
- Descriptor registry independent of EWSD metric registry.
- Qualitative constraint engine that cannot emit EWSD numbers.

## 4. Claims usable only as qualitative constraints

From the PDF (secondary synthesis): non-invariant timbre; multidimensional T(β, force, velocity, …); sul tasto conditional upper-partial/centroid/attack/diffuseness tendencies; sul ponticello multiple-slip and spectral variance; mute as bridge-mass/mobility filter; harmonics as modal reorganization; textural functions require grouping context; combinations nonlinear.

## 5. Numerical statements requiring primary verification

| Claim (as reported in PDF) | Status |
|---|---|
| Violin mute ~5–13 dB mean bridge-mobility reduction ~1–2.5 kHz (Elie et al.) | `secondary_synthesis_requires_primary_verification`; inactive for EWSD |
| Heavy violin mute classification threshold ≈ 35 g (Evangelista & Freire 2025) | same |
| Any implied density ratio vs ordinary | prohibited / not implemented |

## 6. Compatibility risks

- Replacing `technique` as sole authority breaks flat CSV importers unless migration retained.
- Changing evidence-matrix cardinality from 16 breaks Phase-3 tests unless legacy matrix retained and labeled.
- Expanding `allowed_orders` to include 6 changes validation for artificial harmonics.
- Deprecating `bow_position_ratio` without migration field breaks GUI/manual entry.
- Silent renames of mute categories would invalidate existing records.

## 7. Scientifically / mathematically unsafe code paths

1. **`prediction/operations.py`:** additive density difference incorrectly applied in η-space for all links; multiplicative ratio assumes log-compatible η.
2. **Hard-coded `transfer_sd = 0.1`** in `prediction/pipeline.py` without config/provenance.
3. **Spectrum-aware capability advertising** without numerical transform.
4. **Duplicated applicability** with declared-but-unevaluated fields (bow β, frequency in prediction path).
5. **Example `touched_interval: P5`** in prediction request template inconsistent with fourth-partial convention.
6. **Parquet failures swallowed** in prediction outputs → opaque empty paths.
7. **README** claims predictions unimplemented while Phase-4 exists.

## 8. Implementation decisions (this update)

- Introduce versioned `ProductionInstruction` as authoritative combined state; keep `technique` as legacy compatibility label.
- Configurable ontology YAML; retain explicitly labeled legacy 4×4 evidence matrix.
- Acoustic-descriptor registry + qualitative constraint engine; no active EWSD coefficients from the PDF.
- Unify applicability resolver; correct operation/link spaces; config-driven transfer uncertainty; honest capability states; parquet preflight.
