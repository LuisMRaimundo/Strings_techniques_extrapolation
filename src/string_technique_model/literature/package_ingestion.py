"""Ingest and validate the curated literature-evidence package.

Curated YAML/CSV files are the scientific source of truth.
Python must not invent acoustic coefficients or technique-density predictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.activation import (
    ActivationDecision,
    ApplicabilityQuery,
    evaluate_all_parameters,
)
from string_technique_model.literature.density_mapping import load_density_mappings, mapping_matrix_rows
from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES
from string_technique_model.literature.evidence_matrix import (
    build_evidence_matrix,
    enrich_matrix_parameter_counts,
    serialize_matrix_row_for_csv,
)
from string_technique_model.literature.extracts import EvidenceExtract, load_extracts
from string_technique_model.literature.outputs import write_csv, write_text
from string_technique_model.literature.package_models import (
    DensityMappingModel,
    EvidenceExtractModel,
    LiteratureParameterModel,
    LiteratureSourceModel,
    PhysicalMechanismModel,
)
from string_technique_model.literature.parameter_ledger import load_parameter_config
from string_technique_model.literature.source_registry import SourceRegistry


@dataclass
class PackageIngestionResult:
    validated_sources: list[dict[str, Any]] = field(default_factory=list)
    rejected_sources: list[dict[str, Any]] = field(default_factory=list)
    validated_extracts: list[dict[str, Any]] = field(default_factory=list)
    rejected_extracts: list[dict[str, Any]] = field(default_factory=list)
    candidate_parameters: list[dict[str, Any]] = field(default_factory=list)
    active_parameters: list[dict[str, Any]] = field(default_factory=list)
    inactive_parameters: list[dict[str, Any]] = field(default_factory=list)
    activation_failures: list[dict[str, Any]] = field(default_factory=list)
    rebuilt_matrix: list[dict[str, Any]] = field(default_factory=list)
    mechanisms: list[dict[str, Any]] = field(default_factory=list)
    unsupported_parameters: list[dict[str, Any]] = field(default_factory=list)
    density_mappings: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[ActivationDecision] = field(default_factory=list)
    output_files: dict[str, str] = field(default_factory=dict)
    density_prediction_produced: bool = False
    summary: dict[str, Any] = field(default_factory=dict)


def load_physical_mechanisms(path: Path | str | None = None) -> list[dict[str, Any]]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "physical_mechanisms.yaml")
    data = load_yaml(path)
    rows: list[dict[str, Any]] = []
    models = data.get("instrument_technique_models") or {}
    for instrument, techniques in models.items():
        if instrument not in ALLOWED_INSTRUMENTS:
            raise ValueError(f"Mechanism instrument outside domain: {instrument}")
        for technique, payload in (techniques or {}).items():
            if technique not in ALLOWED_TECHNIQUES:
                raise ValueError(f"Mechanism technique outside domain: {technique}")
            mechs = (payload or {}).get("mechanisms") or {}
            for name, body in mechs.items():
                if name == "numerical_parameter_status" and not isinstance(body, dict):
                    continue
                if not isinstance(body, dict):
                    continue
                model = PhysicalMechanismModel(
                    instrument=instrument,
                    technique=technique,
                    mechanism_name=name,
                    supported=body.get("supported", False),
                    status=str(body.get("status") or "unsupported"),
                    evidence_ids=list(body.get("evidence_ids") or []),
                    reason=body.get("reason"),
                    numerical_parameter_status=body.get("numerical_parameter_status"),
                )
                rows.append(model.model_dump())
    return rows


def extract_package_row(ext: EvidenceExtract) -> dict[str, Any]:
    return {
        "evidence_id": ext.evidence_id,
        "source_id": ext.source_id,
        "instrument": ext.instrument,
        "technique": ext.technique,
        "page_start": ext.page_start,
        "page_end": ext.page_end,
        "canonical_variable": ext.canonical_variable_name or ext.original_variable_name,
        "reported_value": ext.reported_value,
        "unit": ext.canonical_unit or ext.original_unit,
        "operation_type": getattr(ext, "operation_type", None)
        or (
            "range_constraint"
            if ext.reported_lower_bound is not None and ext.reported_upper_bound is not None
            else ("decibel_gain" if (ext.canonical_unit or "") == "dB" else None)
        ),
        "directness": ext.directness,
        "density_mapping_status": getattr(ext, "density_mapping_status", None),
        "quantitative_or_qualitative": ext.quantitative_or_qualitative,
        "curator_verification_status": ext.curator_verification_status,
        "section_title": ext.section_title,
        "mute_type": ext.mute_type,
        "harmonic_type": ext.harmonic_type,
    }


def _validate_source(src_model: LiteratureSourceModel) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if src_model.evidence_status in {"excluded", "incomplete_reference"}:
        reasons.append(src_model.evidence_status)
    for inst in src_model.instruments_covered:
        # allow empty; reject unknown codes
        key = str(inst).strip().lower()
        mapping = {
            "violin": "vln",
            "vln": "vln",
            "viola": "vla",
            "vla": "vla",
            "cello": "vlc",
            "violoncello": "vlc",
            "vlc": "vlc",
            "double_bass": "cb",
            "cb": "cb",
            "contrabass": "cb",
        }
        if key and key not in mapping and key not in ALLOWED_INSTRUMENTS:
            reasons.append(f"unsupported_instrument:{inst}")
    for tech in src_model.techniques_covered:
        if tech and tech not in ALLOWED_TECHNIQUES:
            reasons.append(f"unsupported_technique:{tech}")
    return (len(reasons) == 0), reasons


def _validate_extract(
    ext: EvidenceExtract,
    registry: SourceRegistry,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    try:
        EvidenceExtractModel.model_validate(
            {
                **ext.model_dump(by_alias=True),
                "evidence_id": ext.evidence_id,
                "density_mapping_status": getattr(ext, "density_mapping_status", None),
            }
        )
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"schema:{exc}")
    if ext.source_id not in registry.sources:
        reasons.append("unknown_source")
    if ext.instrument is not None and ext.instrument not in ALLOWED_INSTRUMENTS:
        reasons.append("unsupported_instrument")
    if ext.technique is not None and ext.technique not in ALLOWED_TECHNIQUES:
        if ext.technique != "natural_harmonic":
            reasons.append("unsupported_technique")
    if not ext.has_location():
        reasons.append("missing_location")
    if ext.is_quantitative() and not (ext.original_unit or ext.canonical_unit):
        reasons.append("missing_units")
    if ext.curator_verification_status == "rejected":
        reasons.append("rejected_by_curator")
    return (len(reasons) == 0), reasons


def ingest_evidence_package(
    *,
    output_dir: Path | str | None = None,
    reports_dir: Path | str | None = None,
    dry_run: bool = False,
    overwrite: bool = True,
    activation_target: ApplicabilityQuery | None = None,
) -> PackageIngestionResult:
    registry = SourceRegistry.from_yaml()
    extracts = load_extracts()
    param_cfg = load_parameter_config()
    mechanisms = load_physical_mechanisms()
    mappings = load_density_mappings()

    result = PackageIngestionResult()
    result.mechanisms = mechanisms
    result.density_mappings = [DensityMappingModel.model_validate(m).model_dump() for m in mappings]
    result.unsupported_parameters = list(param_cfg.get("unsupported_requested_parameters") or [])

    for src in registry.list_sources():
        model = LiteratureSourceModel.model_validate(src.model_dump())
        ok, reasons = _validate_source(model)
        row = model.model_dump()
        row["validation_ok"] = ok
        row["rejection_reasons"] = ";".join(reasons)
        if ok and model.is_usable_bibliography():
            result.validated_sources.append(row)
        else:
            result.rejected_sources.append(row)

    for ext in extracts:
        ok, reasons = _validate_extract(ext, registry)
        row = extract_package_row(ext)
        row["validation_ok"] = ok
        row["rejection_reasons"] = ";".join(reasons)
        if ok and ext.is_validated():
            result.validated_extracts.append(row)
        else:
            result.rejected_extracts.append(row)

    # Candidate parameters from curated ledger
    raw_params = list(param_cfg.get("parameters") or [])
    for p in raw_params:
        LiteratureParameterModel.model_validate(p)
        if p.get("instrument") and p["instrument"] not in ALLOWED_INSTRUMENTS:
            raise ValueError(f"Parameter instrument outside domain: {p.get('parameter_id')}")
        if p.get("technique") and p["technique"] not in ALLOWED_TECHNIQUES:
            raise ValueError(f"Parameter technique outside domain: {p.get('parameter_id')}")
        result.candidate_parameters.append(dict(p))

    decisions = evaluate_all_parameters(
        result.candidate_parameters,
        registry=registry,
        extracts=extracts,
        target=activation_target,
    )
    result.decisions = decisions
    extracts_by_id = {str(e.evidence_id): e for e in extracts if e.evidence_id}

    for param, decision in zip(result.candidate_parameters, decisions, strict=True):
        row = dict(param)
        row["activation_active"] = decision.active
        row["active_for_density_prediction"] = decision.active_for_density_prediction
        row["applicability_status"] = decision.applicability_status
        row["failure_reasons"] = ";".join(decision.reasons)
        if decision.active:
            result.active_parameters.append(row)
        else:
            result.inactive_parameters.append(row)
            result.activation_failures.append(decision.to_row())

    # Rebuild matrix from validated package extracts
    validated_extract_models = [
        e for e in extracts if e.is_validated() and e.source_id in registry.sources
    ]
    result.rebuilt_matrix = enrich_matrix_parameter_counts(
        build_evidence_matrix(
            registry,
            validated_extract_models,
            parameter_decisions=decisions,
            mechanisms=mechanisms,
            mode="curated_package",
        ),
        result.candidate_parameters,
        decisions,
    )

    from string_technique_model.literature.domain import legacy_evidence_matrix_cell_count

    assert len(result.rebuilt_matrix) == legacy_evidence_matrix_cell_count()
    assert not any("estimated_density" in r or "predicted_density" in r for r in result.rebuilt_matrix)
    result.density_prediction_produced = False

    result.summary = {
        "curated_files_loaded": [
            "configs/literature_sources.yaml",
            "configs/physical_mechanisms.yaml",
            "configs/literature_parameters.yaml",
            "configs/literature_evidence_extracts.yaml",
            "configs/literature_density_mappings.yaml",
        ],
        "n_validated_sources": len(result.validated_sources),
        "n_rejected_sources": len(result.rejected_sources),
        "n_validated_extracts": len(result.validated_extracts),
        "n_rejected_extracts": len(result.rejected_extracts),
        "n_candidate_parameters": len(result.candidate_parameters),
        "n_active_parameters": len(result.active_parameters),
        "n_inactive_parameters": len(result.inactive_parameters),
        "activation_failure_reasons": sorted(
            {r for d in result.decisions for r in d.reasons}
        ),
        "rebuilt_evidence_grades": {
            f"{r['instrument']}/{r['technique']}": r["evidence_grade"] for r in result.rebuilt_matrix
        },
        "unresolved_cells": [
            f"{r['instrument']}/{r['technique']}"
            for r in result.rebuilt_matrix
            if r["evidence_grade"] in {"NA", "D"}
            or r.get("estimation_status") == "not_estimable_from_current_local_evidence"
        ],
        "density_prediction_produced": False,
        "n_mechanisms": len(result.mechanisms),
    }

    out = Path(output_dir or PACKAGE_ROOT / "outputs" / "literature")
    reports = Path(reports_dir or PACKAGE_ROOT / "reports")
    files: dict[str, str] = {}

    if not dry_run:
        if out.exists() and any(out.iterdir()) and not overwrite:
            raise FileExistsError(f"Output directory exists and overwrite=False: {out}")
        out.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)

        # Curated package exports
        files["evidence_extracts.csv"] = write_csv(
            out / "evidence_extracts.csv",
            [extract_package_row(e) for e in extracts],
            columns=[
                "evidence_id",
                "source_id",
                "instrument",
                "technique",
                "page_start",
                "page_end",
                "canonical_variable",
                "reported_value",
                "unit",
                "operation_type",
                "directness",
                "density_mapping_status",
            ],
        )
        files["instrument_technique_evidence_matrix.csv"] = write_csv(
            out / "instrument_technique_evidence_matrix.csv",
            [serialize_matrix_row_for_csv(r) for r in result.rebuilt_matrix],
        )
        files["parameter_evidence_ledger.csv"] = write_csv(
            out / "parameter_evidence_ledger.csv",
            result.candidate_parameters,
        )
        files["density_mapping_matrix.csv"] = write_csv(
            out / "density_mapping_matrix.csv",
            mapping_matrix_rows(mappings),
        )
        files["unsupported_parameters.csv"] = write_csv(
            out / "unsupported_parameters.csv",
            _flatten_unsupported(result.unsupported_parameters),
        )

        files["validated_sources.csv"] = write_csv(out / "validated_sources.csv", result.validated_sources)
        files["validated_evidence_extracts.csv"] = write_csv(
            out / "validated_evidence_extracts.csv", result.validated_extracts
        )
        files["validated_parameters.csv"] = write_csv(
            out / "validated_parameters.csv", result.candidate_parameters
        )
        files["active_parameters.csv"] = write_csv(out / "active_parameters.csv", result.active_parameters)
        files["inactive_parameters.csv"] = write_csv(
            out / "inactive_parameters.csv", result.inactive_parameters
        )
        files["parameter_activation_failures.csv"] = write_csv(
            out / "parameter_activation_failures.csv", result.activation_failures
        )
        files["rebuilt_evidence_matrix.csv"] = write_csv(
            out / "rebuilt_evidence_matrix.csv",
            [serialize_matrix_row_for_csv(r) for r in result.rebuilt_matrix],
        )
        files["literature_parameter_validation.md"] = write_text(
            reports / "literature_parameter_validation.md",
            validation_report(result),
        )
        result.output_files = files

    _ = extracts_by_id
    return result


def _flatten_unsupported(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        instruments = item.get("instruments") or [None]
        techniques = item.get("techniques") or [None]
        for inst in instruments:
            for tech in techniques:
                rows.append(
                    {
                        "parameter_name": item.get("parameter_name"),
                        "instrument": inst,
                        "technique": tech,
                        "reason": item.get("reason"),
                    }
                )
    return rows


def validation_report(result: PackageIngestionResult) -> str:
    s = result.summary
    lines = [
        "# Literature parameter validation",
        "",
        "Curated evidence package is the scientific source of truth.",
        "No technique-density prediction was produced in this phase.",
        "",
        "## Load summary",
        "",
        f"- Curated files: {', '.join(s.get('curated_files_loaded') or [])}",
        f"- Validated sources: {s.get('n_validated_sources')}",
        f"- Rejected sources: {s.get('n_rejected_sources')}",
        f"- Validated extracts: {s.get('n_validated_extracts')}",
        f"- Rejected extracts: {s.get('n_rejected_extracts')}",
        f"- Candidate parameters: {s.get('n_candidate_parameters')}",
        f"- Active density parameters: {s.get('n_active_parameters')}",
        f"- Inactive parameters: {s.get('n_inactive_parameters')}",
        f"- Mechanisms registered: {s.get('n_mechanisms')}",
        f"- Density prediction produced: {s.get('density_prediction_produced')}",
        "",
        "## Activation failure reasons",
        "",
    ]
    for reason in s.get("activation_failure_reasons") or []:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Rebuilt evidence grades", ""])
    grades = s.get("rebuilt_evidence_grades") or {}
    lines.append("| cell | grade |")
    lines.append("|---|---|")
    for cell, grade in sorted(grades.items()):
        lines.append(f"| {cell} | {grade} |")
    lines.extend(["", "## Unresolved / weak cells", ""])
    for cell in s.get("unresolved_cells") or []:
        lines.append(f"- {cell}")
    lines.append("")
    return "\n".join(lines)
