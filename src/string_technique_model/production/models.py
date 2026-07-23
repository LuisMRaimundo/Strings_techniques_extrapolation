"""Pydantic models for compositional production instructions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LeftHandRegime = Literal[
    "ordinary_stopped",
    "natural_harmonic",
    "artificial_harmonic",
    "half_harmonic",
    "multiphonic",
    "natural_harmonic_glissando",
    "artificial_harmonic_glissando",
]

BowContactCategory = Literal[
    "molto_sul_tasto",
    "sul_tasto",
    "poco_sul_tasto",
    "ordinario",
    "poco_sul_ponticello",
    "sul_ponticello",
    "molto_sul_ponticello",
]

ExcitationRegion = Literal[
    "speaking_string",
    "directly_on_bridge",
    "afterlength_behind_bridge",
]

TimbreExecutionTarget = Literal[
    "flautando",
    "ordinary_colour",
    "unresolved",
]

MuteCategory = Literal[
    # Legacy canonical labels (retained for backward compatibility)
    "standard_performance_orchestral",
    "heavy_practice_hotel",
    "historical_metal",
    "historical_or_modern_wood",
    # Additive aliases aligned with primary-source mute taxonomy (Evangelista 2025)
    "performance_mute",
    "light_practice",
    "heavy_practice",
    "historical",
    "adjustable_partial",
    "other_explicitly_described",
    "none",
    "unresolved",
]

NotationRepresents = Literal[
    "touched_pitch",
    "sounding_pitch",
    "both",
    "unresolved",
]

DoubleBassPitchConvention = Literal[
    "written_transposed",
    "sounding",
    "unresolved",
]

MotionRegime = Literal[
    "stable_helmholtz",
    "unstable_multiple_slip",
    "unresolved",
]

HarmonicType = Literal["natural", "artificial", "half", "multiphonic"]

MuteState = Literal["on", "off", "unresolved"]


class HarmonicInstruction(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    left_hand_regime: LeftHandRegime
    harmonic_type: HarmonicType | None = None
    touched_node: str | None = None
    stopped_pitch_name: str | None = None
    stopped_pitch_midi: float | None = None
    touched_pitch_name: str | None = None
    touched_pitch_midi: float | None = None
    sounding_pitch_name: str | None = None
    sounding_pitch_midi: float | None = None
    harmonic_order: int | None = None
    touched_interval: str | None = None
    string_name: str | None = None
    notation_represents: NotationRepresents | None = None
    string_specified: bool | None = None
    double_bass_pitch_convention: DoubleBassPitchConvention | None = None
    glissando_type: str | None = None
    finger_position_ratio: float | None = None
    bow_position_ratio_multiphonic: float | None = None
    rational_relationship_id: str | None = None
    expected_pitch_components: list[str] | None = None
    mutation_point: str | None = None
    stability_region: str | None = None
    half_harmonic_definition: str | None = None
    allow_order_inference: bool = False


class BowContactInstruction(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    category: BowContactCategory | None = None
    relative_bow_bridge_distance_beta: float | None = None
    bow_bridge_distance_m: float | None = None
    speaking_length_m: float | None = None
    excitation_region: ExcitationRegion | None = None
    motion_regime: MotionRegime | None = None
    bow_position_ratio_deprecated: float | None = None
    beta_provenance: dict[str, Any] | None = None


class MuteInstruction(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    state: MuteState | None = None
    category: MuteCategory | None = None
    material: str | None = None
    mute_mass_g: float | None = None
    mass_raw: str | None = None
    geometry: str | None = None
    bridge_contact_area: str | None = None
    placement: str | None = None
    adjustable_setting: str | None = None
    device_model_id: str | None = None
    remains_mounted_on_strings: bool | None = None
    application_removal_handling_time_s: float | None = None


class BowingConditions(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    force_n: float | None = None
    velocity_m_s: float | None = None
    articulation: str | None = None
    hair_inclination: str | None = None
    contact_area_descriptor: str | None = None
    dynamic: str | None = None


class PerformanceContext(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True, populate_by_name=True)

    instrument: str | None = None
    pitch_name_written: str | None = None
    pitch_midi_written: float | None = None
    pitch_name_sounding: str | None = None
    pitch_midi_sounding: float | None = None
    string_name: str | None = None
    fundamental_frequency_hz: float | None = None
    performance_register: str | None = Field(default=None, alias="register")
    performer_id: str | None = None
    instrument_id: str | None = None
    instrument_setup: str | None = None
    string_model: str | None = None
    string_scale_m: float | None = None
    bow_rosin_metadata: dict[str, Any] | None = None
    room: str | None = None
    microphone: str | None = None
    microphone_position: str | None = None
    recording_geometry: str | None = None
    ensemble_or_section_size: int | None = None
    player_index: int | None = None
    take_index: int | None = None
    repeated_measure_design: str | None = None
    inter_player_variance: str | None = None
    within_player_variance: str | None = None


class MultiphonicInstruction(BaseModel):
    """
    Compositional/performance specification for bowed-string multiphonics.

    Multiphonics are a single bowed excitation yielding two or more perceptually distinct
    pitch components. They are NOT equivalent to natural harmonics, artificial harmonics,
    half harmonics, double stops, or harmonic glissandi (natural or artificial).
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    instrument: str | None = None
    string: str | None = None
    touching_position_ratio: float | None = None
    equivalent_touching_position_ratio: float | None = None
    bow_position_ratio: float | None = None
    relative_bow_bridge_distance_beta: float | None = None
    principal_harmonic_components: list[str] | None = None
    observed_partials: list[str] | None = None
    expected_pitch_components: list[str] | None = None
    chain_identifier: str | None = None
    mutation_relationship: str | None = None
    excitation_type: str | None = None
    bow_contact_category: BowContactCategory | None = None
    dynamic: str | None = None
    establishment_time_s: float | None = None
    stability: str | None = None
    performer_dependency: str | None = None
    instrument_dependency: str | None = None
    source_reference: str | None = None


class ProductionInstruction(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    schema_version: str = "production_instruction_v1"
    legacy_technique_label: str | None = None
    left_hand: HarmonicInstruction | None = None
    bow_contact: BowContactInstruction = Field(default_factory=BowContactInstruction)
    mute: MuteInstruction = Field(default_factory=MuteInstruction)
    bowing: BowingConditions = Field(default_factory=BowingConditions)
    timbre_execution_target: TimbreExecutionTarget | None = None
    performance_context: PerformanceContext = Field(default_factory=PerformanceContext)
    provenance: dict[str, Any] = Field(default_factory=dict)
    missingness: dict[str, Any] = Field(default_factory=dict)
    migration_warnings: list[str] = Field(default_factory=list)
