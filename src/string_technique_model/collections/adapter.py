from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.collections.canonical import PHASE1_REQUIRED_COLUMNS, CanonicalRecord
from string_technique_model.collections.instruments_domain import (
    ALLOWED_INSTRUMENTS,
    UNSUPPORTED_STATUS,
)
from string_technique_model.collections.loaders import file_fingerprint, load_table
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.quality import annotate_quality, summarize_quality
from string_technique_model.collections.reports import (
    CollectionInventory,
    CompatibilityReport,
    ValidationReport,
)
from string_technique_model.collections.schema_map import (
    map_raw_to_canonical,
    relativize_source_path,
)
from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path


class CollectionAdapter(ABC):
    collection_id: str

    @abstractmethod
    def inspect(self) -> CollectionInventory: ...

    @abstractmethod
    def load_raw(self) -> pd.DataFrame: ...

    @abstractmethod
    def map_to_canonical_schema(self, data: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def validate_schema(self, data: pd.DataFrame) -> ValidationReport: ...

    @abstractmethod
    def validate_metric_compatibility(
        self,
        data: pd.DataFrame,
        metric_registry: MetricRegistry,
        target_metric_definition_id: str,
    ) -> CompatibilityReport: ...

    @abstractmethod
    def export_canonical(self, data: pd.DataFrame, output_dir: Path | str) -> Path: ...

    def enrich(
        self,
        canonical: pd.DataFrame,
        metric_registry: MetricRegistry,
        target_metric_definition_id: str,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def quality_summary(self, enriched: pd.DataFrame) -> dict[str, Any]:
        raise NotImplementedError

    def assert_sources_unchanged(self) -> None:
        raise NotImplementedError


class DeclarativeCollectionAdapter(CollectionAdapter):
    """Generic adapter driven entirely by configs/collections.yaml + schema YAML."""

    def __init__(self, entry: dict[str, Any], *, root: Path | None = None) -> None:
        self.entry = entry
        self.root = root or PACKAGE_ROOT
        self.collection_id = str(entry["collection_id"])
        schema_path = resolve_path(entry["schema_mapping"], self.root)
        self.schema = load_yaml(schema_path)
        self._source_fingerprints_before: list[dict[str, Any]] = []

    def _default_roles(self) -> list[str]:
        roles = self.entry.get("default_roles")
        if roles:
            return list(roles)
        legacy = self.entry.get("default_role")
        if legacy:
            return [str(legacy)]
        return []

    def inspect(self) -> CollectionInventory:
        paths = [resolve_path(p, self.root) for p in self.entry.get("data_paths") or []]
        found = [p for p in paths if p.exists()]
        columns: list[str] = []
        n_rows = None
        if found:
            raw = self.load_raw()
            columns = list(raw.columns)
            n_rows = int(len(raw))
        return CollectionInventory(
            collection_id=self.collection_id,
            display_name=str(self.entry.get("display_name", self.collection_id)),
            enabled=bool(self.entry.get("enabled", True)),
            format=str(self.entry.get("format")),
            data_paths=[str(p) for p in paths],
            n_files_found=len(found),
            n_raw_rows=n_rows,
            columns=columns,
            notes=self.entry.get("notes"),
            default_role=(self._default_roles()[0] if self._default_roles() else None),
            default_roles=self._default_roles(),
            metric_definition_id=self.entry.get("metric_definition_id"),
            collection_type=self.entry.get("collection_type"),
            measured_or_estimated=self.entry.get("measured_or_estimated"),
        )

    def load_raw(self) -> pd.DataFrame:
        paths = [resolve_path(p, self.root) for p in self.entry.get("data_paths") or []]
        if not paths:
            raise FileNotFoundError(f"No data_paths configured for {self.collection_id}")
        self._source_fingerprints_before = [file_fingerprint(p) for p in paths if p.exists()]
        frames = []
        for path in paths:
            frame = load_table(
                path,
                str(self.entry.get("format")),
                sheet_name=self.entry.get("sheet_name"),
                sqlite_table=(
                    self.entry.get("table_name")
                    or self.entry.get("sqlite_table")
                    or self.entry.get("sheet_name")
                ),
                nested_spectral_options=self.schema.get("nested_spectral_options"),
            )
            frame = frame.copy()
            frame["__source_file"] = relativize_source_path(path, self.root)
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)

    def map_to_canonical_schema(self, data: pd.DataFrame) -> pd.DataFrame:
        parts = []
        table_name = self.entry.get("table_name")
        if "__source_file" in data.columns:
            for source_file, part in data.groupby("__source_file", sort=True):
                raw = part.drop(columns=["__source_file"])
                parts.append(
                    map_raw_to_canonical(
                        raw,
                        schema=self.schema,
                        collection_meta=self.entry,
                        source_file=str(source_file),
                        source_sheet=self.entry.get("sheet_name"),
                        source_table=table_name,
                        import_timestamp_utc=None,
                    )
                )
        else:
            parts.append(
                map_raw_to_canonical(
                    data,
                    schema=self.schema,
                    collection_meta=self.entry,
                    source_file=";".join(self.entry.get("data_paths") or []),
                    source_sheet=self.entry.get("sheet_name"),
                    source_table=table_name,
                    import_timestamp_utc=None,
                )
            )
        frame = pd.concat(parts, ignore_index=True)
        sort_cols = [c for c in ("collection_id", "record_id", "source_row") if c in frame.columns]
        if sort_cols:
            frame = frame.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
        # Explicit Pydantic validation (does not invent values)
        for row in frame.to_dict(orient="records"):
            CanonicalRecord.model_validate(row)
        return frame

    def validate_schema(self, data: pd.DataFrame) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}
        rules = self.schema.get("validation") or {}
        allowed_techniques = set(rules.get("allowed_techniques") or [])
        allowed_dynamics = set(rules.get("allowed_dynamics") or [])

        for col in PHASE1_REQUIRED_COLUMNS:
            if col not in data.columns:
                errors.append(f"Missing canonical column: {col}")

        if "density_value" in data.columns and (data["density_value"] == 0).any():
            details["n_zero_density"] = int((data["density_value"] == 0).sum())

        details["allowed_instruments"] = sorted(ALLOWED_INSTRUMENTS)
        unsupported = []
        if "instrument_mapping_status" in data.columns:
            mask = data["instrument_mapping_status"] == UNSUPPORTED_STATUS
            if mask.any() and "original_instrument_label" in data.columns:
                unsupported = sorted(
                    {str(v) for v in data.loc[mask, "original_instrument_label"].dropna().unique()}
                )
            details["n_unsupported_instruments"] = int(mask.sum())
        if unsupported:
            warnings.append(
                "Unsupported instruments outside project scope "
                f"(retained only in rejection report): {unsupported}"
            )
            details["unsupported_instruments"] = unsupported

        invalid_techniques = []
        if allowed_techniques and "technique" in data.columns:
            for val in data["technique"].dropna().unique():
                if str(val) not in allowed_techniques:
                    invalid_techniques.append(str(val))
        if invalid_techniques:
            warnings.append(f"Invalid / unmapped technique values: {sorted(set(invalid_techniques))}")
            details["invalid_techniques"] = sorted(set(invalid_techniques))

        if allowed_dynamics and "dynamic" in data.columns:
            bad_dyn = sorted(
                {str(v) for v in data["dynamic"].dropna().unique() if str(v) not in allowed_dynamics}
            )
            if bad_dyn:
                warnings.append(f"Unexpected dynamic labels: {bad_dyn}")
                details["invalid_dynamics"] = bad_dyn

        n_dup = int(data.duplicated(subset=["record_id"]).sum()) if "record_id" in data.columns else 0
        if n_dup:
            warnings.append(f"{n_dup} duplicate record_id values.")
            details["duplicate_record_ids"] = n_dup
            details["duplicate_ids"] = (
                data.loc[data.duplicated(subset=["record_id"], keep=False), "record_id"]
                .astype(str)
                .unique()
                .tolist()
            )

        if "technique_mapping_status" in data.columns:
            details["unmapped_techniques"] = int((data["technique_mapping_status"] == "unmapped").sum())

        # Missing density must remain null — never zero-filled
        if "density_value" in data.columns:
            details["n_missing_density"] = int(data["density_value"].isna().sum())
            details["n_density_present"] = int(data["density_value"].notna().sum())

        return ValidationReport(
            collection_id=self.collection_id,
            ok=not errors,
            errors=errors,
            warnings=warnings,
            n_records=int(len(data)),
            details=details,
        )

    def validate_metric_compatibility(
        self,
        data: pd.DataFrame,
        metric_registry: MetricRegistry,
        target_metric_definition_id: str,
    ) -> CompatibilityReport:
        metrics = sorted({str(x) for x in data["metric_definition_id"].dropna().unique()})
        per: dict[str, str] = {}
        statuses = []
        reasons = []
        for mid in metrics:
            if mid not in metric_registry.definitions:
                per[mid] = "unknown"
                statuses.append("unknown")
                reasons.append(f"Unknown metric_definition_id: {mid}")
                continue
            result = metric_registry.compare(mid, target_metric_definition_id)
            per[mid] = result.status
            statuses.append(result.status)
            reasons.append(result.reason)

        if not statuses:
            status, reason = "unknown", "No metric_definition_id values present."
        elif any(s == "incompatible" for s in statuses):
            status, reason = "incompatible", "; ".join(reasons)
        elif any(s == "unknown" for s in statuses):
            status, reason = "unknown", "; ".join(reasons)
        elif all(s == "identical" for s in statuses):
            status, reason = "identical", "All known records use the target metric definition."
        else:
            status, reason = statuses[0], "; ".join(reasons)

        return CompatibilityReport(
            collection_id=self.collection_id,
            target_metric_definition_id=target_metric_definition_id,
            status=status,
            reason=reason,
            n_records=int(len(data)),
            per_metric_status=per,
            required_conversion=None,
            uncertainty_introduced=None,
            allowed_operations=["import", "validate", "compare", "export_canonical"],
            prohibited_operations=[
                "silent_minmax",
                "silent_zscore",
                "silent_rescale",
                "silent_unit_conversion",
                "silent_average",
                "missing_to_zero",
            ],
        )

    def export_canonical(self, data: pd.DataFrame, output_dir: Path | str) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.collection_id}.parquet"
        sort_cols = [c for c in ("collection_id", "record_id", "source_row") if c in data.columns]
        export = (
            data.sort_values(sort_cols, kind="mergesort").reset_index(drop=True) if sort_cols else data
        )
        export.to_parquet(path, index=False)
        return path

    def assert_sources_unchanged(self) -> None:
        paths = [resolve_path(p, self.root) for p in self.entry.get("data_paths") or []]
        after = [file_fingerprint(p) for p in paths if p.exists()]
        if self._source_fingerprints_before and after != self._source_fingerprints_before:
            raise RuntimeError(
                f"Source files for {self.collection_id} changed during import; "
                "loaders must not alter originals."
            )

    def enrich(
        self,
        canonical: pd.DataFrame,
        metric_registry: MetricRegistry,
        target_metric_definition_id: str,
    ) -> pd.DataFrame:
        role = self._default_roles()[0] if self._default_roles() else None
        return annotate_quality(
            canonical,
            metric_registry=metric_registry,
            target_metric_definition_id=target_metric_definition_id,
            default_role=role,
        )

    def quality_summary(self, enriched: pd.DataFrame) -> dict[str, Any]:
        return summarize_quality(enriched)
