"""In-memory metadata collection with undo/redo and persistence helpers."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from string_technique_model.metadata_entry import io as meta_io
from string_technique_model.metadata_entry.models import SCHEMA_VERSION, MetadataEntryRecord
from string_technique_model.metadata_entry.technique_combo import (
    TechniqueCombination,
    apply_combination_to_row,
    summarize_technique_combination,
)
from string_technique_model.metadata_entry.validation import MetadataValidationReport, MetadataValidationService
from string_technique_model.pitch.modes import migrate_legacy_pitch_fields


class MetadataCollection:
    """Table-first collection: one record per analysis unit."""

    def __init__(self, *, collection_id: str = "untitled_collection", display_name: str = "Untitled") -> None:
        self.collection_id = collection_id
        self.display_name = display_name
        self.path: Path | None = None
        self.records: list[MetadataEntryRecord] = []
        self._undo: list[list[dict[str, Any]]] = []
        self._redo: list[list[dict[str, Any]]] = []
        self._validator = MetadataValidationService()
        self.last_report: MetadataValidationReport | None = None
        self.dirty = False

    def _snapshot(self) -> list[dict[str, Any]]:
        return [r.model_dump() for r in self.records]

    def _push_undo(self) -> None:
        self._undo.append(self._snapshot())
        self._redo.clear()
        if len(self._undo) > 100:
            self._undo.pop(0)

    def _restore(self, snap: list[dict[str, Any]]) -> None:
        self.records = [MetadataEntryRecord.from_mapping(r) for r in snap]
        self.dirty = True

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    def new_collection(self, collection_id: str = "untitled_collection", display_name: str = "Untitled") -> None:
        self._push_undo()
        self.collection_id = collection_id
        self.display_name = display_name
        self.path = None
        self.records = []
        self.dirty = False

    def add_record(self, record: MetadataEntryRecord | None = None) -> MetadataEntryRecord:
        self._push_undo()
        rec = record or MetadataEntryRecord.new_empty(collection_id=self.collection_id)
        if not rec.collection_id:
            rec.collection_id = self.collection_id
        if not rec.technique_display:
            rec.technique_display = summarize_technique_combination(
                left_hand_regime=rec.left_hand_regime,
                bow_contact_regime=rec.bow_contact_regime,
                mute_state=rec.mute_state,
                articulation=rec.articulation,
                additional_technique=rec.additional_technique,
                legacy_technique=rec.technique,
            ) or None
        self.records.append(rec)
        self.dirty = True
        return rec

    def duplicate_record(self, index: int) -> MetadataEntryRecord | None:
        if index < 0 or index >= len(self.records):
            return None
        self._push_undo()
        src = self.records[index].model_dump()
        src["record_id"] = MetadataEntryRecord.new_empty().record_id
        rec = MetadataEntryRecord.from_mapping(src)
        self.records.insert(index + 1, rec)
        self.dirty = True
        return rec

    def delete_records(self, indices: list[int]) -> None:
        if not indices:
            return
        self._push_undo()
        for i in sorted(set(indices), reverse=True):
            if 0 <= i < len(self.records):
                del self.records[i]
        self.dirty = True

    def update_record(self, index: int, updates: dict[str, Any]) -> MetadataEntryRecord | None:
        if index < 0 or index >= len(self.records):
            return None
        self._push_undo()
        data = self.records[index].model_dump()
        data.update(updates)
        # Keep audio/source aliases aligned
        if "audio_file" in updates and "source_file" not in updates:
            data["source_file"] = updates["audio_file"]
        if "source_file" in updates and "audio_file" not in updates:
            data["audio_file"] = updates["source_file"]
        # Refresh technique summary when combo fields change
        if any(
            k in updates
            for k in (
                "left_hand_regime",
                "bow_contact_regime",
                "mute_state",
                "articulation",
                "additional_technique",
                "technique",
            )
        ):
            data = apply_combination_to_row(
                data,
                TechniqueCombination(
                    left_hand_regime=data.get("left_hand_regime"),
                    bow_contact_regime=data.get("bow_contact_regime"),
                    mute_state=data.get("mute_state"),
                    articulation=data.get("articulation"),
                    additional_technique=data.get("additional_technique"),
                ),
            )
        data = migrate_legacy_pitch_fields(data)
        self.records[index] = MetadataEntryRecord.from_mapping(data)
        self.dirty = True
        return self.records[index]

    def fill_down(self, column: str, start: int, end: int) -> None:
        if start < 0 or start >= len(self.records) or end <= start:
            return
        self._push_undo()
        value = getattr(self.records[start], column, None)
        if value is None and column in self.records[start].model_dump():
            value = self.records[start].model_dump().get(column)
        for i in range(start + 1, min(end + 1, len(self.records))):
            data = self.records[i].model_dump()
            data[column] = copy.deepcopy(value)
            self.records[i] = MetadataEntryRecord.from_mapping(data)
        self.dirty = True

    def validate(self) -> MetadataValidationReport:
        rows = [r.model_dump() for r in self.records]
        report = self._validator.validate_rows(rows)
        # Attach per-row status
        by_row: dict[int, list[str]] = {}
        for issue in report.issues:
            if issue.row_index is None:
                continue
            by_row.setdefault(issue.row_index, []).append(issue.severity)
        for i, rec in enumerate(self.records):
            levels = by_row.get(i, [])
            if "error" in levels:
                rec.validation_status = "error"
            elif "warning" in levels:
                rec.validation_status = "warning"
            elif levels:
                rec.validation_status = "information"
            else:
                rec.validation_status = "ok"
        self.last_report = report
        return report

    def save_json(self, path: Path | str) -> Path:
        path = Path(path)
        meta_io.export_json(self.records, path)
        self.path = path
        self.dirty = False
        return path

    def save_csv(self, path: Path | str, *, columns: list[str] | None = None) -> Path:
        path = Path(path)
        meta_io.export_csv(self.records, path, columns=columns)
        self.path = path
        self.dirty = False
        return path

    def export(self, path: Path | str, *, fmt: str | None = None, columns: list[str] | None = None) -> Path:
        path = Path(path)
        fmt = (fmt or path.suffix.lstrip(".")).lower()
        if fmt == "json":
            return meta_io.export_json(self.records, path)
        if fmt == "csv":
            return meta_io.export_csv(self.records, path, columns=columns)
        if fmt in {"parquet", "pq"}:
            return meta_io.export_parquet(self.records, path)
        raise ValueError(f"Unsupported export format: {fmt}")

    def load(self, path: Path | str) -> list[str]:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".json":
            records, problems = meta_io.import_json(path)
        elif suffix == ".csv":
            records, problems = meta_io.import_csv(path)
        elif suffix in {".parquet", ".pq"}:
            records, problems = meta_io.import_parquet(path)
        else:
            raise ValueError(f"Unsupported import format: {suffix}")
        self._push_undo()
        self.records = records
        for r in self.records:
            if not r.collection_id:
                r.collection_id = self.collection_id
        self.path = path
        self.dirty = False
        return problems

    def counts(self) -> dict[str, int]:
        status = [r.validation_status or "" for r in self.records]
        return {
            "total": len(self.records),
            "ok": sum(1 for s in status if s == "ok"),
            "warnings": sum(1 for s in status if s == "warning"),
            "errors": sum(1 for s in status if s == "error"),
        }

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION
