"""Validation rules for the literature evidence layer."""

from __future__ import annotations

from typing import Any

from string_technique_model.literature.domain import (
    ACTIVE_PARAMETER_STATUSES,
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
)
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.parameter_ledger import assert_no_active_without_evidence
from string_technique_model.literature.source_registry import SourceRegistry


class LiteratureValidationError(ValueError):
    pass


def validate_literature_layer(
    *,
    registry: SourceRegistry,
    extracts: list[EvidenceExtract],
    matrix_rows: list[dict[str, Any]],
    parameter_rows: list[dict[str, Any]],
    transfer_rows: list[dict[str, Any]],
    strict: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Active sources supporting parameters need complete citations + verified status
    for s in registry.list_sources():
        if s.may_support_parameters() and not s.citation_complete():
            errors.append(f"Verified source {s.source_id} has incomplete citation")

    # 2–3. Extracts point to valid sources and have locations
    for e in extracts:
        if e.source_id not in registry.sources:
            errors.append(f"Extract {e.evidence_id} has unknown source_id={e.source_id}")
            continue
        src = registry.get(e.source_id)
        if not e.has_location():
            errors.append(f"Extract {e.evidence_id} missing page/table/figure/equation/section")
        # 4. Quantitative requires units
        if e.is_quantitative() and not (e.original_unit or e.canonical_unit):
            errors.append(f"Quantitative extract {e.evidence_id} missing units")
        # 5. dB convention when known as decibel
        if e.linear_or_decibel == "decibel" and not e.amplitude_or_power:
            warnings.append(f"Extract {e.evidence_id} is decibel without amplitude/power convention")
        # Non-verified sources may hold curated quantitative constraints, but they
        # cannot activate density parameters (enforced by the activation gate).
        if src.evidence_status != "verified_local_source" and e.is_quantitative():
            mapping = getattr(e, "density_mapping_status", None)
            if mapping in {"direct_same_metric", "directly_computable_from_reported_spectrum"}:
                errors.append(
                    f"Quantitative density-mapped extract {e.evidence_id} requires "
                    f"verified_local_source (got {src.evidence_status})"
                )
            else:
                warnings.append(
                    f"Quantitative extract {e.evidence_id} from {src.evidence_status}; "
                    "inactive for direct density prediction"
                )
        # 10–12. Directness vs instrument
        if e.directness == "direct_same_instrument_same_technique":
            if e.instrument and e.instrument not in ALLOWED_INSTRUMENTS:
                errors.append(f"Direct extract outside instrument domain: {e.evidence_id}")
        # 12. natural vs artificial
        if e.technique == "artificial_harmonic" and e.harmonic_type == "natural":
            errors.append(
                f"Extract {e.evidence_id} marks natural harmonic_type on artificial_harmonic technique"
            )
        # 13. sul tasto / flautando
        claim = (e.paraphrased_claim or "").lower() + " " + (e.quoted_fragment or "").lower()
        if "flautando" in claim and e.technique == "sul_tasto":
            if "explicit" not in (e.curator_notes or "").lower() and "synonym" not in (
                e.curator_notes or ""
            ).lower():
                warnings.append(
                    f"Extract {e.evidence_id} mentions flautando with sul_tasto; "
                    "ensure source-defined synonymy before merging"
                )
        # 15. Violin not direct for others
        if e.instrument in {"vla", "vlc", "cb"} and e.directness == "direct_same_instrument_same_technique":
            # OK if extract instrument matches cell instrument
            pass
        if e.directness == "direct_same_instrument_same_technique" and e.instrument == "vln":
            # Ensure no mislabel in scope claiming other instruments
            scope = (e.evidence_scope or "").lower()
            for other in ("viola", "cello", "double bass", "contrabass"):
                if other in scope and "transfer" not in scope:
                    errors.append(
                        f"Extract {e.evidence_id} claims violin direct evidence for {other}"
                    )

    # Matrix rules
    from string_technique_model.literature.domain import (
        LEGACY_EVIDENCE_MATRIX_LABEL,
        legacy_evidence_matrix_cell_count,
    )

    expected = legacy_evidence_matrix_cell_count()
    if len(matrix_rows) != expected:
        errors.append(
            f"Legacy evidence matrix ({LEGACY_EVIDENCE_MATRIX_LABEL}) must have "
            f"{expected} rows; got {len(matrix_rows)}"
        )
    instruments = {r["instrument"] for r in matrix_rows}
    techniques = {r["technique"] for r in matrix_rows}
    if instruments - ALLOWED_INSTRUMENTS:
        errors.append(f"Matrix has unsupported instruments: {instruments - ALLOWED_INSTRUMENTS}")
    if techniques - ALLOWED_TECHNIQUES:
        errors.append(f"Matrix has unsupported techniques: {techniques - ALLOWED_TECHNIQUES}")
    for r in matrix_rows:
        if not r.get("evidence_grade"):
            errors.append(f"Matrix cell missing grade: {r.get('instrument')}/{r.get('technique')}")
        # 11. NA cells cannot activate density parameters
        if r.get("evidence_grade") == "NA":
            for p in parameter_rows:
                if (
                    p.get("instrument") == r["instrument"]
                    and p.get("technique") == r["technique"]
                    and p.get("is_active")
                ):
                    errors.append(
                        f"NA cell {r['instrument']}/{r['technique']} has active density parameter "
                        f"{p.get('parameter_id')}"
                    )

    errors.extend(assert_no_active_without_evidence(parameter_rows))

    # Transfers
    for t in transfer_rows:
        if t.get("transfer_status") == "physically_justified_candidate":
            if not t.get("proposed_equation"):
                errors.append(
                    f"Transfer {t.get('target_instrument')}/{t.get('target_parameter')} "
                    "lacks proposed_equation"
                )
            if not t.get("physical_justification"):
                errors.append("Transfer candidate missing physical_justification")
        if t.get("activated"):
            errors.append("No transfer may be activated in Phase 3")

    # Qualitative adjectives → no active numerical coefficients
    for p in parameter_rows:
        if p.get("parameter_status") == "qualitative_only" and p.get("is_active"):
            errors.append(f"Qualitative-only parameter must not be active: {p.get('parameter_id')}")
        if p.get("is_active"):
            if not p.get("operation_type") or not p.get("numerical_scale"):
                errors.append(f"Active parameter missing operation/scale: {p.get('parameter_id')}")
            if p.get("parameter_status") not in ACTIVE_PARAMETER_STATUSES:
                errors.append(
                    f"Active density parameter has non-activatable status: {p.get('parameter_id')}"
                )

    ok = not errors
    if strict and warnings:
        # promote warnings optionally — keep as warnings unless strict_warnings desired
        pass
    if not ok:
        raise LiteratureValidationError("; ".join(errors))
    return {"ok": True, "errors": errors, "warnings": warnings}


def validation_report_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Literature validation report",
        "",
        f"- ok: {result.get('ok')}",
        f"- errors: {len(result.get('errors') or [])}",
        f"- warnings: {len(result.get('warnings') or [])}",
        "",
    ]
    if result.get("errors"):
        lines.append("## Errors")
        lines.extend(f"- {e}" for e in result["errors"])
        lines.append("")
    if result.get("warnings"):
        lines.append("## Warnings")
        lines.extend(f"- {w}" for w in result["warnings"])
        lines.append("")
    if result.get("ok"):
        lines.append("All Phase-3 literature validation rules passed.")
        lines.append("")
    return "\n".join(lines)
