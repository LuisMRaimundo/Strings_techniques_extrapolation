"""Deterministic prediction run manifests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from string_technique_model import __version__
from string_technique_model.stable_seed import stable_hex


def build_run_id(
    *,
    baseline_run_id: str | None,
    instruments: list[str],
    techniques: list[str],
    backend: str,
    seed: int,
    n_draws: int,
    ledger_checksum: str,
    matrix_checksum: str,
) -> str:
    return "PRED_" + stable_hex(
        baseline_run_id or "",
        ",".join(sorted(instruments)),
        ",".join(sorted(techniques)),
        backend,
        seed,
        n_draws,
        ledger_checksum,
        matrix_checksum,
        n_chars=16,
    )


def file_checksum(path: Path) -> str:
    if not path.exists():
        return "missing"
    return stable_hex(path.read_bytes().hex() if path.stat().st_size < 2_000_000 else path.name, n_chars=16)


def write_run_manifest(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Timestamp is recorded but must not enter run_id
    payload = dict(payload)
    payload.setdefault("software_version", __version__)
    payload.setdefault("created_at_utc", datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
