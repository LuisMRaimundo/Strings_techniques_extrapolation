# Source identity validation

Internal title/author/year/DOI/ISBN and page count take precedence over filenames.
File presence does not activate EWSD parameters.

**Registry version:** 0.4.0-archive-identity

## Summary

- Verified identity: 8
- Partial identity match: 1
- Duplicate file: 1
- Rejected (identity mismatch): 3
- Insufficient metadata: 1
- Hash-duplicate groups: 1

## Entries

### ID_BERIO_CLAIMED

- Archive filename claim: `Berio_(1976)_Sequenza VIII for violin.pdf`
- Deposited path: `None`
- SHA-256: `1c803b7fa767ddc96965c732dac6c5b0d6809178bce6e7b488f18f109232c3eb`
- Pages: 3
- Internal title: Review of Sequenza XI for guitar (Notes)
- Internal authors: ['McKenzie']
- Internal year: 1991
- Internal DOI: None
- Internal ISBN: None
- Publisher: Notes
- Expected citation (claim): Berio Sequenza VIII for violin (1976) — filename claim
- Identity match: False
- Validation status: `rejected_file_identity_mismatch`
- Rejection reason: Internal document is a short review of Sequenza XI for guitar, not Sequenza VIII for violin.
- Duplicate of: None
- Associated source ID: `None`
- Ingest decision: reject

### ID_EVANGELISTA_FREIRE_2025

- Archive filename claim: `Evangelista_(2025)_Audio analysis of the effects of heavy violin practice mutes Spectral and loudness changes.pdf`
- Deposited path: `literature/corpus/articles/evangelista_freire_2025_heavy_violin_practice_mutes.pdf`
- SHA-256: `354091dc9296e39ed870a7d52e2b9054527a75dccc45ec6682a01928ab941a58`
- Pages: 7
- Internal title: Audio analysis of the effects of heavy violin practice mutes: Spectral and loudness changes
- Internal authors: ['Evangelista, Gianpaolo', 'Freire, Sérgio']
- Internal year: 2025
- Internal DOI: 10.1051/aacus/2025029
- Internal ISBN: None
- Publisher: Acta Acustica
- Expected citation (claim): Evangelista, G., & Freire, S. (2025). Audio analysis of the effects of heavy violin practice mutes… Acta Acustica.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_EVANGELISTA_FREIRE_2025`
- Ingest decision: deposit_and_register

### ID_FALLOWFIELD_2009_CLAIMED

- Archive filename claim: `Fallowfield_(2009)_Cello map A handbook of cello technique for performers and composers.pdf`
- Deposited path: `None`
- SHA-256: `47fd44cd265ffd570fb5ba6e75839f6d8928150d86c10ef76c9dea515fa0a5f5`
- Pages: 19
- Internal title: Cello Multiphonics: Technical and Musical Parameters
- Internal authors: ['Fallowfield, Ellen']
- Internal year: None
- Internal DOI: None
- Internal ISBN: None
- Publisher: TEMPO
- Expected citation (claim): Fallowfield 2009 Cello Map handbook (filename claim)
- Identity match: False
- Validation status: `duplicate_file`
- Rejection reason: Byte-identical to Fallowfield TEMPO multiphonics article; not the 2009 handbook.
- Duplicate of: ID_FALLOWFIELD_2020_TEMPO
- Associated source ID: `None`
- Ingest decision: reject_duplicate

### ID_FALLOWFIELD_2020_TEMPO

- Archive filename claim: `Fallowfield_(2020)_Cello multiphonics Technical and musical parameters.pdf`
- Deposited path: `literature/corpus/articles/fallowfield_2020_cello_multiphonics_tempo.pdf`
- SHA-256: `47fd44cd265ffd570fb5ba6e75839f6d8928150d86c10ef76c9dea515fa0a5f5`
- Pages: 19
- Internal title: Cello Multiphonics: Technical and Musical Parameters
- Internal authors: ['Fallowfield, Ellen']
- Internal year: 2019
- Internal DOI: 10.1017/S0040298219000974
- Internal ISBN: None
- Publisher: TEMPO / Cambridge University Press
- Expected citation (claim): Fallowfield, E. (2019). Cello multiphonics… TEMPO 74(291), 51–69.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_FALLOWFIELD_TEMPO_MULTIPHONICS`
- Ingest decision: deposit_and_register

_Notes:_ Footer recovers TEMPO 74 (291) 51–69 © 2019. Filename '2020' is a download-date style claim; not the 2009 Cello Map handbook.


### ID_FLETCHER_ROSSING_PHYSICS

