"""Deterministic baseline run IDs and manifests."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from string_technique_model import __version__
from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.stable_seed import stable_hex


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def config_checksum(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_run_id(
    *,
    collection_ids: list[str],
    source_checksums: dict[str, str],
    schema_versions: dict[str, str],
    metric_definition_id: str,
    conversion_registry_version: str,
    alignment_key: list[str],
    pooling_method: str,
    pooling_parameters: dict[str, Any],
    instruments: list[str],
    dynamics: list[str],
    seed: int | None,
) -> str:
    """Deterministic run ID — must not include current timestamp."""
    payload = {
        "collections": sorted(collection_ids),
        "source_checksums": source_checksums,
        "schema_versions": schema_versions,
        "metric_definition_id": metric_definition_id,
        "conversion_registry_version": conversion_registry_version,
        "alignment_key": list(alignment_key),
        "pooling_method": pooling_method,
        "pooling_parameters": pooling_parameters,
        "instruments": sorted(instruments),
        "dynamics": list(dynamics),
        "seed": seed,
    }
    return f"baseline_{stable_hex(json.dumps(payload, sort_keys=True, default=str), n_chars=24)}"


def dependency_versions() -> dict[str, str]:
    names = ["numpy", "pandas", "scipy", "pyyaml", "pyarrow", "pydantic", "openpyxl"]
    out: dict[str, str] = {}
    for name in names:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "unknown"
    return out


def write_run_manifest(
    path: Path,
    *,
    run_id: str,
    collection_ids: list[str],
    excluded_collections: list[str],
    metric_definition_id: str,
    alignment_key: list[str],
    pooling_method: str,
    weights: dict[str, float],
    seed: int | None,
    source_checksums: dict[str, str],
    configuration_checksums: dict[str, str],
    output_files: dict[str, str],
    warnings: list[str],
) -> dict[str, Any]:
    manifest = {
        "run_id": run_id,
        "software_version": __version__,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "dependency_versions": dependency_versions(),
        "source_file_checksums": source_checksums,
        "configuration_checksums": configuration_checksums,
        "selected_collections": list(collection_ids),
        "excluded_collections": list(excluded_collections),
        "metric_definition": metric_definition_id,
        "alignment_key": list(alignment_key),
        "pooling_method": pooling_method,
        "weights": weights,
        "seed": seed,
        "output_files": output_files,
        "warnings": warnings,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "package_root": str(PACKAGE_ROOT),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
