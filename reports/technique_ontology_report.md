# Technique ontology report

**Config:** `configs/technique_ontology.yaml` (`0.3.0-pdf-soa-ontology`)  
**Schema:** `production_instruction_v1`

## Domain

- Instruments: vln, vla, vlc, cb
- Left-hand regimes: ordinary_stopped, natural/artificial/half harmonic, multiphonic, harmonic glissandi
- Bow-contact categories: molto/poco sul tasto ↔ ordinario ↔ poco/molto sul ponticello (verbal only; no β thresholds)
- Excitation regions outside continuum: directly_on_bridge, afterlength_behind_bridge
- Timbre targets: flautando distinct from sul tasto
- Mute categories: standard performance, heavy practice/hotel, historical metal/wood, adjustable/partial, other, none, unresolved

## Artificial-harmonic relations (PDF)

| Interval | Order | Practicality |
|---|---|---|
| P4 | 4 | standard |
| M3 | 5 | specialized |
| m3 | 6 | specialized |
| P5 | 3 | specialized |

Inference disabled by default.

## Legacy compatibility

Labeled matrix `legacy_four_by_four_specialised_techniques` with expected cell count 16 remains for evidence-matrix and model-registry compatibility. It is not the scientific authority for combined production states.

## β documentation

`relative_bow_bridge_distance_beta = bow_bridge_distance_m / speaking_length_m`  
Larger β → farther from the bridge. Deprecated alias: `bow_position_ratio`.
