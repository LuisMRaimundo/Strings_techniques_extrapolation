"""Metadata-entry domain layer (GUI-independent)."""

from string_technique_model.metadata_entry.collection import MetadataCollection
from string_technique_model.metadata_entry.models import SCHEMA_VERSION, MetadataEntryRecord
from string_technique_model.metadata_entry.technique_combo import (
    TechniqueCombination,
    summarize_technique_combination,
)
from string_technique_model.metadata_entry.validation import MetadataValidationService

__all__ = [
    "SCHEMA_VERSION",
    "MetadataCollection",
    "MetadataEntryRecord",
    "MetadataValidationService",
    "TechniqueCombination",
    "summarize_technique_combination",
]
