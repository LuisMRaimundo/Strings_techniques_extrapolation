"""I/O utilities including Parquet preflight."""

from string_technique_model.io.parquet_preflight import (
    PreflightResult,
    check_parquet_engine,
    require_parquet_engine,
)

__all__ = [
    "PreflightResult",
    "check_parquet_engine",
    "require_parquet_engine",
]
