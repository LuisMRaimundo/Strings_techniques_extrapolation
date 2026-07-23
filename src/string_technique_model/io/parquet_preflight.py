"""Parquet engine preflight checks for collection import outputs."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    engine_name: str | None
    error_message: str | None
    actionable_hint: str | None


def check_parquet_engine() -> PreflightResult:
    """
    Verify that Parquet read/write is available.

    Parquet is **mandatory** for collection import outputs. Prediction pipelines
    may fall back to other formats when Parquet is unavailable, but must emit an
    explicit warning when doing so.
    """
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        return PreflightResult(
            ok=False,
            engine_name=None,
            error_message=str(exc),
            actionable_hint="Install pyarrow: pip install 'pyarrow>=14.0,<20'",
        )

    try:
        frame = pd.DataFrame({"probe": [1]})
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            frame.to_parquet(tmp_path, engine="pyarrow", index=False)
            pd.read_parquet(tmp_path, engine="pyarrow")
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover - environment-specific
        return PreflightResult(
            ok=False,
            engine_name="pyarrow",
            error_message=str(exc),
            actionable_hint=(
                "PyArrow is installed but Parquet I/O failed; reinstall pyarrow "
                "or check filesystem permissions."
            ),
        )

    return PreflightResult(
        ok=True,
        engine_name="pyarrow",
        error_message=None,
        actionable_hint=None,
    )


def require_parquet_engine() -> str:
    """Raise ``RuntimeError`` once if Parquet is unavailable."""
    result = check_parquet_engine()
    if not result.ok:
        hint = result.actionable_hint or "Install pyarrow."
        raise RuntimeError(
            f"Parquet engine unavailable ({result.error_message}). {hint} "
            "Parquet is mandatory for collection import outputs."
        )
    assert result.engine_name is not None
    return result.engine_name
