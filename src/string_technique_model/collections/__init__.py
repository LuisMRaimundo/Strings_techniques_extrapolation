"""Generic multi-collection ingestion, registry, pooling, and compatibility."""

from string_technique_model.collections.adapter import (
    CollectionAdapter,
    DeclarativeCollectionAdapter,
)
from string_technique_model.collections.registry import CollectionRegistry

__all__ = [
    "CollectionAdapter",
    "DeclarativeCollectionAdapter",
    "CollectionRegistry",
]
