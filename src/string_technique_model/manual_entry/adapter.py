"""Manual GUI entry as a normal CollectionAdapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.collections.adapter import DeclarativeCollectionAdapter
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.reports import CompatibilityReport, ValidationReport
from string_technique_model.manual_entry.storage import ManualEntryStore


@dataclass
class CommittedCollection:
    collection_id: str
    commit_id: str
    parquet_path: Path
    csv_path: Path
    n_records: int
    workflow_state: str = "committed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "commit_id": self.commit_id,
            "parquet_path": str(self.parquet_path),
            "csv_path": str(self.csv_path),
            "n_records": self.n_records,
            "workflow_state": self.workflow_state,
        }


class ManualCollectionAdapter(DeclarativeCollectionAdapter):
    """Adapter for committed manual collections (CSV + schema), with draft helpers."""

    def __init__(
        self,
        entry: dict[str, Any],
        *,
        root: Path | None = None,
        store: ManualEntryStore | None = None,
    ) -> None:
        super().__init__(entry, root=root)
        self.store = store

    def load_draft(self) -> pd.DataFrame:
        if self.store is None:
            raise RuntimeError("No ManualEntryStore attached")
        rows = self.store.load_draft_records(self.collection_id)
        return pd.DataFrame(rows)

    def validate_draft(self) -> ValidationReport:
        # Draft validation is handled by MetricValidationService; this method
        # validates the mapped committed-like frame if present.
        if self.store is None:
            raise RuntimeError("No ManualEntryStore attached")
        draft = self.load_draft()
        if draft.empty:
            return ValidationReport(
                collection_id=self.collection_id,
                ok=False,
                errors=["empty_draft"],
                warnings=[],
                n_records=0,
                details={},
            )
        return ValidationReport(
            collection_id=self.collection_id,
            ok=True,
            errors=[],
            warnings=["draft_not_in_registry"],
            n_records=int(len(draft)),
            details={"workflow_state": "draft"},
        )

    def commit_collection(self) -> CommittedCollection:
        raise RuntimeError(
            "Use ManualEntryService.commit_collection — commit is transactional "
            "and registers through the generic collection service."
        )

    def validate_metric_compatibility(
        self,
        data: pd.DataFrame,
        metric_registry: MetricRegistry,
        target_metric_definition_id: str,
    ) -> CompatibilityReport:
        return super().validate_metric_compatibility(
            data, metric_registry, target_metric_definition_id
        )
