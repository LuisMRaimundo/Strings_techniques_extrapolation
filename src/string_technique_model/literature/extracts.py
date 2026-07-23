"""Evidence extract loading, IDs, and deduplication."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.domain import (
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
    DIRECTNESS_VALUES,
    EXTRACT_VERIFICATION_STATUSES,
)
from string_technique_model.stable_seed import stable_hex


class EvidenceExtract(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    evidence_id: str | None = None
    source_id: str
    instrument: str | None = None
    technique: str | None = None
    evidence_scope: str | None = None
    page_start: int | str | None = None
    page_end: int | str | None = None
    table_number: str | None = None
    figure_number: str | None = None
    equation_number: str | None = None
    section_title: str | None = None
    original_variable_name: str | None = None
    canonical_variable_name: str | None = None
    quoted_fragment: str | None = None
    paraphrased_claim: str
    quantitative_or_qualitative: str
    reported_value: float | None = None
    reported_lower_bound: float | None = None
    reported_upper_bound: float | None = None
    reported_mean: float | None = None
    reported_median: float | None = None
    reported_sd: float | None = None
    reported_se: float | None = None
    reported_ci_lower: float | None = None
    reported_ci_upper: float | None = None
    reported_sample_size: int | None = None
    original_unit: str | None = None
    canonical_unit: str | None = None
    amplitude_or_power: str | None = None
    linear_or_decibel: str | None = None
    frequency_range_hz: str | None = None
    pitch_range: str | None = None
    pitch_register: str | None = Field(default=None, alias="register")
    dynamic: str | None = None
    string_name: str | None = None
    bow_position: str | None = None
    mute_type: str | None = None
    mute_mass: str | float | None = None
    harmonic_type: str | None = None
    harmonic_order: int | None = None
    temporal_region: str | None = None
    recording_condition: str | None = None
    directness: str
    extraction_method: str | None = None
    extraction_confidence: str | None = None
    curator_verification_status: str = "unverified"
    curator_notes: str | None = None
    related_technique_note: str | None = None
    evidence_last_evaluated_utc: str | None = None
    density_mapping_status: str | None = None
    operation_type: str | None = None
    numerical_scale: str | None = None

    @field_validator("directness")
    @classmethod
    def _directness_ok(cls, value: str) -> str:
        if value not in DIRECTNESS_VALUES:
            raise ValueError(f"Invalid directness: {value}")
        return value

    @field_validator("curator_verification_status")
    @classmethod
    def _verification_ok(cls, value: str) -> str:
        status = str(value or "unverified").lower()
        if status not in EXTRACT_VERIFICATION_STATUSES:
            raise ValueError(f"Invalid curator_verification_status: {value}")
        return status

    def is_validated(self) -> bool:
        return self.curator_verification_status == "validated"

    def has_location(self) -> bool:
        return any(
            [
                self.page_start is not None,
                self.table_number,
                self.figure_number,
                self.equation_number,
                self.section_title,
            ]
        )

    def is_quantitative(self) -> bool:
        return str(self.quantitative_or_qualitative).lower().startswith("quant")

    def fingerprint_parts(self) -> list[str]:
        return [
            str(self.source_id),
            str(self.page_start or ""),
            str(self.page_end or ""),
            str(self.table_number or ""),
            str(self.figure_number or ""),
            str(self.equation_number or ""),
            str(self.section_title or ""),
            str(self.canonical_variable_name or self.original_variable_name or ""),
            str(self.instrument or ""),
            str(self.technique or ""),
            str(self.paraphrased_claim or "")[:200],
        ]

    def assign_deterministic_id(self) -> str:
        eid = f"EVIDENCE_{stable_hex(*self.fingerprint_parts(), n_chars=12)}"
        self.evidence_id = eid
        return eid


def load_extracts(path: Path | str | None = None) -> list[EvidenceExtract]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_evidence_extracts.yaml")
    data = load_yaml(path)
    raw = data.get("extracts") or []
    extracts: list[EvidenceExtract] = []
    seen: set[str] = set()
    for item in raw:
        ext = EvidenceExtract.model_validate(item)
        if ext.instrument is not None and str(ext.instrument).strip() not in {"", "null", "None"}:
            if ext.instrument not in ALLOWED_INSTRUMENTS:
                raise ValueError(f"Extract instrument outside domain: {ext.instrument}")
        else:
            ext.instrument = None
        if ext.technique and ext.technique not in ALLOWED_TECHNIQUES:
            if ext.technique != "natural_harmonic":
                raise ValueError(f"Extract technique outside domain: {ext.technique}")
        # Prefer curated evidence_id when provided; else deterministic.
        if not ext.evidence_id:
            ext.assign_deterministic_id()
        eid = str(ext.evidence_id)
        if eid in seen:
            continue  # idempotent: skip duplicates
        seen.add(eid)
        extracts.append(ext)
    return extracts


def extracts_to_rows(extracts: list[EvidenceExtract]) -> list[dict[str, Any]]:
    return [e.model_dump(by_alias=True) for e in extracts]
