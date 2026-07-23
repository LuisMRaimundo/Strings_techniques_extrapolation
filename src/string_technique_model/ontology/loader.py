"""Load technique ontology from YAML."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml

ONTOLOGY_PATH = PACKAGE_ROOT / "configs" / "technique_ontology.yaml"


class HarmonicIntervalRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    touched_interval: str
    aliases: list[str] = Field(default_factory=list)
    harmonic_order: int
    practicality: str | None = None


class HarmonicIntervalRelations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_order_inference: bool = False
    relations: list[HarmonicIntervalRelation] = Field(default_factory=list)


class LegacyEvidenceMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    techniques: list[str] = Field(default_factory=list)
    expected_cell_count: int | None = None
    note: str | None = None


class RelativeBowBridgeDistanceBeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str = "relative_bow_bridge_distance_beta"
    numerator: str = "bow_bridge_distance_m"
    denominator: str = "speaking_length_m"
    units: str | None = None
    expected_domain: str | None = None
    larger_means: str | None = None
    deprecated_alias: str | None = None
    contradiction_tolerance_abs: float = 1.0e-6


class OntologyConfig(BaseModel):
    """Versioned technique ontology loaded from configs/technique_ontology.yaml."""

    model_config = ConfigDict(extra="forbid")

    version: str | None = None
    schema_version: str | None = None
    instruments: list[str] = Field(default_factory=list)
    legacy_technique_labels: list[str] = Field(default_factory=list)
    legacy_evidence_matrix: LegacyEvidenceMatrix | None = None
    left_hand_regimes: list[str] = Field(default_factory=list)
    bow_contact_categories: list[str] = Field(default_factory=list)
    bow_contact_beta_thresholds: Any | None = None
    excitation_regions: list[str] = Field(default_factory=list)
    excitation_regions_outside_continuum: list[str] = Field(default_factory=list)
    timbre_execution_targets: list[str] = Field(default_factory=list)
    mute_categories: list[str] = Field(default_factory=list)
    artificial_harmonic_interval_order_relations: HarmonicIntervalRelations | None = None
    harmonic_orders: dict[str, Any] | None = None
    notation_represents: list[str] = Field(default_factory=list)
    double_bass_pitch_conventions: list[str] = Field(default_factory=list)
    instrument_harmonic_applicability: dict[str, Any] = Field(default_factory=dict)
    relative_bow_bridge_distance_beta: RelativeBowBridgeDistanceBeta | None = None
    multidimensional_timbre_relation: dict[str, Any] | None = None

    @property
    def contradiction_tolerance(self) -> float:
        beta = self.relative_bow_bridge_distance_beta
        if beta is None:
            return 1.0e-6
        return beta.contradiction_tolerance_abs


def _build_alias_index(config: OntologyConfig) -> dict[str, str]:
    """Map normalized alias strings to canonical touched_interval codes."""
    index: dict[str, str] = {}
    relations = config.artificial_harmonic_interval_order_relations
    if relations is None:
        return index
    for relation in relations.relations:
        canonical = relation.touched_interval
        index[_normalize_alias(canonical)] = canonical
        for alias in relation.aliases:
            index[_normalize_alias(alias)] = canonical
    return index


def _build_order_index(config: OntologyConfig) -> dict[str, int]:
    index: dict[str, int] = {}
    relations = config.artificial_harmonic_interval_order_relations
    if relations is None:
        return index
    for relation in relations.relations:
        index[relation.touched_interval] = relation.harmonic_order
    return index


def _normalize_alias(value: str) -> str:
    return value.strip()


@lru_cache(maxsize=1)
def load_ontology(path: str | None = None) -> OntologyConfig:
    yaml_path = ONTOLOGY_PATH if path is None else PACKAGE_ROOT / path
    data = load_yaml(yaml_path)
    return OntologyConfig.model_validate(data)


def legacy_matrix_cells(config: OntologyConfig | None = None) -> list[tuple[str, str]]:
    """Return (technique, instrument) pairs for the legacy 4×4 evidence matrix."""
    cfg = config or load_ontology()
    matrix = cfg.legacy_evidence_matrix
    techniques = matrix.techniques if matrix else []
    return [(technique, instrument) for technique in techniques for instrument in cfg.instruments]


def legacy_cell_count(config: OntologyConfig | None = None) -> int:
    cfg = config or load_ontology()
    matrix = cfg.legacy_evidence_matrix
    if matrix is not None and matrix.expected_cell_count is not None:
        return matrix.expected_cell_count
    return len(legacy_matrix_cells(cfg))


def legacy_technique_labels(config: OntologyConfig | None = None) -> list[str]:
    cfg = config or load_ontology()
    return list(cfg.legacy_technique_labels)


def allowed_instruments(config: OntologyConfig | None = None) -> list[str]:
    cfg = config or load_ontology()
    return list(cfg.instruments)


def normalize_touched_interval(interval: str | None, config: OntologyConfig | None = None) -> str | None:
    """Normalize interval aliases (P4/M3/m3/P5) to canonical ontology codes."""
    if interval is None:
        return None
    text = str(interval).strip()
    if not text:
        return None
    cfg = config or load_ontology()
    alias_index = _build_alias_index(cfg)
    return alias_index.get(_normalize_alias(text))


def interval_to_order(interval: str | None, config: OntologyConfig | None = None) -> int | None:
    """Map a touched interval (or alias) to its harmonic order, if known."""
    canonical = normalize_touched_interval(interval, config=config)
    if canonical is None:
        return None
    cfg = config or load_ontology()
    order_index = _build_order_index(cfg)
    return order_index.get(canonical)
