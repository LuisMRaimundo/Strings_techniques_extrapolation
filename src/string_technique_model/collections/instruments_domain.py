"""Strict four-instrument domain for orchestral bowed strings."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from string_technique_model.config import PACKAGE_ROOT, load_yaml

ALLOWED_INSTRUMENTS: frozenset[str] = frozenset({"vln", "vla", "vlc", "cb"})

DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "vln": ("vln", "vn", "violin", "violino", "violon"),
    "vla": ("vla", "va", "viola"),
    "vlc": ("vlc", "vc", "cello", "violoncello", "violoncelo"),
    "cb": (
        "cb",
        "db",
        "double bass",
        "double_bass",
        "double-bass",
        "contrabass",
        "contrabasso",
        "contrabaixo",
    ),
}

EXCLUSION_REASON_UNSUPPORTED = "instrument_outside_project_scope"
UNSUPPORTED_STATUS = "unsupported_instrument"


def _normalize_key(label: str) -> str:
    return " ".join(str(label).strip().lower().split())


@lru_cache(maxsize=1)
def _alias_lookup() -> dict[str, str]:
    path = PACKAGE_ROOT / "configs" / "instrument_domain.yaml"
    # Start from code defaults, then extend with YAML (YAML cannot drop defaults).
    aliases: dict[str, tuple[str, ...]] = {k: tuple(v) for k, v in DEFAULT_ALIASES.items()}
    if path.exists():
        data = load_yaml(path)
        configured = data.get("instrument_aliases") or {}
        for code, labels in configured.items():
            if code in ALLOWED_INSTRUMENTS and labels:
                merged = list(aliases.get(str(code), ()))
                for label in labels:
                    if str(label) not in merged:
                        merged.append(str(label))
                aliases[str(code)] = tuple(merged)
    lookup: dict[str, str] = {}
    for code, labels in aliases.items():
        if code not in ALLOWED_INSTRUMENTS:
            continue
        for label in labels:
            lookup[_normalize_key(label)] = code
        lookup[_normalize_key(code)] = code
    return lookup


def normalize_instrument_label(label: Any) -> str | None:
    """Map a source label to vln/vla/vlc/cb, or None if unsupported.

    Exact alias match only (case-insensitive, whitespace-trimmed).
    No fuzzy matching and no ambiguous abbreviation inference.
    """
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    try:
        if pd.isna(label):
            return None
    except Exception:
        pass
    text = str(label).strip()
    if not text:
        return None
    if text in ALLOWED_INSTRUMENTS:
        return text
    return _alias_lookup().get(_normalize_key(text))


def is_allowed_instrument(code: Any) -> bool:
    return bool(code is not None and not pd.isna(code) and str(code) in ALLOWED_INSTRUMENTS)


def apply_instrument_domain(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize instrument labels and mark out-of-scope rows."""
    out = frame.copy()
    if "instrument" not in out.columns:
        out["original_instrument_label"] = pd.NA
        out["instrument_mapping_status"] = "missing"
        out["exclusion_reason"] = pd.NA
        return out

    originals: list[Any] = []
    codes: list[Any] = []
    statuses: list[str] = []
    exclusions: list[Any] = []

    for val in out["instrument"]:
        originals.append(val if not (val is None or pd.isna(val)) else pd.NA)
        if val is None or pd.isna(val) or str(val).strip() == "":
            codes.append(pd.NA)
            statuses.append("missing")
            exclusions.append(pd.NA)
            continue
        mapped = normalize_instrument_label(val)
        if mapped is None:
            codes.append(pd.NA)
            statuses.append(UNSUPPORTED_STATUS)
            exclusions.append(EXCLUSION_REASON_UNSUPPORTED)
        else:
            codes.append(mapped)
            statuses.append("mapped")
            exclusions.append(pd.NA)

    out["original_instrument_label"] = originals
    out["instrument"] = codes
    out["instrument_mapping_status"] = statuses
    out["exclusion_reason"] = exclusions
    return out


def split_supported_instruments(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (accepted, rejected) by strict instrument domain."""
    if frame is None or len(frame) == 0:
        empty = frame.copy() if frame is not None else pd.DataFrame()
        return empty, empty
    supported = frame["instrument"].isin(list(ALLOWED_INSTRUMENTS))
    if "instrument_mapping_status" in frame.columns:
        supported = supported & (frame["instrument_mapping_status"] != UNSUPPORTED_STATUS)
    return frame.loc[supported].copy(), frame.loc[~supported].copy()


def rejected_records_table(rejected: pd.DataFrame, *, import_timestamp_utc: str) -> pd.DataFrame:
    """Build the provenance rejection CSV frame."""
    columns = [
        "collection_id",
        "source_file",
        "source_row",
        "original_instrument_label",
        "rejection_reason",
        "import_timestamp_utc",
        "schema_mapping_version",
    ]
    if rejected is None or len(rejected) == 0:
        return pd.DataFrame(columns=columns)
    rows = pd.DataFrame(
        {
            "collection_id": rejected["collection_id"] if "collection_id" in rejected else pd.NA,
            "source_file": rejected["source_file"] if "source_file" in rejected else pd.NA,
            "source_row": rejected["source_row"] if "source_row" in rejected else pd.NA,
            "original_instrument_label": rejected["original_instrument_label"]
            if "original_instrument_label" in rejected
            else rejected.get("instrument"),
            "rejection_reason": rejected["exclusion_reason"]
            if "exclusion_reason" in rejected
            else EXCLUSION_REASON_UNSUPPORTED,
            "import_timestamp_utc": import_timestamp_utc,
            "schema_mapping_version": rejected["schema_mapping_version"]
            if "schema_mapping_version" in rejected
            else pd.NA,
        }
    )
    rows["rejection_reason"] = rows["rejection_reason"].fillna(EXCLUSION_REASON_UNSUPPORTED)
    rows["schema_mapping_version"] = rows["schema_mapping_version"].map(
        lambda v: "" if pd.isna(v) else str(v)
    )
    return rows[columns]
