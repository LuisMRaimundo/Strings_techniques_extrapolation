"""Note-level requests: have(note,value,metadata) → need(note,technique)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.extrapolation.density_effects import (
    estimate_technique_density,
    load_density_effects,
)
from string_technique_model.extrapolation.evidence import load_literature_evidence, select_evidence
from string_technique_model.extrapolation.models import ExtrapolationCell
from string_technique_model.extrapolation.request_io import (
    load_request_workbook,
    normalize_technique,
    parse_measured_table,
    parse_request_table,
    write_request_template,
)
from string_technique_model.extrapolation.register_builder import TECHNIQUE_SORT_ORDER, resolve_note
from string_technique_model.extrapolation.research_excel import parse_research_workbook

_PRIORITY1 = frozenset({"sul_tasto", "sul_ponticello", "con_sordino"})
_PRIORITY2 = frozenset({"artificial_harmonic", "natural_harmonic"})
_NUMERIC_TECHS = _PRIORITY1 | _PRIORITY2


def _technique_sort_key(technique: str | None) -> tuple[int, str]:
    tech = str(technique or "")
    try:
        return (TECHNIQUE_SORT_ORDER.index(tech), tech)
    except ValueError:
        return (len(TECHNIQUE_SORT_ORDER), tech)


def sort_results_by_technique(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group rows by technique (con_sordino block, then sul_tasto, …), notes ascending within."""

    def note_midi(note: str | None) -> int:
        if not note:
            return 9999
        resolved = resolve_note(str(note))
        return resolved[1] if resolved else 9999

    return sorted(
        results,
        key=lambda r: (
            _technique_sort_key(r.get("request_technique") or r.get("technique")),
            str(r.get("instrument") or ""),
            str(r.get("dynamic") or ""),
            note_midi(r.get("request_note") or r.get("note")),
            str(r.get("request_note") or r.get("note") or ""),
        ),
    )


