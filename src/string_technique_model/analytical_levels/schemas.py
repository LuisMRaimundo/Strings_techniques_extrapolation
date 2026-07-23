"""Analytical-level schemas — acoustic, perceptual, and textural layers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PerceptualOrganizationCategory = Literal[
    "fusion",
    "segregation",
    "streaming",
    "stratification",
    "source_identification_ambiguity",
    "salience",
    "insufficient_context",
]

TexturalFunctionCategory = Literal[
    "foreground_background",
    "layer_differentiation",
    "transformation",
    "continuity",
    "formal_segmentation",
    "accumulation",
    "dissolution",
    "surface_texture_formation",
    "timbral_augmentation",
    "insufficient_context",
]

GROUPING_CONTEXT_FIELDS = (
    "onset_synchrony",
    "register",
    "rhythm",
    "dynamics",
    "spatial_placement",
    "voice_leading",
    "ensemble_size",
    "comparison_layer",
)

MIN_GROUPING_CONTEXT_FIELDS = 3


class AcousticDescriptorObservation(BaseModel):
    """Low-level acoustic measurement — not a textural function assessment."""

    model_config = ConfigDict(extra="forbid")

    descriptor_id: str
    value: float | list[float] | None = None
    units: str | None = None
    analysis_params: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class PerceptualOrganizationAssessment(BaseModel):
    """Mid-level perceptual grouping assessment."""

    model_config = ConfigDict(extra="forbid")

    organization: PerceptualOrganizationCategory
    required_context_fields: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class TexturalFunctionAssessment(BaseModel):
    """High-level textural function — requires grouping context, not technique label alone."""

    model_config = ConfigDict(extra="forbid")

    function: TexturalFunctionCategory | None = None
    conditional_candidates: list[str] = Field(default_factory=list)
    required_context_fields: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    technique_label: str | None = None


def _present_grouping_fields(grouping_context: dict[str, Any] | None) -> list[str]:
    if not grouping_context:
        return []
    return [
        field
        for field in GROUPING_CONTEXT_FIELDS
        if grouping_context.get(field) is not None
        and str(grouping_context.get(field)).strip() not in {"", "null", "None"}
    ]


def infer_textural_function(
    technique_label: str,
    grouping_context: dict[str, Any] | None = None,
) -> TexturalFunctionAssessment:
    """
    Infer textural function only when sufficient grouping context is present.

    Never assigns a categorical function from the technique label alone.
    """
    present = _present_grouping_fields(grouping_context)
    missing = [f for f in GROUPING_CONTEXT_FIELDS if f not in present]

    if len(present) < MIN_GROUPING_CONTEXT_FIELDS:
        return TexturalFunctionAssessment(
            function="insufficient_context",
            conditional_candidates=[],
            required_context_fields=missing,
            evidence=[
                f"Only {len(present)}/{len(GROUPING_CONTEXT_FIELDS)} grouping fields present; "
                "categorical textural function cannot be inferred from technique label alone."
            ],
            technique_label=technique_label,
        )

    candidates = [
        "layer_differentiation",
        "surface_texture_formation",
        "timbral_augmentation",
        "transformation",
    ]
    return TexturalFunctionAssessment(
        function=None,
        conditional_candidates=candidates,
        required_context_fields=missing,
        evidence=[
            "Partial grouping context available; returning conditional candidates only "
            "(no categorical prediction from technique label alone)."
        ],
        technique_label=technique_label,
    )


def assert_level_separation(observation: Any, *, as_level: str | None = None) -> None:
    """Raise if analytical levels are mixed or an acoustic observation is mis-stored."""
    if as_level == "textural_function" and isinstance(observation, AcousticDescriptorObservation):
        raise TypeError(
            "Acoustic descriptor observation cannot be stored as a textural function; "
            "analytical levels must remain separated."
        )
    if isinstance(observation, AcousticDescriptorObservation):
        return
    if isinstance(observation, TexturalFunctionAssessment):
        raise TypeError(
            "Acoustic descriptor observation cannot be stored as TexturalFunctionAssessment; "
            "analytical levels must remain separated."
        )
    if isinstance(observation, dict):
        if "descriptor_id" in observation and "function" in observation:
            raise TypeError(
                "Object mixes acoustic descriptor_id with textural function fields."
            )
        if "descriptor_id" in observation:
            return
        if "function" in observation or "conditional_candidates" in observation:
            raise TypeError(
                "Textural function assessment cannot substitute for acoustic descriptor observation."
            )
