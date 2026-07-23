"""Tests for multiphonic, measurement-domain, and recognition schemas."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from string_technique_model.config import PACKAGE_ROOT, load_yaml
from string_technique_model.measurement_domains import (
    REQUIRED_DOMAIN_IDS,
    load_measurement_domain_registry,
)
from string_technique_model.production import MultiphonicInstruction, assert_distinct_from_harmonics
from string_technique_model.recognition import TechniqueRecognitionResult


class _MuteTableRowStub(BaseModel):
    model_config = ConfigDict(extra="allow")

    mute_category: str | None = None
    mute_material: str | None = None
    mute_mass_g: float | None = None
    mute_geometry: str | None = None
    bridge_contact_configuration: str | None = None
    mute_model: str | None = None
    loudness_sones: float | None = None
    intensity_reduction_percent: float | None = None
    instrument: str | None = None
    provenance_notes: str | None = None


class _EvangelistaMuteTableDataset(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_id: str
    status: str
    schema_version: str
    source: dict[str, str]
    field_schema: dict[str, str]
    rows: list[_MuteTableRowStub] = Field(default_factory=list)


def test_multiphonic_instruction_schema_validates() -> None:
    inst = MultiphonicInstruction.model_validate(
        {
            "instrument": "vln",
            "string": "G",
            "touching_position_ratio": 0.25,
            "bow_position_ratio": 0.12,
            "relative_bow_bridge_distance_beta": 0.12,
            "expected_pitch_components": ["G4", "D5"],
            "stability": "performer_dependent",
            "source_reference": "fallowfield_2020",
        }
    )
    assert inst.instrument == "vln"
    assert inst.expected_pitch_components == ["G4", "D5"]


@pytest.mark.parametrize(
    "harmonic_kind",
    [
        "natural_harmonic",
        "artificial_harmonic",
        "half_harmonic",
        "natural_harmonic_glissando",
        "artificial_harmonic_glissando",
        "double_stop",
    ],
)
def test_multiphonics_distinct_from_ordinary_harmonic_labels(harmonic_kind: str) -> None:
    with pytest.raises(ValueError, match="ordinary harmonic"):
        assert_distinct_from_harmonics(harmonic_kind)


def test_multiphonics_accepts_multiphonic_label() -> None:
    assert_distinct_from_harmonics("multiphonic")


def test_measurement_domains_load_and_include_required_ids() -> None:
    registry = load_measurement_domain_registry()
    assert REQUIRED_DOMAIN_IDS <= registry.ids()
    radiated = registry.get("radiated_audio")
    assert radiated is not None
    assert "spectral centroid" in radiated.notes.lower()
    bridge = registry.get("bridge_force")
    assert bridge is not None
    bridge_notes = bridge.notes.lower()
    assert (
        "not interchangeable" in bridge_notes
        or "not equivalent" in bridge_notes
        or "do not map" in bridge_notes
    )


def test_technique_recognition_result_does_not_claim_ewsd() -> None:
    result = TechniqueRecognitionResult(
        predicted_technique="sul_ponticello",
        confidence=0.87,
        rank=1,
        candidate_techniques=["sul_ponticello", "ordinario"],
        source_taxonomy_label="sul_pont",
        internal_ontology_mapping="unresolved",
        feature_backend="time_frequency_scattering",
        model_version="stub_v0",
        dataset="studio_on_line_style",
        uncertainty={"entropy": 0.42},
    )
    assert result.claims_ewsd is False
    with pytest.raises(ValidationError, match="EWSD"):
        TechniqueRecognitionResult.model_validate(
            {
                "predicted_technique": "sul_tasto",
                "confidence": 0.5,
                "ewsd_coefficient": 1.2,
            }
        )


def test_mute_dataset_yaml_loads() -> None:
    path = PACKAGE_ROOT / "configs" / "datasets" / "evangelista_freire_2025_mute_table.yaml"
    data = load_yaml(path)
    dataset = _EvangelistaMuteTableDataset.model_validate(data)
    assert dataset.dataset_id == "evangelista_freire_2025_mute_table"
    assert dataset.status == "metadata_stub"
    assert dataset.rows == []
    assert "local_pdf" in dataset.source

    zenodo_path = PACKAGE_ROOT / "configs" / "datasets" / "evangelista_freire_2025_zenodo_external.yaml"
    zenodo = load_yaml(zenodo_path)
    assert zenodo["status"] == "external_unresolved"
