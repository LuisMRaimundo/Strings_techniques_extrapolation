from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from string_technique_model.collections.adapter import (
    CollectionAdapter,
    DeclarativeCollectionAdapter,
)
from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path


class CollectionRegistry:
    def __init__(self, entries: list[dict[str, Any]], *, root: Path | None = None) -> None:
        self.root = root or PACKAGE_ROOT
        self.entries = {e["collection_id"]: e for e in entries}
        if len(self.entries) != len(entries):
            raise ValueError("Duplicate collection_id values in registry")

    @classmethod
    def from_yaml(cls, path: Path | str | None = None, *, root: Path | None = None) -> CollectionRegistry:
        root = root or PACKAGE_ROOT
        path = resolve_path(path or root / "configs" / "collections.yaml", root)
        data = load_yaml(path)
        entries = data.get("collections") or []
        if not isinstance(entries, list):
            raise ValueError("collections.yaml must contain a list under 'collections'")
        return cls(entries, root=root)

    def list(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        items = list(self.entries.values())
        if enabled_only:
            items = [e for e in items if e.get("enabled", True)]
        return sorted(items, key=lambda e: e["collection_id"])

    def get_entry(self, collection_id: str) -> dict[str, Any]:
        if collection_id not in self.entries:
            raise KeyError(
                f"Unknown collection_id {collection_id!r}. "
                f"Known: {sorted(self.entries)}"
            )
        return self.entries[collection_id]

    def get_adapter(self, collection_id: str) -> CollectionAdapter:
        entry = self.get_entry(collection_id)
        adapter_path = entry.get("adapter_class")
        if adapter_path:
            # Optional escape hatch for sources that cannot use declarative mapping.
            module_name, cls_name = adapter_path.rsplit(":", 1)
            import importlib

            mod = importlib.import_module(module_name)
            cls = getattr(mod, cls_name)
            return cls(entry, root=self.root)
        return DeclarativeCollectionAdapter(entry, root=self.root)

    def register_entry(self, entry: dict[str, Any], registry_path: Path | str) -> None:
        cid = entry["collection_id"]
        self.entries[cid] = entry
        path = resolve_path(registry_path, self.root)
        payload = {"collections": self.list()}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