- Archive filename claim: `The_Physics_of_Musical_Instruments.pdf`
- Deposited path: `literature/corpus/books/fletcher_rossing_1991_physics_of_musical_instruments.pdf`
- SHA-256: `b784c3251102bead11f39a30a506441eb8833bd00c4e4b3628c22d60d9833675`
- Pages: 628
- Internal title: The Physics of Musical Instruments
- Internal authors: ['Fletcher, Neville H.', 'Rossing, Thomas D.']
- Internal year: 1991
- Internal DOI: 10.1007/978-1-4612-2980-3
- Internal ISBN: 978-0-387-94151-6
- Publisher: Springer-Verlag New York Inc.
- Expected citation (claim): Fletcher, N. H., & Rossing, T. D. The Physics of Musical Instruments. Springer-Verlag, 1991.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_FLETCHER_ROSSING_1991`
- Ingest decision: deposit_and_register

_Notes:_ Copyright © 1991; LoC cataloguing year 1993 on title verso. Part III covers string instruments including Chapter 10 Bowed String Instruments. Generic bowed-string physics — not portable EWSD technique coefficients.


### ID_HANN_CLAIMED

- Archive filename claim: `Hann_(2015)_The influence of historic violin treatises on modern teaching and performance practices.pdf`
- Deposited path: `None`
- SHA-256: `3dd7babc9030901105bb8e261168bdaef15d97db1a30e664329a6d6137087a6e`
- Pages: None
- Internal title: Fashion / luxury brand paper (Yoosun Hann)
- Internal authors: ['Hann, Yoosun']
- Internal year: 2011
- Internal DOI: None
- Internal ISBN: None
- Publisher: None
- Expected citation (claim): Hann 2015 violin treatises (filename claim)
- Identity match: False
- Validation status: `rejected_file_identity_mismatch`
- Rejection reason: Unrelated fashion/luxury brand paper; not a violin-treatise study.
- Duplicate of: None
- Associated source ID: `None`
- Ingest decision: reject

### ID_LOSTANLEN_2018

- Archive filename claim: `Lostanlen_(2018)_Extended playing techniques The next milestone in musical instrument recognition.pdf`
- Deposited path: `literature/corpus/articles/lostanlen_anden_lagrange_2018_extended_playing_techniques.pdf`
- SHA-256: `88e3d9d60e2181750e747f38bd8291e3e257967bfded947fc1046c3d1a5ea9a6`
- Pages: 10
- Internal title: Extended playing techniques: The next milestone in musical instrument recognition
- Internal authors: ['Lostanlen, Vincent', 'Andén, Joakim', 'Lagrange, Mathieu']
- Internal year: 2018
- Internal DOI: 10.1145/3273024.3273036
- Internal ISBN: None
- Publisher: ACM / DLfM
- Expected citation (claim): Lostanlen et al. (2018). Extended playing techniques… DLfM 2018. ACM 10.1145/3273024.3273036
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_LOSTANLEN_ANDEN_LAGRANGE_2018`
- Ingest decision: deposit_and_register_recognition_only

### ID_MESSINA_CLAIMED

- Archive filename claim: `Messina_(2009)_A guide to extended techniques for the violoncello.pdf`
- Deposited path: `None`
- SHA-256: `4185e739a8e5707d74bcb878edf5d8a4d170d1dc26d10b5890344c7f596a0fff`
- Pages: 1
- Internal title: None
- Internal authors: None
- Internal year: None
- Internal DOI: None
- Internal ISBN: None
- Publisher: None
- Expected citation (claim): Messina 2009 cello extended techniques (filename claim)
- Identity match: False
- Validation status: `insufficient_metadata`
- Rejection reason: One-page image PDF; no recoverable internal text/metadata for identity verification.
- Duplicate of: None
- Associated source ID: `None`
- Ingest decision: reject

### ID_MEYER_2009

- Archive filename claim: `IMP_Acoustics and the Performance of music_(Jürgen Meyer) (z-lib.org).pdf`
- Deposited path: `literature/corpus/books/meyer_2009_acoustics_and_the_performance_of_music.pdf`
- SHA-256: `4e58860f92b357de28856768d1eef67222bd06cc5b092afdcd2f436009867b70`
- Pages: 446
- Internal title: Acoustics and the Performance of Music
- Internal authors: ['Meyer, Jürgen']
- Internal year: 2009
- Internal DOI: None
- Internal ISBN: 978-0-387-09516-5
- Publisher: Springer Science+Business Media, LLC
- Expected citation (claim): Meyer, J. Acoustics and the Performance of Music (English 5th ed. translation). Springer, 2009.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `MEYER_ACOUSTICS`
- Ingest decision: deposit_and_register

_Notes:_ Filename claim matches internal identity. Copyright 2009 Springer; LoC 2008944095. String-instrument directional characteristics and seating/tonal chapters present. Does not by itself activate EWSD coefficients.


### ID_RIMSKY_CLAIMED