def sort_requests_by_technique(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def note_midi(note: str | None) -> int:
        if not note:
            return 9999
        resolved = resolve_note(str(note))
        return resolved[1] if resolved else 9999

    return sorted(
        requests,
        key=lambda r: (
            _technique_sort_key(r.get("technique")),
            str(r.get("instrument") or ""),
            str(r.get("dynamic") or ""),
            note_midi(r.get("note")),
            str(r.get("note") or ""),
        ),
    )


def _note_key(note: str) -> str:
    return str(note).strip().upper().replace(" ", "")


def build_registry(measured: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """Key: (instrument, dynamic, note, quantity) → measured row (ordinary preferred)."""
    reg: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in measured:
        tech = row.get("technique") or "ordinary"
        if tech not in {"ordinary", "ordinario", "arco", "arco_normal"}:
            # Only ordinary registry is used as baseline for technique TF
            continue
        key = (
            str(row["instrument"]),
            str(row["dynamic"]).lower(),
            _note_key(row["note"]),
            str(row.get("quantity") or "EWSD_score_acoustic_balanced"),
        )
        reg[key] = row
    return reg


def _lookup(
    registry: dict[tuple[str, str, str, str], dict[str, Any]],
    *,
    instrument: str,
    dynamic: str,
    note: str,
    quantity: str,
) -> dict[str, Any] | None:
    return registry.get((instrument, dynamic.lower(), _note_key(note), quantity))


def _result_row(
    request: dict[str, Any],
    *,
    baseline: dict[str, Any] | None,
    value: Any,
    lower: float | None,
    upper: float | None,
    unit: str | None,
    value_kind: str,
    evidence_status: str,
    source: str | None,
    source_page: str | None,
    method: str,
    uncertainty: str | None,
    assumptions: list[str],
    warnings: list[str],
    na_reason: str | None,
    qualitative_effect: str | None = None,
    attenuation_db: float | None = None,
) -> dict[str, Any]:
    return {
        "request_note": request["note"],
        "request_technique": request["technique"],
        "instrument": request.get("instrument"),
        "dynamic": request.get("dynamic"),
        "quantity": request.get("quantity") or "EWSD_score_acoustic_balanced",
        "baseline_note": baseline["note"] if baseline else None,
        "baseline_technique": baseline.get("technique") if baseline else None,
        "baseline_value": baseline["value"] if baseline else None,
        "value": value,
        "lower_bound": lower,
        "upper_bound": upper,
        "unit": unit,
        "value_kind": value_kind,
        "evidence_status": evidence_status,
        "qualitative_effect_vs_ordinary": qualitative_effect,
        "attenuation_db_power": attenuation_db,
        "source": source,
        "source_page": source_page,
        "extrapolation_method": method,
        "baseline_record_ids": (
            [f"{baseline['instrument']}|ordinary|{baseline['note']}|{baseline['dynamic']}|measured"]
            if baseline
            else []
        ),
        "uncertainty": uncertainty,
        "measured_or_extrapolated": (
            "measured"
            if value_kind == "measured"
            else ("unavailable" if value_kind == "unavailable" else "extrapolated")
        ),
        "assumptions_used": assumptions,
        "warnings": warnings,
        "na_reason": na_reason,
    }


def apply_request(
    request: dict[str, Any],
    registry: dict[tuple[str, str, str, str], dict[str, Any]],
    evidence: list,
    *,
    effects_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one need(note, technique) against the measured registry."""
    inst = request.get("instrument")
    dyn = request.get("dynamic")
    qty = request.get("quantity") or "EWSD_score_acoustic_balanced"
    tech = request["technique"]
    note = request["note"]

    if not inst or not dyn:
        return _result_row(
            request,
            baseline=None,
            value=None,
            lower=None,
            upper=None,
            unit=None,
            value_kind="unavailable",
            evidence_status="literature_insufficient",
            source=None,
            source_page=None,
            method="missing_instrument_or_dynamic",
            uncertainty=None,
            assumptions=[],
            warnings=["Request must include instrument and dynamic (columns or defaults)."],
            na_reason="missing_instrument_or_dynamic",
        )

    baseline = _lookup(registry, instrument=inst, dynamic=dyn, note=note, quantity=qty)
    if baseline is None:
        return _result_row(
            request,
            baseline=None,
            value=None,
            lower=None,
            upper=None,
            unit=None,
            value_kind="unavailable",
            evidence_status="literature_insufficient",
            source=None,
            source_page=None,
            method="note_not_in_measured_registry",
            uncertainty=None,
            assumptions=[],
            warnings=[f"No measured ordinary row for {inst} {dyn} note={note} quantity={qty}."],
            na_reason="note_not_found_in_measured",
        )

    # Same-technique passthrough
    if tech == "ordinary":
        return _result_row(
            request,
            baseline=baseline,
            value=baseline["value"],
            lower=None,
            upper=None,
            unit="dimensionless_score" if "EWSD" in qty else None,
            value_kind="measured",
            evidence_status="measured_baseline",
            source="measured_registry",
            source_page=None,
            method="direct_measured_lookup",
            uncertainty=None,
            assumptions=[],
            warnings=[],
            na_reason=None,
        )

    if tech not in _NUMERIC_TECHS:
        return _result_row(
            request,
            baseline=baseline,
            value=None,
            lower=None,
            upper=None,
            unit=None,
            value_kind="unavailable",
            evidence_status="out_of_scope",
            source=None,
            source_page=None,
            method="technique_out_of_scope",
            uncertainty=None,
            assumptions=[],
            warnings=[f"Technique {tech!r} has no provisional density effect configured."],
            na_reason="technique_out_of_scope",
        )

    warnings = [
        f"Matched ordinary {inst} {dyn} {baseline['note']} = {baseline['value']}.",
    ]
    atten = None
    source_page = None
    if tech == "con_sordino":
        aev = select_evidence(evidence, technique=tech, quantity="attenuation_db_power", instrument=inst)
        if aev and aev.value_kind == "literature_bounded" and aev.numerical_value is not None:
            atten = float(aev.numerical_value)
            source_page = aev.source_page

    est = estimate_technique_density(
        baseline=float(baseline["value"]),
        technique=tech,
        instrument=inst,
        literature_atten_db=atten,
        effects_cfg=effects_cfg,
    )
    if est is None or est.get("value") is None:
        return _result_row(
            request,
            baseline=baseline,
            value=None,
            lower=None,
            upper=None,
            unit="dimensionless_score",
            value_kind="unavailable",
            evidence_status=(est or {}).get("evidence_status") or "mapping_unavailable",
            source=(est or {}).get("source"),
            source_page=source_page,
            method=(est or {}).get("method") or "no_provisional_effect",
            uncertainty="not_applicable",
            assumptions=list((est or {}).get("assumptions") or []),
            warnings=warnings + list((est or {}).get("warnings") or []),
            na_reason=(est or {}).get("na_reason") or "no_provisional_effect",
            qualitative_effect=(est or {}).get("qualitative_effect"),
            attenuation_db=(est or {}).get("attenuation_db"),
        )

    return _result_row(
        request,
        baseline=baseline,
        value=float(est["value"]),
        lower=est.get("lower_bound"),
        upper=est.get("upper_bound"),
        unit="dimensionless_score",
        value_kind=est["value_kind"],
        evidence_status=est["evidence_status"],
        source=est.get("source"),
        source_page=source_page,
        method=str(est["method"]),
        uncertainty="provisional_bounds_from_config",
        assumptions=list(est.get("assumptions") or []),
        warnings=warnings + list(est.get("warnings") or []),
        na_reason=None,
        qualitative_effect=est.get("qualitative_effect"),
        attenuation_db=est.get("attenuation_db"),
    )


def run_note_level_requests(
    measured: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    *,
    evidence_path: Path | str | None = None,
    effects_path: Path | str | None = None,
) -> dict[str, Any]:
    evidence = load_literature_evidence(evidence_path)
    effects_cfg = load_density_effects(effects_path)
    registry = build_registry(measured)
    results = [
        apply_request(req, registry, evidence, effects_cfg=effects_cfg) for req in requests
    ]
    results = sort_results_by_technique(results)
    ordered_requests = sort_requests_by_technique(list(requests))

    summary = {
        "n_measured": len(measured),
        "n_registry_ordinary": len(registry),
        "n_requests": len(requests),
        "n_matched_baseline": sum(1 for r in results if r["baseline_value"] is not None),
        "n_numeric_value": sum(1 for r in results if r["value"] is not None),
        "n_unavailable": sum(1 for r in results if r["value_kind"] == "unavailable"),
        "result_order": "technique_blocks:" + ",".join(TECHNIQUE_SORT_ORDER),
    }
    return {
        "results": results,
        "summary": summary,
        "measured": measured,
        "requests": ordered_requests,
    }


def measured_from_research_excel(
    path: Path | str,
    *,
    instrument: str | None = None,
    dynamic: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert Spectral_Analyser research Excel into Measured rows."""
    rows, warnings = parse_research_workbook(path, instrument=instrument, dynamic=dynamic)
    measured = [
        {
            "note": r["note"],
            "value": r["ewsd"],
            "instrument": r["instrument"],
            "dynamic": r["dynamic"],
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "metadata": {"source_path": r.get("source_path")},
        }
        for r in rows
        if r.get("note") is not None
    ]
    return measured, warnings


def run_from_workbook(
    path: Path | str,
    *,
    default_instrument: str | None = None,
    default_dynamic: str | None = None,
    evidence_path: Path | str | None = None,
) -> dict[str, Any]:
    measured, requests, warnings = load_request_workbook(
        path,
        default_instrument=default_instrument,
        default_dynamic=default_dynamic,
    )
    out = run_note_level_requests(measured, requests, evidence_path=evidence_path)
    out["load_warnings"] = warnings
    return out


def export_note_level_workbook(result: dict[str, Any], path: Path | str) -> Path:
    """Export results Excel: All_Results (technique blocks) + one sheet per technique."""
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sort_results_by_technique(list(result.get("results") or []))
    rows = []
    for r in ordered:
        row = dict(r)
        row["baseline_record_ids"] = ";".join(row.get("baseline_record_ids") or [])
        row["assumptions_used"] = ";".join(row.get("assumptions_used") or [])
        row["warnings"] = ";".join(row.get("warnings") or [])
        rows.append(row)
    frame = pd.DataFrame(rows)

    # Prefer a compact readable column order
    preferred = [
        "request_technique",
        "request_note",
        "instrument",
        "dynamic",
        "baseline_value",
        "value",
        "lower_bound",
        "upper_bound",
        "value_kind",
        "qualitative_effect_vs_ordinary",
        "attenuation_db_power",
        "extrapolation_method",
        "uncertainty",
        "assumptions_used",
        "warnings",
        "source",
        "source_page",
        "na_reason",
    ]
    if not frame.empty:
        cols = [c for c in preferred if c in frame.columns] + [
            c for c in frame.columns if c not in preferred
        ]
        frame = frame[cols]

    summary = pd.DataFrame(
        [{"key": k, "value": str(v)} for k, v in (result.get("summary") or {}).items()]
    )
    measured = pd.DataFrame(result.get("measured") or [])
    requests = pd.DataFrame(sort_requests_by_technique(list(result.get("requests") or [])))

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="All_Results", index=False)
        # One sheet per technique block (Excel sheet name ≤ 31 chars)
        if not frame.empty and "request_technique" in frame.columns:
            for tech in TECHNIQUE_SORT_ORDER:
                block = frame[frame["request_technique"] == tech]
                if block.empty:
                    continue
                sheet = tech[:31]
                block.to_excel(writer, sheet_name=sheet, index=False)
            others = frame[~frame["request_technique"].isin(TECHNIQUE_SORT_ORDER)]
            if not others.empty:
                others.to_excel(writer, sheet_name="other_techniques", index=False)
        summary.to_excel(writer, sheet_name="Run_Summary", index=False)
        if not measured.empty:
            m = measured.drop(columns=["metadata"], errors="ignore")
            m.to_excel(writer, sheet_name="Measured_Used", index=False)
        if not requests.empty:
            rq = requests.drop(columns=["metadata"], errors="ignore")
            rq.to_excel(writer, sheet_name="Requests_Used", index=False)
    return path


def results_to_cells(result: dict[str, Any]) -> list[ExtrapolationCell]:
    """Optional bridge to ExtrapolationCell for shared GUI grids."""
    cells: list[ExtrapolationCell] = []
    for r in result["results"]:
        cells.append(
            ExtrapolationCell(
                instrument=str(r.get("instrument") or ""),
                technique=str(r.get("request_technique") or ""),
                dynamic=str(r.get("dynamic") or ""),
                target_quantity=str(r.get("quantity") or "EWSD_score_acoustic_balanced"),
                value=r.get("value"),
                lower_bound=r.get("lower_bound"),
                upper_bound=r.get("upper_bound"),
                unit=r.get("unit"),
                value_kind=r.get("value_kind") or "unavailable",
                evidence_status=r.get("evidence_status") or "mapping_unavailable",
                source=r.get("source"),
                source_page=r.get("source_page"),
                measurement_domain="note_level_request",
                extrapolation_method=str(r.get("extrapolation_method") or ""),
                baseline_record_ids=list(r.get("baseline_record_ids") or []),
                uncertainty=r.get("uncertainty"),
                measured_or_extrapolated=r.get("measured_or_extrapolated") or "unavailable",
                assumptions_used=list(r.get("assumptions_used") or []),
                warnings=list(r.get("warnings") or []),
                baseline_ewsd_mean=r.get("baseline_value"),
                na_reason=r.get("na_reason"),
            )
        )
    return cells


__all__ = [
    "TECHNIQUE_SORT_ORDER",
    "apply_request",
    "build_registry",
    "export_note_level_workbook",
    "measured_from_research_excel",
    "normalize_technique",
    "parse_measured_table",
    "parse_request_table",
    "results_to_cells",
    "run_from_workbook",
    "run_note_level_requests",
    "sort_requests_by_technique",
    "sort_results_by_technique",
    "write_request_template",
]
