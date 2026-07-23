"""Typed literature oracles — never invent experimental reference values."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.source_identity import load_source_identity_registry

ExpectedOutputType = Literal[
    "exact",
    "interval",
    "approximate_interval",
    "monotonic_direction",
    "rank_order",
    "non_equivalence",
    "categorical_distinction",
    "applicability_only",
    "unsupported_for_numerical_test",
]

OracleType = Literal[
    "empirical",
    "historical",
    "secondary_synthesis",
    "literature_bounded",
    "analytical_identity",
    "performance_practice",
]

ProvenanceType = Literal[
    "primary_experimental_evidence",
    "secondary_synthesis",
    "historical_source",
    "performance_practice_source",
    "first_principles",
    "unresolved",
]

_SOURCE_REQUIRED_ORACLE_TYPES = frozenset(
    {
        "empirical",
        "historical",
        "secondary_synthesis",
        "literature_bounded",
        "performance_practice",
    }
)

_SOURCE_REQUIRED_SOURCE_TYPES = frozenset(
    {
        "primary_experimental_evidence",
        "secondary_synthesis",
        "historical_source",
        "performance_practice_source",
        "peer_reviewed_journal",
        "peer_reviewed_conference",
        "book_chapter",
        "specialised_musical_acoustics_monograph",
        "edited_specialised_monograph",
    }
)


class LiteratureBenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    benchmark_case_id: str
    source_id: str | None = None
    citation: str | None = None
    DOI: str | None = None
    page_or_figure: str | None = None
    source_type: str | None = None
    oracle_type: OracleType | None = None
    provenance_type: ProvenanceType | None = None
    source_required: bool | None = None
    instrument: str | None = None
    string: str | None = None
    technique: str | None = None
    measurement_domain: str | None = None
    recording_or_measurement_setup: str | None = None
    input_variables: dict[str, Any] = Field(default_factory=dict)
    expected_output_type: ExpectedOutputType
    expected: dict[str, Any] = Field(default_factory=dict)
    tolerance_id: str | None = None
    transferability: str | None = None
    direct_numerical_comparison_allowed: bool = False
    known_limitations: str | None = None

    @model_validator(mode="after")
    def _resolve_source_required(self) -> LiteratureBenchmarkCase:
        if self.source_required is not None:
            return self
        if self.oracle_type == "analytical_identity" or self.provenance_type == "first_principles":
            self.source_required = False
        elif self.oracle_type in _SOURCE_REQUIRED_ORACLE_TYPES:
            self.source_required = True
        elif self.source_type in _SOURCE_REQUIRED_SOURCE_TYPES:
            self.source_required = True
        else:
            # Default: require source unless explicitly first-principles
            self.source_required = self.source_id is not None or self.oracle_type != "analytical_identity"
        return self

    def is_first_principles(self) -> bool:
        return self.oracle_type == "analytical_identity" or self.provenance_type == "first_principles"


def load_literature_benchmark_cases(
    path: Path | str | None = None,
) -> list[LiteratureBenchmarkCase]:
    data = load_yaml(resolve_path(path or PACKAGE_ROOT / "configs" / "literature_benchmark_cases.yaml"))
    return [LiteratureBenchmarkCase.model_validate(item) for item in (data.get("cases") or [])]


def validate_benchmark_sources_against_identity(
    cases: list[LiteratureBenchmarkCase] | None = None,
) -> dict[str, Any]:
    """Validate benchmark cases.

    ``source_id`` is required for empirical/historical/secondary/literature-bounded cases.
    Explicit first-principles analytical identities may omit ``source_id``.
    """
    cases = cases or load_literature_benchmark_cases()
    identity = load_source_identity_registry()
    rejected_ids = {
        e.associated_source_id
        for e in identity.list_entries()
        if e.validation_status
        in {"rejected_file_identity_mismatch", "duplicate_file", "insufficient_metadata"}
        and e.associated_source_id
    }
    bad_entry_ids = {e.entry_id for e in identity.rejected()}
    errors: list[str] = []
    warnings: list[str] = []
    for case in cases:
        requires_source = bool(case.source_required)
        if case.is_first_principles() and case.source_required is False:
            requires_source = False

        if requires_source and not case.source_id:
            errors.append(
                f"{case.benchmark_case_id}: source_id required for "
                f"oracle_type={case.oracle_type!r} / source_type={case.source_type!r}"
            )
            continue

        if not requires_source and case.source_id is None:
            # Explicit analytical identity — no warning
            continue

        if case.source_id is None:
            errors.append(f"{case.benchmark_case_id}: missing source_id")
            continue

        if case.source_id in rejected_ids:
            errors.append(f"{case.benchmark_case_id}: source_id {case.source_id} is rejected/duplicate")
        matches = [e for e in identity.list_entries() if e.associated_source_id == case.source_id]
        if matches and not any(
            e.validation_status in {"verified_identity", "partial_identity_match"} for e in matches
        ):
            errors.append(
                f"{case.benchmark_case_id}: no verified/partial identity for {case.source_id}"
            )
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "n_cases": len(cases),
        "rejected_entry_ids": sorted(bad_entry_ids),
    }


def physics_oracle_sounding_hz(f_stopped_hz: float, harmonic_order: int) -> float:
    """First-principles identity: f_n = n × f_0.

    Not a production API for filling ProductionInstruction sounding fields.
    """
    if harmonic_order <= 0:
        raise ValueError("harmonic_order must be positive")
    if f_stopped_hz <= 0:
        raise ValueError("f_stopped_hz must be positive")
    return float(harmonic_order) * float(f_stopped_hz)
