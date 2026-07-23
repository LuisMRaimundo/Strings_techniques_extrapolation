"""Application services for manual metric entry (GUI-agnostic)."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from string_technique_model.collections.instruments_domain import (
    EXCLUSION_REASON_UNSUPPORTED,
    UNSUPPORTED_STATUS,
    normalize_instrument_label,
)
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.service import import_collection, register_collection
from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.manual_entry.adapter import CommittedCollection, ManualCollectionAdapter
from string_technique_model.manual_entry.constants import (
    DEFAULT_ROLE,
    INPUT_METHODS,
)
from string_technique_model.manual_entry.duplicates import DuplicateDetectionService, fingerprint_row
from string_technique_model.manual_entry.mapping import MappingService
from string_technique_model.manual_entry.numbers import parse_density_input
from string_technique_model.manual_entry.pitch import apply_cb_transposition, resolve_pitch_fields
from string_technique_model.manual_entry.roles import RoleAssignmentService
from string_technique_model.manual_entry.storage import ManualEntryStore, utc_now
from string_technique_model.manual_entry.templates import write_templates
from string_technique_model.manual_entry.validation import MetricValidationService, ValidationReport
from string_technique_model.stable_seed import stable_hex, stable_record_id

MANUAL_SCHEMA_TEMPLATE = {
    "columns": {
        "record_id": "record_id",
        "instrument": "instrument",
        "technique": "technique",
        "pitch_name_written": "pitch_name_written",
        "pitch_midi_written": "pitch_midi_written",
        "pitch_name_sounding": "pitch_name_sounding",
        "pitch_midi_sounding": "pitch_midi_sounding",
        "fundamental_hz": "fundamental_hz",
        "dynamic": "dynamic",
        "string_name": "string_name",
        "density_value": "density_value",
        "density_unit": "density_unit",
        "metric_definition_id": "metric_definition_id",
        "measured_or_estimated": "measured_or_estimated",
        "mute_type": "mute_type",
        "mute_material": "mute_material",
        "mute_mass": "mute_mass",
        "harmonic_type": "harmonic_type",
        "harmonic_order": "harmonic_order",
        "articulation": "articulation",
        "performer_id": "performer_id",
        "instrument_id": "instrument_id",
        "analysis_window_id": "analysis_window_id",
        "normalisation_id": "normalisation_id",
        "frequency_range_id": "frequency_range_id",
        "original_technique_label": "original_technique_label",
        "original_dynamic_label": "original_dynamic_label",
        "original_instrument_label": "original_instrument_label",
        "technique_mapping_status": "technique_mapping_status",
        "dynamic_mapping_status": "dynamic_mapping_status",
        "instrument_mapping_status": "instrument_mapping_status",
        "input_method": "input_method",
        "record_version": "record_version",
        "commit_id": "commit_id",
        "source_description": "source_description",
        "created_by": "created_by",
        "created_at_utc": "created_at_utc",
        "last_edit_by": "last_edit_by",
        "last_edit_at_utc": "last_edit_at_utc",
        "fingerprint": "fingerprint",
        "usable_for_modelling": "usable_for_modelling",
        "replicate_id": "replicate_id",
        "take_id": "take_id",
        "uncertainty_type": "uncertainty_type",
        "uncertainty_value": "uncertainty_value",
        "sample_size": "sample_size",
        "citation": "citation",
        "source_page": "source_page",
        "table_number": "table_number",
        "figure_number": "figure_number",
        "extraction_method": "extraction_method",
    },
    "constants": {},
    "value_maps": {},
    "missing_policy": {"unavailable_fields": "missing_by_design"},
    "schema_mapping_version": "manual_entry_v1",
    "required_fields": [
        "instrument",
        "pitch_name_sounding",
        "density_value",
        "metric_definition_id",
    ],
    "missing_value_markers": ["", "NA", "NaN", "null"],
    "validation": {
        "allowed_instruments": ["vln", "vla", "vlc", "cb"],
        "allowed_techniques": [
            "ordinary",
            "artificial_harmonic",
            "sul_ponticello",
            "sul_tasto",
            "con_sordino",
        ],
        "allowed_dynamics": ["ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"],
    },
}


PASTE_COLUMN_CANDIDATES: dict[str, list[str]] = {
    "instrument": ["instrument", "instr", "instrument_code", "inst"],
    "technique": ["technique", "playing_mode", "execution_mode", "mode"],
    "pitch_name_sounding": ["pitch_name_sounding", "note", "pitch", "note_label", "sounding_note"],
    "pitch_midi_sounding": ["pitch_midi_sounding", "midi", "midi_number", "midi_sounding"],
    "fundamental_hz": ["fundamental_hz", "frequency", "freq_hz", "hz"],
    "dynamic": ["dynamic", "dyn", "dyn_label", "dynamics"],
    "density_value": ["density_value", "metric_value", "value", "acoustic_density", "density"],
    "density_unit": ["unit", "density_unit"],
    "uncertainty_value": ["uncertainty", "uncertainty_value", "sd", "se"],
    "string_name": ["string", "string_name"],
    "mute_type": ["mute_type", "mute"],
    "harmonic_order": ["harmonic_order", "harmonic"],
    "notes": ["notes", "comment", "remarks"],
    "metric_definition_id": ["metric_definition_id", "metric", "metric_code"],
    "measured_or_estimated": ["measured_or_estimated", "status"],
}


@dataclass
class PastePreview:
    n_imported: int
    n_valid: int
    n_warning: int
    n_invalid: int
    n_duplicates: int
    n_unsupported_instruments: int
    n_unmapped_techniques: int
    n_unmapped_dynamics: int
    n_incompatible_metrics: int
    column_mapping: dict[str, str]
    ambiguous_mappings: dict[str, list[str]]
    rows: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_imported": self.n_imported,
            "n_valid": self.n_valid,
            "n_warning": self.n_warning,
            "n_invalid": self.n_invalid,
            "n_duplicates": self.n_duplicates,
            "n_unsupported_instruments": self.n_unsupported_instruments,
            "n_unmapped_techniques": self.n_unmapped_techniques,
            "n_unmapped_dynamics": self.n_unmapped_dynamics,
            "n_incompatible_metrics": self.n_incompatible_metrics,
            "column_mapping": self.column_mapping,
            "ambiguous_mappings": self.ambiguous_mappings,
            "issues": self.issues,
        }


class AuditService:
    def __init__(self, store: ManualEntryStore) -> None:
        self.store = store

    def export_audit_csv(self, collection_id: str, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.store.audit_rows(collection_id)
        pd.DataFrame(rows).to_csv(path, index=False)
        return path


class CollectionCommitService:
    def __init__(
        self,
        store: ManualEntryStore,
        *,
        package_root: Path | None = None,
        run_config_path: Path | str | None = None,
        registry_path: Path | str | None = None,
    ) -> None:
        self.store = store
        self.root = package_root or PACKAGE_ROOT
        self.run_config_path = run_config_path
        self.registry_path = Path(registry_path) if registry_path else self.root / "configs" / "collections.yaml"

    def commit(
        self,
        collection_id: str,
        canonical_long: pd.DataFrame,
        meta: dict[str, Any],
        *,
        user: str,
        confirm: bool = False,
    ) -> CommittedCollection:
        if not confirm:
            raise RuntimeError("Explicit confirm=True required before commit")
        if self.store.load_collection_meta(collection_id) is None:
            raise KeyError(collection_id)
        if canonical_long.empty:
            raise RuntimeError("Cannot commit empty collection")

        # Transactional: write staging files, register, import; rollback files on failure
        csv_path = self.root / "data" / "manual" / f"{collection_id}.csv"
        schema_path = self.root / "configs" / "schemas" / f"{collection_id}.yaml"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.parent.mkdir(parents=True, exist_ok=True)

        commit_id = "commit_" + stable_hex(
            collection_id,
            utc_now(),
            len(canonical_long),
            n_chars=16,
        )
        export = canonical_long.copy()
        export["commit_id"] = commit_id

        written: list[Path] = []
        registry_path = self.registry_path
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not registry_path.exists():
            registry_path.write_text("collections: []\n", encoding="utf-8")
        backup_registry = registry_path.read_text(encoding="utf-8")

        try:
            export.to_csv(csv_path, index=False)
            written.append(csv_path)
            schema = dict(MANUAL_SCHEMA_TEMPLATE)
            schema["collection_id"] = collection_id
            schema["constants"] = {
                "measured_or_estimated": meta.get("measured_or_estimated"),
                "metric_definition_id": meta.get("metric_definition_id"),
            }
            schema_path.write_text(
                yaml.safe_dump(schema, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            written.append(schema_path)

            # Never overwrite silently
            from string_technique_model.collections.registry import CollectionRegistry

            reg = CollectionRegistry.from_yaml(registry_path, root=self.root)
            if collection_id in reg.entries and reg.entries[collection_id].get("enabled", True):
                existing_paths = reg.entries[collection_id].get("data_paths") or []
                abs_csv = str(csv_path.resolve())
                normalized = {str(Path(p).resolve()) if Path(p).is_absolute() or (self.root / p).exists() else str(p) for p in existing_paths}
                if abs_csv not in normalized and not any(collection_id in str(p) for p in existing_paths):
                    raise RuntimeError(
                        f"collection_id {collection_id!r} already exists; refuse silent overwrite"
                    )

            # Absolute paths so import works regardless of CollectionRegistry root.
            register_collection(
                collection_id,
                config_path=registry_path,
                display_name=meta.get("display_name"),
                data_paths=[str(csv_path.resolve())],
                fmt="csv",
                schema_mapping=str(schema_path.resolve()),
                metric_definition_id=str(meta.get("metric_definition_id") or "ewsd_v1"),
                collection_type=str(meta.get("collection_type") or "manually_transcribed"),
                default_roles=[str(meta.get("collection_role") or DEFAULT_ROLE)],
                measured_or_estimated=str(meta.get("measured_or_estimated")),
                notes=meta.get("source_description"),
            )

            result = import_collection(
                collection_id,
                self.run_config_path,
                dry_run=False,
                overwrite=True,
            )
            # Prefer run-config imported_dir when available
            imported_dir = self.root / "outputs" / "imported"
            if self.run_config_path:
                from string_technique_model.config import load_run_config

                cfg = load_run_config(self.run_config_path)
                imported_dir = Path(
                    cfg["paths_resolved"].get("imported_dir") or imported_dir
                )
            imported = imported_dir / f"{collection_id}.parquet"
            csv_out = imported_dir / f"{collection_id}.csv"
            imported_dir.mkdir(parents=True, exist_ok=True)
            if imported.exists():
                pd.read_parquet(imported).to_csv(csv_out, index=False)
            else:
                export.to_csv(csv_out, index=False)

            self.store.mark_committed(collection_id, commit_id=commit_id, user=user)
            AuditService(self.store).export_audit_csv(
                collection_id,
                self.root / "outputs" / "audit" / f"{collection_id}_audit_log.csv",
            )
            return CommittedCollection(
                collection_id=collection_id,
                commit_id=commit_id,
                parquet_path=imported if imported.exists() else csv_out,
                csv_path=csv_out,
                n_records=int(result.get("n_records") or len(export)),
            )
        except Exception:
            # Rollback registry + staged files
            registry_path.write_text(backup_registry, encoding="utf-8")
            for path in written:
                if path.exists():
                    path.unlink()
            self.store.set_workflow_state(collection_id, "validation_failed", user=user)
            raise


class ManualEntryService:
    """Facade used by GUI widgets — no scientific logic in callbacks."""

    def __init__(
        self,
        store: ManualEntryStore | None = None,
        *,
        package_root: Path | None = None,
        run_config_path: Path | str | None = None,
        metric_registry: MetricRegistry | None = None,
        db_path: Path | str | None = None,
        registry_path: Path | str | None = None,
    ) -> None:
        self.root = package_root or PACKAGE_ROOT
        self.run_config_path = run_config_path
        db = Path(db_path) if db_path else self.root / "outputs" / "manual_entry" / "manual_entry.sqlite"
        self.store = store or ManualEntryStore(db)
        defs = self.root / "configs" / "metric_definitions.yaml"
        conv = self.root / "configs" / "metric_conversions.yaml"
        if not defs.exists():
            defs = PACKAGE_ROOT / "configs" / "metric_definitions.yaml"
            conv = PACKAGE_ROOT / "configs" / "metric_conversions.yaml"
        if metric_registry is None:
            metric_registry = MetricRegistry.from_paths(defs, conv)
        self.metrics = metric_registry
        self.mapping = MappingService()
        self.validator = MetricValidationService(self.metrics, self.mapping)
        self.duplicates = DuplicateDetectionService()
        self.roles = RoleAssignmentService(self.metrics)
        self.registry_path = Path(registry_path) if registry_path else self.root / "configs" / "collections.yaml"
        self.commit_service = CollectionCommitService(
            self.store,
            package_root=self.root,
            run_config_path=run_config_path,
            registry_path=self.registry_path,
        )
        self.audit = AuditService(self.store)

    # --- Collection lifecycle -------------------------------------------------

    def create_collection(self, meta: dict[str, Any], *, deterministic_id_from_name: bool = False) -> dict[str, Any]:
        meta = dict(meta)
        if deterministic_id_from_name and not meta.get("collection_id"):
            meta["collection_id"] = self.generate_collection_id(str(meta.get("display_name") or "manual"))
        meta.setdefault("collection_role", DEFAULT_ROLE)
        meta.setdefault("workflow_state", "draft")
        issues = self.validator.validate_collection_metadata(meta)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            raise ValueError("; ".join(f"{e.field}:{e.reason}" for e in errors))
        if self.store.collection_exists(meta["collection_id"]):
            existing = self.store.load_collection_meta(meta["collection_id"])
            if existing and existing.get("workflow_state") == "committed":
                raise RuntimeError(f"collection_id already committed: {meta['collection_id']}")
        self.store.upsert_draft_collection(meta, user=meta.get("created_by"))
        return meta

    @staticmethod
    def generate_collection_id(display_name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", display_name.strip()).strip("_").lower()
        if not slug:
            slug = "manual"
        return f"manual_{slug}_{stable_hex(display_name, n_chars=8)}"

    def save_draft_rows(
        self,
        collection_id: str,
        rows: list[dict[str, Any]],
        *,
        user: str,
        input_method: str = "table_entry",
    ) -> list[dict[str, Any]]:
        if input_method not in INPUT_METHODS:
            raise ValueError(f"unknown input_method: {input_method}")
        meta = self.store.load_collection_meta(collection_id)
        if meta is None:
            raise KeyError(collection_id)
        if meta.get("workflow_state") == "committed":
            raise RuntimeError("Cannot overwrite committed collection draft silently")
        prepared = [self.prepare_observation(r, meta=meta, user=user, input_method=input_method) for r in rows]
        self.store.replace_draft_records(collection_id, prepared, user=user)
        self.store.set_workflow_state(collection_id, "draft", user=user)
        return prepared

    def load_draft(self, collection_id: str) -> pd.DataFrame:
        return pd.DataFrame(self.store.load_draft_records(collection_id))

    def validate_draft(self, collection_id: str) -> ValidationReport:
        meta = self.store.load_collection_meta(collection_id)
        if meta is None:
            raise KeyError(collection_id)
        rows = self.store.load_draft_records(collection_id)
        report = self.validator.validate_rows(rows, meta)
        dups = self.duplicates.classify_rows(rows)
        report.details["duplicates"] = [d.to_dict() for d in dups]
        self.store.save_validation(collection_id, report.to_dict())
        self.store.set_workflow_state(collection_id, report.status, user=meta.get("created_by"))
        return report

    def prepare_observation(
        self,
        row: dict[str, Any],
        *,
        meta: dict[str, Any],
        user: str,
        input_method: str,
    ) -> dict[str, Any]:
        out = dict(row)
        out["collection_id"] = meta["collection_id"]
        out["input_method"] = input_method
        out["created_by"] = out.get("created_by") or user
        out["last_edit_by"] = user
        now = utc_now()
        out.setdefault("created_at_utc", now)
        out["last_edit_at_utc"] = now
        out.setdefault("record_version", 1)
        out.setdefault("record_status", "draft")
        out.setdefault("measured_or_estimated", meta.get("measured_or_estimated"))
        out.setdefault("metric_definition_id", meta.get("metric_definition_id"))
        out["source_description"] = meta.get("source_description")

        raw_inst = out.get("instrument")
        out["original_instrument_label"] = raw_inst
        mapped_inst = normalize_instrument_label(raw_inst)
        if mapped_inst is None and raw_inst not in (None, ""):
            out["instrument"] = None
            out["instrument_mapping_status"] = UNSUPPORTED_STATUS
            out["exclusion_reason"] = EXCLUSION_REASON_UNSUPPORTED
        else:
            out["instrument"] = mapped_inst
            out["instrument_mapping_status"] = "mapped" if mapped_inst else "missing"
            out["exclusion_reason"] = None

        tech_src = out.get("original_technique_label") or out.get("technique")
        out["original_technique_label"] = tech_src
        tech_map = self.mapping.map_technique(None if tech_src is None else str(tech_src))
        out["technique"] = tech_map.canonical_code
        out["technique_mapping_status"] = tech_map.mapping_status

        dyn_src = out.get("original_dynamic_label") or out.get("dynamic")
        out["original_dynamic_label"] = dyn_src
        dyn_map = self.mapping.map_dynamic(None if dyn_src is None else str(dyn_src))
        out["dynamic"] = dyn_map.canonical_code
        out["dynamic_mapping_status"] = dyn_map.mapping_status

        pitch = resolve_pitch_fields(
            pitch_name=out.get("pitch_name_sounding") or out.get("pitch") or out.get("pitch_name"),
            pitch_midi=out.get("pitch_midi_sounding")
            if out.get("pitch_midi_sounding") is not None
            else out.get("pitch_midi"),
            fundamental_hz=out.get("fundamental_hz"),
        )
        if pitch.get("pitch_name_sounding"):
            out["pitch_name_sounding"] = pitch["pitch_name_sounding"]
        if pitch.get("pitch_midi_sounding") is not None:
            out["pitch_midi_sounding"] = pitch["pitch_midi_sounding"]
        if pitch.get("fundamental_hz") is not None:
            out["fundamental_hz"] = pitch["fundamental_hz"]

        if out.get("instrument") in {"vln", "vla", "vlc"}:
            out.setdefault("pitch_name_written", out.get("pitch_name_sounding"))
            out.setdefault("pitch_midi_written", out.get("pitch_midi_sounding"))
        if out.get("instrument") == "cb":
            # Preserve written; compute sounding only with explicit transposition + confirmation
            if out.get("pitch_name_written") is None and out.get("pitch_name_sounding"):
                # If user entered only one pitch into sounding field as written, keep written separate
                out.setdefault("pitch_name_written", out.get("pitch_name_sounding"))
                out.setdefault("pitch_midi_written", out.get("pitch_midi_sounding"))
            cb = apply_cb_transposition(
                written_name=out.get("pitch_name_written"),
                written_midi=out.get("pitch_midi_written"),
                sounding_name=out.get("pitch_name_sounding"),
                sounding_midi=out.get("pitch_midi_sounding"),
                transposition_semitones=out.get("cb_transposition_semitones"),
                confirmed=bool(out.get("cb_sounding_confirmed")),
            )
            out["pitch_name_written"] = cb["pitch_name_written"]
            out["pitch_midi_written"] = cb["pitch_midi_written"]
            if cb["ok"] or out.get("cb_sounding_confirmed"):
                out["pitch_name_sounding"] = cb["pitch_name_sounding"]
                out["pitch_midi_sounding"] = cb["pitch_midi_sounding"]

        parsed = parse_density_input(out.get("density_value"), confirmed_locale=out.get("confirmed_locale"))
        if parsed.ok:
            out["density_value"] = parsed.value
            out["density_value_parsed_preview"] = parsed.value
        out["density_unit"] = out.get("density_unit") or "dimensionless"

        out["fingerprint"] = fingerprint_row(out)
        if not out.get("record_id"):
            out["record_id"] = stable_record_id(
                out["collection_id"],
                out.get("instrument"),
                out.get("original_technique_label"),
                out.get("pitch_name_sounding"),
                out.get("original_dynamic_label"),
                out.get("density_value"),
                out.get("replicate_id"),
                out.get("take_id"),
                out.get("input_method"),
            )
        out["transformations"] = out.get("transformations") or []
        out["usable_for_modelling"] = (
            out.get("technique_mapping_status") == "mapped"
            and out.get("dynamic_mapping_status") == "mapped"
            and out.get("instrument_mapping_status") == "mapped"
            and out.get("technique") is not None
        )
        return out

    def map_to_canonical_schema(self, collection_id: str) -> pd.DataFrame:
        meta = self.store.load_collection_meta(collection_id)
        if meta is None:
            raise KeyError(collection_id)
        rows = self.store.load_draft_records(collection_id)
        frame = pd.DataFrame(rows)
        # Long format is authoritative
        if frame.empty:
            return frame
        # Drop unsupported instruments from scientific commit set (kept in draft for correction)
        if "instrument_mapping_status" in frame.columns:
            unsupported = frame[frame["instrument_mapping_status"] == UNSUPPORTED_STATUS]
            frame = frame[frame["instrument_mapping_status"] != UNSUPPORTED_STATUS].copy()
            meta["_n_unsupported_dropped_at_map"] = int(len(unsupported))
        return frame.reset_index(drop=True)

    def commit_collection(self, collection_id: str, *, user: str, confirm: bool = False) -> CommittedCollection:
        report = self.validate_draft(collection_id)
        if report.status == "validation_failed" or report.n_invalid:
            raise RuntimeError("Cannot commit while blocking errors remain")
        # Block exact duplicates without confirmation flag on meta
        meta = self.store.load_collection_meta(collection_id) or {}
        dups = report.details.get("duplicates") or []
        blocking = [
            d
            for d in dups
            if d.get("classification") in {"exact_duplicate", "conflicting_observation", "probable_duplicate"}
            and d.get("requires_confirmation")
            and not meta.get("duplicates_confirmed")
        ]
        if blocking:
            raise RuntimeError("Duplicate resolution requires user confirmation")
        canonical = self.map_to_canonical_schema(collection_id)
        # Ensure no out-of-domain instruments
        if "instrument" in canonical.columns:
            bad = canonical[~canonical["instrument"].isin(["vln", "vla", "vlc", "cb"])]
            if len(bad):
                raise RuntimeError("Out-of-domain instruments present; commit refused")
        return self.commit_service.commit(collection_id, canonical, meta, user=user, confirm=confirm)

    def review_summary(self, collection_id: str) -> dict[str, Any]:
        meta = self.store.load_collection_meta(collection_id) or {}
        rows = self.store.load_draft_records(collection_id)
        report = self.validate_draft(collection_id)
        frame = pd.DataFrame(rows)
        pitches = sorted({str(x) for x in frame.get("pitch_name_sounding", pd.Series(dtype=object)).dropna().unique()})
        return {
            "collection_metadata": meta,
            "observation_count": len(rows),
            "instruments": sorted({str(x) for x in frame.get("instrument", pd.Series(dtype=object)).dropna().unique()}),
            "techniques": sorted(
                {str(x) for x in frame.get("original_technique_label", pd.Series(dtype=object)).dropna().unique()}
            ),
            "dynamics": sorted(
                {str(x) for x in frame.get("original_dynamic_label", pd.Series(dtype=object)).dropna().unique()}
            ),
            "pitch_ranges": [pitches[0], pitches[-1]] if pitches else [],
            "metric_definitions": sorted(
                {str(x) for x in frame.get("metric_definition_id", pd.Series(dtype=object)).dropna().unique()}
            ),
            "missing_fields": [i.to_dict() for i in report.issues if i.reason == "missing_required_field"],
            "warnings": [i.to_dict() for i in report.issues if i.severity == "warning"],
            "errors": [i.to_dict() for i in report.issues if i.severity == "error"],
            "duplicate_count": len(report.details.get("duplicates") or []),
            "provenance_completeness": bool(meta.get("source_description") and meta.get("created_by")),
            "validation_status": report.status,
        }

    # --- Grid / paste ---------------------------------------------------------

    def grid_to_long(
        self,
        grid: pd.DataFrame,
        *,
        instrument: str,
        technique: str,
        metric_definition_id: str,
        measured_or_estimated: str,
        pitch_column: str = "pitch",
    ) -> list[dict[str, Any]]:
        """Convert pitch × dynamic wide grid to long-format observations."""
        if pitch_column not in grid.columns:
            raise ValueError(f"Missing pitch column {pitch_column!r}")
        dynamics = [c for c in grid.columns if c != pitch_column]
        rows: list[dict[str, Any]] = []
        for _, r in grid.iterrows():
            pitch = r[pitch_column]
            for dyn in dynamics:
                val = r[dyn]
                if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
                    continue
                rows.append(
                    {
                        "instrument": instrument,
                        "technique": technique,
                        "pitch_name_sounding": pitch,
                        "dynamic": dyn,
                        "density_value": val,
                        "metric_definition_id": metric_definition_id,
                        "measured_or_estimated": measured_or_estimated,
                        "input_method": "grid_entry",
                    }
                )
        return rows

    def preview_paste(
        self,
        text: str,
        *,
        column_mapping: dict[str, str] | None = None,
        confirmed_ambiguous: bool = False,
    ) -> PastePreview:
        table = self._parse_tsv(text)
        if table.empty:
            return PastePreview(0, 0, 0, 0, 0, 0, 0, 0, 0, {}, {})
        source_cols = [str(c) for c in table.columns]
        auto_map, ambiguous = self._suggest_column_mapping(source_cols)
        if column_mapping is None:
            column_mapping = auto_map
        if ambiguous and not confirmed_ambiguous and column_mapping == auto_map:
            # Do not guess silently when two possible mappings exist
            return PastePreview(
                n_imported=int(len(table)),
                n_valid=0,
                n_warning=0,
                n_invalid=0,
                n_duplicates=0,
                n_unsupported_instruments=0,
                n_unmapped_techniques=0,
                n_unmapped_dynamics=0,
                n_incompatible_metrics=0,
                column_mapping=auto_map,
                ambiguous_mappings=ambiguous,
                rows=[],
                issues=[{"reason": "ambiguous_column_mapping", "fields": ambiguous}],
            )

        renamed = table.rename(columns={v: k for k, v in column_mapping.items() if v in table.columns})
        rows = renamed.to_dict(orient="records")
        # Temporary meta for validation stats
        meta = {
            "collection_id": "_paste_preview",
            "display_name": "paste",
            "collection_type": "measured",
            "collection_role": DEFAULT_ROLE,
            "metric_definition_id": "ewsd_v1",
            "created_by": "preview",
            "measured_or_estimated": "measured",
            "source_description": "clipboard_paste_preview",
        }
        prepared = []
        for r in rows:
            row: dict[str, Any] = {str(k): v for k, v in dict(r).items()}
            row.setdefault("metric_definition_id", "ewsd_v1")
            row.setdefault("measured_or_estimated", "measured")
            prepared.append(
                self.prepare_observation(row, meta=meta, user="preview", input_method="clipboard_paste")
            )
        report = self.validator.validate_rows(prepared, None)
        dups = self.duplicates.classify_rows(prepared)
        n_unsup = sum(1 for r in prepared if r.get("instrument_mapping_status") == UNSUPPORTED_STATUS)
        n_untech = sum(1 for r in prepared if r.get("technique_mapping_status") == "unmapped")
        n_undyn = sum(1 for r in prepared if r.get("dynamic_mapping_status") == "unmapped")
        n_incompat = sum(
            1
            for i in report.issues
            if i.reason == "incompatible" or i.field == "metric_definition_id" and "incompatible" in i.reason
        )
        return PastePreview(
            n_imported=len(prepared),
            n_valid=report.n_valid,
            n_warning=report.n_warning,
            n_invalid=report.n_invalid,
            n_duplicates=len(dups),
            n_unsupported_instruments=n_unsup,
            n_unmapped_techniques=n_untech,
            n_unmapped_dynamics=n_undyn,
            n_incompatible_metrics=n_incompat,
            column_mapping=column_mapping,
            ambiguous_mappings=ambiguous,
            rows=prepared,
            issues=[i.to_dict() for i in report.issues],
        )

    def copy_from_collection(
        self,
        source_collection_id: str,
        new_meta: dict[str, Any],
        *,
        user: str,
    ) -> dict[str, Any]:
        """Copy committed imported parquet into a new derived draft collection."""
        src = self.root / "outputs" / "imported" / f"{source_collection_id}.parquet"
        if not src.exists():
            raise FileNotFoundError(src)
        frame = pd.read_parquet(src)
        new_meta = dict(new_meta)
        new_meta.setdefault("collection_type", "derived")
        new_meta.setdefault("collection_role", DEFAULT_ROLE)
        new_meta.setdefault("measured_or_estimated", "derived")
        meta = self.create_collection(new_meta)
        rows = []
        for rec in frame.to_dict(orient="records"):
            row = {
                "instrument": rec.get("instrument"),
                "technique": rec.get("technique"),
                "original_technique_label": rec.get("technique"),
                "pitch_name_sounding": rec.get("pitch_name_sounding"),
                "pitch_midi_sounding": rec.get("pitch_midi_sounding"),
                "pitch_name_written": rec.get("pitch_name_written"),
                "pitch_midi_written": rec.get("pitch_midi_written"),
                "dynamic": rec.get("dynamic"),
                "original_dynamic_label": rec.get("dynamic"),
                "density_value": rec.get("density_value"),
                "metric_definition_id": rec.get("metric_definition_id"),
                "measured_or_estimated": meta.get("measured_or_estimated"),
                "copied_from_collection": source_collection_id,
                "copied_from_record_id": rec.get("record_id"),
            }
            rows.append(row)
        self.save_draft_rows(meta["collection_id"], rows, user=user, input_method="copied_from_collection")
        return meta

    def assign_role(
        self,
        collection_id: str,
        role: str,
        *,
        existing_calibration_ids: list[str] | None = None,
        existing_validation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        meta = self.store.load_collection_meta(collection_id)
        if meta is None:
            raise KeyError(collection_id)
        if meta.get("workflow_state") != "committed":
            raise RuntimeError("Role assignment only for committed collections")
        path = self.root / "outputs" / "imported" / f"{collection_id}.parquet"
        frame = pd.read_parquet(path) if path.exists() else self.load_draft(collection_id)
        result = self.roles.validate_role_assignment(
            role=role,
            frame=frame,
            meta=meta,
            existing_calibration_ids=existing_calibration_ids,
            existing_validation_ids=existing_validation_ids,
        )
        if not result.ok:
            return result.to_dict()
        meta["collection_role"] = role
        meta["workflow_state"] = "committed"
        self.store.upsert_draft_collection(meta, user=meta.get("created_by"))
        # Update registry default_roles
        registry_path = self.root / "configs" / "collections.yaml"
        from string_technique_model.collections.registry import CollectionRegistry

        reg = CollectionRegistry.from_yaml(registry_path, root=self.root)
        entry = dict(reg.get_entry(collection_id))
        entry["default_roles"] = [role]
        reg.register_entry(entry, registry_path)
        return result.to_dict()

    def edit_record(
        self,
        old_record_id: str,
        updates: dict[str, Any],
        *,
        user: str,
        reason: str,
    ) -> dict[str, Any]:
        with self.store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM manual_records WHERE record_id = ?",
                (old_record_id,),
            ).fetchone()
        if row is None:
            raise KeyError(old_record_id)
        old = json.loads(row["payload_json"])
        meta = self.store.load_collection_meta(old["collection_id"])
        if meta is None:
            raise KeyError(old["collection_id"])
        new_payload = dict(old)
        new_payload.update(updates)
        new_payload["record_id"] = stable_record_id(
            old["collection_id"],
            new_payload.get("instrument"),
            new_payload.get("original_technique_label"),
            new_payload.get("pitch_name_sounding"),
            new_payload.get("original_dynamic_label"),
            new_payload.get("density_value"),
            new_payload.get("replicate_id"),
            "edit",
            utc_now(),
        )
        prepared = self.prepare_observation(
            new_payload,
            meta=meta,
            user=user,
            input_method=new_payload.get("input_method") or "table_entry",
        )
        prepared["supersedes_record_id"] = old_record_id
        prepared["record_version"] = int(old.get("record_version") or 1) + 1
        self.store.supersede_record(old_record_id, prepared, user=user, reason=reason)
        return prepared

    def logical_delete(self, record_id: str, *, user: str, reason: str) -> None:
        self.store.logical_delete_record(record_id, user=user, reason=reason)

    def download_templates(self, output_dir: Path | str | None = None) -> dict[str, Path]:
        return write_templates(output_dir or (self.root / "outputs" / "manual_entry" / "templates"))

    def register_metric_definition(self, definition: dict[str, Any]) -> dict[str, Any]:
        """Append a metric definition to the YAML registry (validated fields)."""
        required = [
            "metric_definition_id",
            "name",
            "version",
            "mathematical_domain",
            "unit",
            "normalisation",
            "frequency_range",
            "temporal_window",
            "amplitude_or_power_convention",
            "thresholding",
            "aggregation_method",
        ]
        for key in required:
            if key not in definition or definition[key] in (None, ""):
                raise ValueError(f"missing metric field: {key}")
        mid = str(definition["metric_definition_id"])
        path = self.root / "configs" / "metric_definitions.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        defs = data.setdefault("metric_definitions", {})
        if mid in defs:
            raise RuntimeError(f"metric_definition_id already exists: {mid}")
        formula = definition.get("exact_formula") or definition.get("formula") or "unresolved"
        status = "resolved" if formula not in (None, "", "unresolved") else "unresolved"
        entry = {
            "metric_definition_id": mid,
            "name": definition["name"],
            "version": definition["version"],
            "exact_formula": formula,
            "mathematical_domain": definition["mathematical_domain"],
            "unit": definition["unit"],
            "normalisation": definition["normalisation"],
            "frequency_range_id": definition.get("frequency_range"),
            "temporal_window": definition["temporal_window"],
            "amplitude_or_power_convention": definition["amplitude_or_power_convention"],
            "thresholding": definition["thresholding"],
            "aggregation_method": definition["aggregation_method"],
            "metric_definition_status": status,
            "usable_for_pooling": False if status == "unresolved" else bool(definition.get("usable_for_pooling")),
            "compatible_with": [mid],
            "notes": definition.get("notes"),
        }
        defs[mid] = entry
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        # refresh registry
        self.metrics = MetricRegistry.from_paths(
            path,
            self.root / "configs" / "metric_conversions.yaml",
        )
        self.validator = MetricValidationService(self.metrics, self.mapping)
        return entry

    def get_adapter(self, collection_id: str) -> ManualCollectionAdapter:
        entry = {
            "collection_id": collection_id,
            "display_name": collection_id,
            "enabled": True,
            "format": "csv",
            "data_paths": [f"data/manual/{collection_id}.csv"],
            "schema_mapping": f"configs/schemas/{collection_id}.yaml",
            "metric_definition_id": "ewsd_v1",
            "default_roles": [DEFAULT_ROLE],
            "collection_type": "manually_transcribed",
            "measured_or_estimated": "manually_transcribed",
            "adapter_class": "string_technique_model.manual_entry.adapter:ManualCollectionAdapter",
        }
        return ManualCollectionAdapter(entry, root=self.root, store=self.store)

    def is_draft_in_registry(self, collection_id: str) -> bool:
        """Drafts must not appear as importable registry scientific sources until committed."""
        meta = self.store.load_collection_meta(collection_id)
        if meta is None:
            return False
        if meta.get("workflow_state") != "committed":
            # Even if somehow registered, draft state means not ready
            from string_technique_model.collections.registry import CollectionRegistry

            reg = CollectionRegistry.from_yaml(self.root / "configs" / "collections.yaml", root=self.root)
            return collection_id in reg.entries and meta.get("workflow_state") == "committed"
        return True

    @staticmethod
    def _parse_tsv(text: str) -> pd.DataFrame:
        text = text.strip("\n")
        if not text.strip():
            return pd.DataFrame()
        # Detect delimiter
        dialect = csv.Sniffer().sniff(text.splitlines()[0] + "\n" + (text.splitlines()[1] if len(text.splitlines()) > 1 else ""), delimiters="\t,;")
        buf = io.StringIO(text)
        return pd.read_csv(buf, sep=dialect.delimiter)

    @staticmethod
    def _suggest_column_mapping(source_cols: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
        mapping: dict[str, str] = {}
        ambiguous: dict[str, list[str]] = {}
        normalized = {c: re.sub(r"\s+", "_", c.strip().lower()) for c in source_cols}
        for target, candidates in PASTE_COLUMN_CANDIDATES.items():
            hits = [src for src, norm in normalized.items() if norm in candidates or src in candidates]
            if len(hits) == 1:
                mapping[target] = hits[0]
            elif len(hits) > 1:
                ambiguous[target] = hits
        return mapping, ambiguous


def literature_parameters_untouched_by_manual(manual_frame: pd.DataFrame, literature_path: Path) -> bool:
    """Ensure target-technique observations are not written into literature parameters."""
    if not literature_path.exists():
        return True
    text = literature_path.read_text(encoding="utf-8")
    for val in manual_frame.get("density_value", pd.Series(dtype=float)).dropna().astype(str):
        # Heuristic: exact value dumps into literature yaml would be a bug for this check in tests
        if f"density_ratio: {val}" in text or f"value: {val}" in text and "manual" in text.lower():
            return False
    return True