- Archive filename claim: `Rimsky-Korsakov_(1922)_Principles of orchestration.pdf`
- Deposited path: `None`
- SHA-256: `b7b4303127983aad5274891680631c054a7e8a030b30158c17beb6caf7d416a6`
- Pages: 3
- Internal title: JSTOR review of Principles of Orchestration
- Internal authors: None
- Internal year: None
- Internal DOI: None
- Internal ISBN: None
- Publisher: JSTOR review excerpt
- Expected citation (claim): Rimsky-Korsakov Principles of Orchestration (1922 treatise) — filename claim
- Identity match: False
- Validation status: `rejected_file_identity_mismatch`
- Rejection reason: Short JSTOR review, not the complete treatise.
- Duplicate of: None
- Associated source ID: `None`
- Ingest decision: reject

### ID_ROSSING_SCIENCE_STRINGS_2010

- Archive filename claim: `Thomas D. Rossing_The Science of String Instruments.pdf`
- Deposited path: `literature/corpus/books/rossing_2010_science_of_string_instruments.pdf`
- SHA-256: `d40e5018d6d2a917125f0daa586252246ff0d21878800095c347bc149d853084`
- Pages: 466
- Internal title: The Science of String Instruments
- Internal authors: ['Rossing, Thomas D. (editor)']
- Internal year: 2010
- Internal DOI: 10.1007/978-1-4419-7110-4
- Internal ISBN: 978-1-4419-7109-8
- Publisher: Springer Science+Business Media, LLC
- Expected citation (claim): Rossing, T. D. (Ed.). The Science of String Instruments. Springer, 2010.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_ROSSING_SCIENCE_STRING_INSTRUMENTS_2010`
- Ingest decision: deposit_and_register

_Notes:_ Edited volume. Chapters on bowed strings, violin, cello, double bass, and bowing (Guettler). Chapter-level extracts require separate curator validation before any numerical parameter activation.


### ID_SCHOONDERWALDT_2009

- Archive filename claim: `Schoonderwaldt_(2009)_The violinist’s sound palette Spectral centroid, pitch flattening and anomalous low frequencies.pdf`
- Deposited path: `literature/corpus/articles/schoonderwaldt_2009_violinists_sound_palette.pdf`
- SHA-256: `afe670ac94fb8d8da65798e0a55873a39b28cafd38f89edbbedbf45e34b86144`
- Pages: 14
- Internal title: The Violinist's Sound Palette: Spectral Centroid, Pitch Flattening and Anomalous Low Frequencies
- Internal authors: ['Schoonderwaldt, Erwin']
- Internal year: 2009
- Internal DOI: 10.3813/AAA.918221
- Internal ISBN: None
- Publisher: Acta Acustica united with Acustica
- Expected citation (claim): Schoonderwaldt, E. (2009). The violinist’s sound palette… Acta Acustica united with Acustica.
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_SCHOONDERWALDT_2009`
- Ingest decision: deposit_and_register

### ID_SOA_SYNTHESIS

- Archive filename claim: `String Timbral and Articulatory Techniques.pdf`
- Deposited path: `literature/corpus/reports/string_timbral_articulatory_state_of_art.pdf`
- SHA-256: `8adcc93b6ea340e987004b396ce727f0454856c0c25d9b87b2ba403aafa0efb3`
- Pages: 20
- Internal title: State of the Art on String Timbral and Articulatory Techniques: Harmonics, Sul Tasto, Sul Ponticello, and Con Sordino
- Internal authors: None
- Internal year: None
- Internal DOI: None
- Internal ISBN: None
- Publisher: None
- Expected citation (claim): State of the Art on String Timbral and Articulatory Techniques (local synthesis)
- Identity match: True
- Validation status: `verified_identity`
- Rejection reason: None
- Duplicate of: None
- Associated source ID: `SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART`
- Ingest decision: already_registered_secondary_synthesis

_Notes:_ Secondary synthesis; author/year unresolved; not a substitute for primaries.

### ID_STOWELL_CLAIMED_1978

- Archive filename claim: `Stowell_(1978)_Development of violin technique from L’Abbé le fils to Paganini.pdf`
- Deposited path: `literature/corpus/books/stowell_cambridge_companion_technique_performing_practice.pdf`
- SHA-256: `adc5ec9aab4bedebae3d293986bde8d9136e8885a105aecec488284fe96090e0`
- Pages: 21
- Internal title: Technique and performing practice
- Internal authors: ['Stowell, Robin']
- Internal year: 1992
- Internal DOI: 10.1017/CCOL9780521390330.008
- Internal ISBN: None
- Publisher: Cambridge University Press
- Expected citation (claim): Stowell 1978 L’Abbé–Paganini thesis (filename claim)
- Identity match: False
- Validation status: `partial_identity_match`
- Rejection reason: Filename claims 1978 thesis; internal content is Cambridge Companion to the Violin chapter (DOI CCOL9780521390330.008).
- Duplicate of: None
- Associated source ID: `SRC_STOWELL_CAMBRIDGE_TECHNIQUE_PERFORMING_PRACTICE`
- Ingest decision: register_actual_publication_terminology_only
