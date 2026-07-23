"""Narrow extrapolator: measured ordinary baseline + literature evidence → auditable cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.extrapolation.baselines import OrdinaryBaselineStore
from string_technique_model.extrapolation.evidence import load_literature_evidence, select_evidence
from string_technique_model.extrapolation.models import ExtrapolationCell, TargetSpec
from string_technique_model.extrapolation.targets import load_target_grid

_EXCLUDED = frozenset(
    {
        "multiphonic",
        "heavy_practice_mute",
        "flautando",
        "on_bridge",
        "afterlength",
    }
)


def _method_for(technique: str, quantity: str, value_kind: str) -> str:
    if value_kind == "measured":
        return "ordinary_cdm_baseline_lookup"
    if quantity == "EWSD_score_acoustic_balanced":
        return "ewsd_direct_extrapolation_refused"
    if value_kind == "literature_bounded":
        return f"instrument_specific_literature_bound:{technique}"
    if value_kind == "qualitative_only":
        return f"technique_specific_qualitative_tendency:{technique}"
    if value_kind == "unavailable":
        return "evidence_insufficient_or_out_of_scope"
    return f"technique_specific:{technique}"


def _cell_from_evidence(
    target: TargetSpec,
    *,
    baseline_ids: list[str],
    baseline_mean: float | None,
    evidence,
) -> ExtrapolationCell:
    warnings = list(evidence.warnings or [])
    assumptions = list(evidence.assumptions or [])

    if evidence.instrument is None and target.instrument:
        warnings.append(
            f"Evidence is bowed-string generic; applied to {target.instrument} without a universal multiplier."
        )

    if evidence.value_kind == "unavailable":
        return ExtrapolationCell(
            instrument=target.instrument,
            technique=target.technique,
            dynamic=target.dynamic,
            target_quantity=target.target_quantity,
            value=None,
            unit=evidence.unit,
            value_kind="unavailable",
            evidence_status="literature_insufficient",
            source=evidence.source_id,
            source_page=evidence.source_page,
            measurement_domain=evidence.measurement_domain,
            extrapolation_method=_method_for(target.technique, target.target_quantity, "unavailable"),
            baseline_record_ids=baseline_ids,
            uncertainty="not_applicable",
            measured_or_extrapolated="unavailable",
            assumptions_used=assumptions,
            warnings=warnings,
            mute_state=target.mute_state,
            evidence_id=evidence.evidence_id,
            baseline_ewsd_mean=baseline_mean,
            na_reason=evidence.supported_relation or "insufficient_evidence",
        )

    if evidence.value_kind == "literature_bounded":
        # Never treat mute dB as EWSD
        if target.target_quantity == "EWSD_score_acoustic_balanced":
            return ExtrapolationCell(
                instrument=target.instrument,
                technique=target.technique,
                dynamic=target.dynamic,
                target_quantity=target.target_quantity,
                value=None,
                value_kind="unavailable",
                evidence_status="mapping_unavailable",
                source=evidence.source_id,
                source_page=evidence.source_page,
                measurement_domain=evidence.measurement_domain,
                extrapolation_method="refuse_indirect_proxy_as_ewsd",
                baseline_record_ids=baseline_ids,
                uncertainty="not_applicable",
                measured_or_extrapolated="unavailable",
                assumptions_used=assumptions,
                warnings=warnings + ["Indirect acoustic proxy refused as EWSD."],
                mute_state=target.mute_state,
                evidence_id=evidence.evidence_id,
                baseline_ewsd_mean=baseline_mean,
                na_reason="indirect_proxy_not_ewsd_mapping",
            )
        return ExtrapolationCell(
            instrument=target.instrument,
            technique=target.technique,
            dynamic=target.dynamic,
            target_quantity=target.target_quantity,
            value=evidence.numerical_value,
            lower_bound=evidence.lower_bound,
            upper_bound=evidence.upper_bound,
            unit=evidence.unit,
            value_kind="literature_bounded",
            evidence_status="literature_supported",
            source=evidence.source_id,
            source_page=evidence.source_page,
            measurement_domain=evidence.measurement_domain,
            extrapolation_method=_method_for(target.technique, target.target_quantity, "literature_bounded"),
            baseline_record_ids=baseline_ids,
            uncertainty="literature_point_or_interval_as_curated",
            measured_or_extrapolated="extrapolated",
            assumptions_used=assumptions,
            warnings=warnings,
            mute_state=target.mute_state,
            evidence_id=evidence.evidence_id,
            baseline_ewsd_mean=baseline_mean,
        )

    if evidence.value_kind == "qualitative_only":
        return ExtrapolationCell(
            instrument=target.instrument,
            technique=target.technique,
            dynamic=target.dynamic,
            target_quantity=target.target_quantity,
            value=evidence.qualitative_value,
            unit=evidence.unit or "tendency",
            value_kind="qualitative_only",
            evidence_status="secondary_synthesis_qualitative",
            source=evidence.source_id,
            source_page=evidence.source_page,
            measurement_domain=evidence.measurement_domain,
            extrapolation_method=_method_for(target.technique, target.target_quantity, "qualitative_only"),
            baseline_record_ids=baseline_ids,
            uncertainty="qualitative_no_numeric_interval",
            measured_or_extrapolated="extrapolated",
            assumptions_used=assumptions,
            warnings=warnings,
            mute_state=target.mute_state,
            evidence_id=evidence.evidence_id,
            baseline_ewsd_mean=baseline_mean,
        )

    # Fallback
    return ExtrapolationCell(
        instrument=target.instrument,
        technique=target.technique,
        dynamic=target.dynamic,
        target_quantity=target.target_quantity,
        value=None,
        value_kind="unavailable",
        evidence_status="literature_insufficient",
        source=evidence.source_id,
        source_page=evidence.source_page,
        measurement_domain=evidence.measurement_domain,
        extrapolation_method="unhandled_value_kind",
        baseline_record_ids=baseline_ids,
        measured_or_extrapolated="unavailable",
        warnings=warnings + [f"Unhandled evidence value_kind={evidence.value_kind}"],
        mute_state=target.mute_state,
        evidence_id=evidence.evidence_id,
        baseline_ewsd_mean=baseline_mean,
        na_reason="unhandled_value_kind",
    )


def _baseline_ewsd_cell(
    instrument: str,
    dynamic: str,
    *,
    mean: float,
    ids: list[str],
    metric_name: str,
    baseline_source: str,
) -> ExtrapolationCell:
    from_research = baseline_source == "spectral_analyser_research_excel" or any(
        "research_excel" in i for i in ids
    )
    return ExtrapolationCell(
        instrument=instrument,
        technique="ordinary",
        dynamic=dynamic,
        target_quantity="EWSD_score_acoustic_balanced",
        value=mean,
        lower_bound=None,
        upper_bound=None,
        unit="dimensionless_score",
        value_kind="measured",
        evidence_status="measured_baseline",
        source=(
            "spectral_analyser_compiled_density_metrics_research"
            if from_research
            else "ordinary_cdm_baselines"
        ),
        source_page="Spectral_Density_Metrics" if from_research else None,
        measurement_domain="radiated_audio_orchidea_spectral_analyser" if from_research else "unresolved_mixed_iowa_orchidea_midpoint",
        extrapolation_method=(
            "research_excel_mean_across_notes"
            if from_research
            else "ordinary_cdm_mean_across_notes"
        ),
        baseline_record_ids=ids,
        uncertainty="note_aggregate_mean_only;per_note_ids_in_baseline_record_ids",
        measured_or_extrapolated="measured",
        assumptions_used=[],
        warnings=[
            f"Baseline metric: {metric_name}",
            f"Baseline source: {baseline_source}",
            "Aggregated across notes for this dynamic; not a single-note prediction.",
        ],
        mute_state="off",
        evidence_id=None,
        baseline_ewsd_mean=mean,
    )


def _baseline_component_cell(
    instrument: str,
    dynamic: str,
    quantity: str,
    *,
    mean: float,
    ids: list[str],
) -> ExtrapolationCell:
    return ExtrapolationCell(
        instrument=instrument,
        technique="ordinary",
        dynamic=dynamic,
        target_quantity=quantity,
        value=mean,
        unit="from_research_excel_column",
        value_kind="measured",
        evidence_status="measured_baseline",
        source="spectral_analyser_compiled_density_metrics_research",
        source_page="Spectral_Density_Metrics",
        measurement_domain="radiated_audio_orchidea_spectral_analyser",
        extrapolation_method="research_excel_component_mean_across_notes",
        baseline_record_ids=ids,
        uncertainty="note_aggregate_mean_only",
        measured_or_extrapolated="measured",
        assumptions_used=[],
        warnings=["Ordinary measured component from Spectral_Analyser research workbook."],
        mute_state="off",
        baseline_ewsd_mean=None,
    )


def run_narrow_extrapolation(
    *,
    evidence_path: Path | str | None = None,
    target_path: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    research_excel: Path | str | None = None,
    orchidea_root: Path | str | None = None,
    orchidea_manifest: Path | str | None = None,
    use_orchidea_manifest: bool = True,
) -> dict[str, Any]:
    """Run first-priority ordinario→ST/SP/standard-sordino extrapolation."""
    store = OrdinaryBaselineStore()
    store.load_cdm_directory(baseline_dir)
    load_warnings: list[str] = []
    if use_orchidea_manifest:
        load_warnings.extend(
            store.load_orchidea_manifest(orchidea_manifest, orchidea_root=orchidea_root)
        )
    if research_excel:
        load_warnings.extend(store.load_research_excel(research_excel))
    # store.load_warnings already accumulated by load_* helpers; avoid double-count
    for w in store.load_warnings:
        if w not in load_warnings:
            load_warnings.append(w)

    evidence = load_literature_evidence(evidence_path)
    targets, grid_meta = load_target_grid(target_path)
    cells: list[ExtrapolationCell] = []

    # Measured ordinary EWSD (+ available components) reference rows
    if grid_meta.get("emit_baseline_measured_ewsd", True):
        for inst in grid_meta.get("instruments") or []:
            for dyn in grid_meta.get("dynamics") or []:
                mean, ids = store.dynamic_mean_ewsd(inst, dyn)
                if mean is None:
                    cells.append(
                        ExtrapolationCell(
                            instrument=inst,
                            technique="ordinary",
                            dynamic=dyn,
                            target_quantity="EWSD_score_acoustic_balanced",
                            value=None,
                            value_kind="unavailable",
                            evidence_status="literature_insufficient",
                            source="ordinary_baseline_store",
                            measurement_domain="unresolved",
                            extrapolation_method="ordinary_baseline_lookup",
                            baseline_record_ids=[],
                            measured_or_extrapolated="unavailable",
                            warnings=["No ordinary measured EWSD for this instrument/dynamic."],
                            mute_state="off",
                            na_reason="missing_baseline",
                        )
                    )
                else:
                    cells.append(
                        _baseline_ewsd_cell(
                            inst,
                            dyn,
                            mean=mean,
                            ids=ids,
                            metric_name=store.metric_name,
                            baseline_source=store.baseline_source,
                        )
                    )
                for qty in ("spectral_slope", "upper_partial_energy_ratio"):
                    cmean, cids = store.dynamic_mean_component(inst, dyn, qty)
                    if cmean is not None:
                        cells.append(
                            _baseline_component_cell(inst, dyn, qty, mean=cmean, ids=cids)
                        )

    for target in targets:
        if target.technique in _EXCLUDED:
            cells.append(
                ExtrapolationCell(
                    instrument=target.instrument,
                    technique=target.technique,
                    dynamic=target.dynamic,
                    target_quantity=target.target_quantity,
                    value=None,
                    value_kind="unavailable",
                    evidence_status="out_of_scope",
                    source=None,
                    measurement_domain=None,
                    extrapolation_method="excluded_from_first_priority_model",
                    measured_or_extrapolated="unavailable",
                    warnings=["Excluded from first-priority extrapolator scope."],
                    mute_state=target.mute_state,
                    na_reason="out_of_scope",
                )
            )
            continue

        mean, ids = store.dynamic_mean_ewsd(target.instrument, target.dynamic)

        # EWSD: always refuse numerical TF unless future validated mapping exists
        if target.target_quantity == "EWSD_score_acoustic_balanced":
            ev = select_evidence(
                evidence,
                technique=target.technique,
                quantity=target.target_quantity,
                instrument=target.instrument,
            )
            cells.append(
                ExtrapolationCell(
                    instrument=target.instrument,
                    technique=target.technique,
                    dynamic=target.dynamic,
                    target_quantity=target.target_quantity,
                    value=None,
                    value_kind="unavailable",
                    evidence_status="mapping_unavailable",
                    source=ev.source_id if ev else None,
                    source_page=ev.source_page if ev else None,
                    measurement_domain="unresolved",
                    extrapolation_method="ewsd_direct_extrapolation_refused",
                    baseline_record_ids=ids,
                    uncertainty="not_applicable",
                    measured_or_extrapolated="unavailable",
                    assumptions_used=[],
                    warnings=[
                        "No validated literature→EWSD component mapping is active.",
                        "Preserve component-level qualitative/literature_bounded rows instead.",
                        "Do not apply mute dB or universal multipliers to EWSD.",
                    ],
                    mute_state=target.mute_state,
                    evidence_id=ev.evidence_id if ev else "EXEV_EWSD_NO_DIRECT_TF",
                    baseline_ewsd_mean=mean,
                    na_reason="ewsd_formula_component_mapping_not_validated_for_technique_tf",
                )
            )
            continue

        ev = select_evidence(
            evidence,
            technique=target.technique,
            quantity=target.target_quantity,
            instrument=target.instrument,
        )
        if ev is None:
            cells.append(
                ExtrapolationCell(
                    instrument=target.instrument,
                    technique=target.technique,
                    dynamic=target.dynamic,
                    target_quantity=target.target_quantity,
                    value=None,
                    value_kind="unavailable",
                    evidence_status="literature_insufficient",
                    source=None,
                    measurement_domain=None,
                    extrapolation_method="no_matching_evidence_row",
                    baseline_record_ids=ids,
                    measured_or_extrapolated="unavailable",
                    warnings=["No curated evidence row for this technique×quantity×instrument."],
                    mute_state=target.mute_state,
                    baseline_ewsd_mean=mean,
                    na_reason="no_matching_evidence",
                )
            )
            continue

        cells.append(
            _cell_from_evidence(target, baseline_ids=ids, baseline_mean=mean, evidence=ev)
        )

    summary = {
        "n_cells": len(cells),
        "n_measured": sum(1 for c in cells if c.value_kind == "measured"),
        "n_literature_bounded": sum(1 for c in cells if c.value_kind == "literature_bounded"),
        "n_qualitative_only": sum(1 for c in cells if c.value_kind == "qualitative_only"),
        "n_unavailable": sum(1 for c in cells if c.value_kind == "unavailable"),
        "n_ewsd_unavailable": sum(
            1
            for c in cells
            if c.target_quantity == "EWSD_score_acoustic_balanced" and c.value_kind == "unavailable"
            and c.technique != "ordinary"
        ),
        "load_warnings": load_warnings,
        "baseline_source": store.baseline_source,
        "n_research_rows": len(store.research_rows),
        "scope": "ordinario→sul_tasto|sul_ponticello|standard_con_sordino; pp/mf/ff; vln/vla/vlc/cb",
    }
    return {"cells": cells, "summary": summary, "targets": targets}
