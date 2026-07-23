"""Explicit technique and dynamic mapping (no fuzzy auto-mapping)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from string_technique_model.manual_entry.constants import CANONICAL_DYNAMICS, CANONICAL_TECHNIQUES
from string_technique_model.stable_seed import stable_hex


@dataclass
class MappingRecord:
    original_label: str
    canonical_code: str | None
    mapping_status: str
    justification: str | None
    user: str | None
    timestamp_utc: str
    mapping_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_label": self.original_label,
            "canonical_code": self.canonical_code,
            "mapping_status": self.mapping_status,
            "justification": self.justification,
            "user": self.user,
            "timestamp_utc": self.timestamp_utc,
            "mapping_version": self.mapping_version,
        }


# Explicit only — never flautando→sul_tasto, natural→artificial, etc.
DEFAULT_TECHNIQUE_MAP: dict[str, str] = {
    "ordinary": "ordinary",
    "ordinario": "ordinary",
    "ordinario arco": "ordinary",
    "arco": "ordinary",
    "artificial_harmonic": "artificial_harmonic",
    "artificial harmonic": "artificial_harmonic",
    "artificial harmonics": "artificial_harmonic",
    "harmonics artificial": "artificial_harmonic",
    "sul_ponticello": "sul_ponticello",
    "sul ponticello": "sul_ponticello",
    "ponticello": "sul_ponticello",
    "sul_tasto": "sul_tasto",
    "sul tasto": "sul_tasto",
    "tastiera": "sul_tasto",
    "con_sordino": "con_sordino",
    "con sordino": "con_sordino",
    "con sord.": "con_sordino",
    "muted": "con_sordino",
}

DEFAULT_DYNAMIC_MAP: dict[str, str] = {
    d: d for d in sorted(CANONICAL_DYNAMICS)
}


def _norm(label: str) -> str:
    return " ".join(str(label).strip().lower().split())


class MappingService:
    def __init__(self) -> None:
        self.technique_maps: dict[str, MappingRecord] = {}
        self.dynamic_maps: dict[str, MappingRecord] = {}
        # seed defaults
        for src, dst in DEFAULT_TECHNIQUE_MAP.items():
            self.technique_maps[_norm(src)] = MappingRecord(
                original_label=src,
                canonical_code=dst,
                mapping_status="mapped",
                justification="built_in_explicit_alias",
                user="system",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )
        for src, dst in DEFAULT_DYNAMIC_MAP.items():
            self.dynamic_maps[_norm(src)] = MappingRecord(
                original_label=src,
                canonical_code=dst,
                mapping_status="mapped",
                justification="built_in_canonical",
                user="system",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )

    def map_technique(self, label: str | None) -> MappingRecord:
        if label is None or not str(label).strip():
            return MappingRecord(
                original_label="",
                canonical_code=None,
                mapping_status="unmapped",
                justification="empty_label",
                user=None,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )
        key = _norm(label)
        if key in self.technique_maps:
            return self.technique_maps[key]
        # exact canonical code
        if str(label).strip() in CANONICAL_TECHNIQUES:
            return MappingRecord(
                original_label=str(label).strip(),
                canonical_code=str(label).strip(),
                mapping_status="mapped",
                justification="canonical_code",
                user="system",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )
        return MappingRecord(
            original_label=str(label).strip(),
            canonical_code=None,
            mapping_status="unmapped",
            justification=None,
            user=None,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            mapping_version="v1",
        )

    def map_dynamic(self, label: str | None) -> MappingRecord:
        if label is None or not str(label).strip():
            return MappingRecord(
                original_label="",
                canonical_code=None,
                mapping_status="unmapped",
                justification="empty_label_not_defaulted_to_mf",
                user=None,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )
        key = _norm(label)
        if key in self.dynamic_maps:
            return self.dynamic_maps[key]
        if str(label).strip() in CANONICAL_DYNAMICS:
            return MappingRecord(
                original_label=str(label).strip(),
                canonical_code=str(label).strip(),
                mapping_status="mapped",
                justification="canonical_code",
                user="system",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                mapping_version="v1",
            )
        return MappingRecord(
            original_label=str(label).strip(),
            canonical_code=None,
            mapping_status="unmapped",
            justification=None,
            user=None,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            mapping_version="v1",
        )

    def register_technique_mapping(
        self,
        original_label: str,
        canonical_code: str,
        *,
        justification: str,
        user: str,
    ) -> MappingRecord:
        if canonical_code not in CANONICAL_TECHNIQUES:
            raise ValueError(f"canonical technique not allowed: {canonical_code}")
        # Forbid silent forbidden equivalences unless explicitly justified and registered
        forbidden_pairs = {
            ("flautando", "sul_tasto"),
            ("natural_harmonic", "artificial_harmonic"),
            ("natural harmonic", "artificial_harmonic"),
        }
        if (_norm(original_label), canonical_code) in forbidden_pairs and "explicit" not in justification.lower():
            raise ValueError(
                "Forbidden automatic equivalence; justification must contain 'explicit' "
                "and user must intentionally register the mapping."
            )
        rec = MappingRecord(
            original_label=original_label,
            canonical_code=canonical_code,
            mapping_status="mapped",
            justification=justification,
            user=user,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            mapping_version="v1_" + stable_hex(original_label, canonical_code, n_chars=6),
        )
        self.technique_maps[_norm(original_label)] = rec
        return rec

    def register_dynamic_mapping(
        self,
        original_label: str,
        canonical_code: str,
        *,
        justification: str,
        user: str,
    ) -> MappingRecord:
        if canonical_code not in CANONICAL_DYNAMICS:
            raise ValueError(f"canonical dynamic not allowed: {canonical_code}")
        rec = MappingRecord(
            original_label=original_label,
            canonical_code=canonical_code,
            mapping_status="mapped",
            justification=justification,
            user=user,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            mapping_version="v1_" + stable_hex(original_label, canonical_code, n_chars=6),
        )
        self.dynamic_maps[_norm(original_label)] = rec
        return rec
