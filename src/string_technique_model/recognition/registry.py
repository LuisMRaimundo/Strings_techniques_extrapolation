"""Load recognition label-mapping config from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.recognition.models import (
    RecognitionLabelMapping,
    RecognitionLabelMappingRegistry,
)

DEFAULT_PATH = PACKAGE_ROOT / "configs" / "recognition_label_mappings.yaml"


def load_recognition_label_mappings(
    path: Path | str | None = None,
) -> RecognitionLabelMappingRegistry:
    data = load_yaml(resolve_path(path or DEFAULT_PATH))
    mappings = [
        RecognitionLabelMapping.model_validate(item) for item in data.get("mappings", [])
    ]
    return RecognitionLabelMappingRegistry(
        version=data.get("version"),
        schema_version=data.get("schema_version"),
        source_taxonomy=data.get("source_taxonomy"),
        mappings=mappings,
    )


@lru_cache(maxsize=1)
def _default_mappings() -> RecognitionLabelMappingRegistry:
    return load_recognition_label_mappings()


def get_recognition_label_mapping(source_label: str) -> RecognitionLabelMapping | None:
    for mapping in _default_mappings().mappings:
        if mapping.source_label == source_label:
            return mapping
    return None
