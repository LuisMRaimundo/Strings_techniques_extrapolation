from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = PACKAGE_ROOT / "configs" / "run.yaml"


def load_yaml(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def resolve_path(path: Path | str, root: Path | None = None) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return (root or PACKAGE_ROOT) / path


def load_run_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg = load_yaml(path or DEFAULT_RUN)
    paths = cfg.get("paths", {})
    resolved = {}
    for key, value in paths.items():
        resolved[key] = str(resolve_path(value))
    cfg["paths_resolved"] = resolved
    return cfg
