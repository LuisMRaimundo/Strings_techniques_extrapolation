"""Multi-sheet Excel export for nonlinear extrapolation runs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import (
    ExtrapolationResult,
    ModelComparisonResult,
    ValueKind,
)
from string_technique_model.extrapolation.nonlinear.priors import load_priors


def _selected_technique_models(results: list[ExtrapolationResult]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in results:
        if r.technique not in out:
            out[r.technique] = str(r.selected_model_id or r.model_id)
    return out


def export_nonlinear_workbook(
    results: list[ExtrapolationResult],
    path: Path | str,
    *,
    comparisons: list[ModelComparisonResult] | None = None,
    run_metadata: dict[str, Any] | None = None,
) -> Path:
    """Write audit workbook with methodology, posterior summary, diagnostics, etc."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pandas required for Excel export") from exc

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    comparisons = comparisons or []
    run_metadata = dict(run_metadata or {})

    # Prefer explicit requested_method; map legacy hierarchical_spline control → automatic
    requested_method = run_metadata.pop("requested_method", None)
    legacy_method = run_metadata.pop("method", None)
    gui_control = run_metadata.pop("gui_method_control", None) or run_metadata.pop(
        "gui_or_cli_method_control", None
    )
    if requested_method is None:
        requested_method = (
            "automatic" if legacy_method in {None, "hierarchical_spline"} else legacy_method
        )
    if gui_control is None and legacy_method == "hierarchical_spline":
        gui_control = legacy_method
    if gui_control is not None:
        run_metadata.setdefault("gui_displayed_method", str(gui_control))
    run_metadata.setdefault("effective_selection_mode", str(requested_method))

    rows = [r.to_row() for r in results]
    summary_df = pd.DataFrame(rows)
    unavailable_df = summary_df[summary_df["value_kind"].eq("unavailable")] if not summary_df.empty else summary_df
    by_technique = (
        summary_df.groupby(["technique", "instrument", "dynamic", "model_id"], dropna=False)
        .size()
        .reset_index(name="n_cells")
        if not summary_df.empty
        else pd.DataFrame(columns=["technique", "instrument", "dynamic", "model_id", "n_cells"])
    )

    methodology = pd.DataFrame(
        [
            {"topic": "Model selection", "detail": "model=f(mechanism, target_quantity, data, evidence_tier)"},
            {"topic": "Stages", "detail": "1) admissible models 2) data ceiling — never auto-pick most complex"},
            {"topic": "Ladder", "detail": "M0 constant → M1 linear → M2 spline → M3 hierarchical → M4 physical → M5 spectral/modal"},
            {"topic": "Config", "detail": "configs/extrapolation_model_selection.yaml"},
            {"topic": "Baseline", "detail": "ordinary log penalized B-spline on MIDI (may be nonlinear)"},
            {"topic": "Technique shape", "detail": "g_t only when register_shape_identified; else constant effect / NA"},
            {"topic": "Intervals", "detail": "assumption_distribution_interval when prior_dominated; NOT classical CI/CrI"},
            {"topic": "Estimate columns", "detail": "estimate_mean/interval_*; posterior_*/credible_* only if bayesian_backend_used"},
            {"topic": "Assumptions", "detail": "assumption_ids=ASSUMP_*; assumptions_trace=detail; assumptions_used aliases ids"},
            {"topic": "Harmonics", "detail": "sounding-pitch targets via modal generator; not ordinary chromatic copy"},
            {"topic": "EWSD mapping", "detail": "observed_scalar_direct_model — not validated F(D1..Dk)"},
        ]
    )

    diagnostics_rows = []
    for r in results:
        diagnostics_rows.append(
            {
                "record_id": r.record_id,
                "technique": r.technique,
                "pitch": r.pitch,
                "model_id": r.model_id,
                "interval_type": r.interval_type,
                "sigma_origin": r.sigma_origin,
                "sigma_value": r.sigma_value,
                "sigma_estimated_from_data": r.sigma_estimated_from_data
                if r.sigma_estimated_from_data is not None
                else "not_applicable",
                "register_shape_identified": r.register_shape_identified
                if r.register_shape_identified is not None
                else "not_applicable",
                "shape_source": r.shape_source,
                "prior_dominated": r.prior_dominated if r.prior_dominated is not None else "not_applicable",
                "model_status": r.model_status,
                "evidence_tier": r.evidence_tier.value,
                "baseline_n_observations": r.baseline_n_observations,
                "baseline_n_knots": r.baseline_n_knots,
                "baseline_penalty_lambda": r.baseline_penalty_lambda,
            }
        )
    diagnostics_df = pd.DataFrame(diagnostics_rows)
    comparison_df = pd.DataFrame([c.model_dump() for c in comparisons])
    priors_df = pd.DataFrame([p.model_dump() for p in load_priors()])

    alpha_rows = []
    seen_alpha: set[tuple[Any, ...]] = set()
    for r in results:
        key_alpha: tuple[Any, ...] = (r.technique, r.instrument, r.dynamic, r.alpha_t, r.alpha_origin)
        if key_alpha in seen_alpha:
            continue
        seen_alpha.add(key_alpha)
        alpha_rows.append(
            {
                "technique": r.technique,
                "instrument": r.instrument,
                "dynamic": r.dynamic,
                "alpha_t": r.alpha_t,
                "technique_multiplier": r.technique_multiplier,
                "alpha_origin": r.alpha_origin,
                "effect_kind": r.effect_kind,
                "attenuation_db_power": r.attenuation_db_power,
                "assumption_ids": ";".join(r.assumption_ids),
                "assumptions_trace": ";".join(r.assumptions_trace),
                "assumptions_used": ";".join(r.assumption_ids),
                "prior_ids": ";".join(r.prior_ids),
                "model_id": r.model_id,
            }
        )
    alpha_df = pd.DataFrame(alpha_rows)

    # Model_Selection (compact) + Model_Selection_Audit (full process)
    selection_rows = []
    audit_rows = []
    seen_sel: set[tuple[Any, ...]] = set()
    for r in results:
        key: tuple[Any, ...] = (r.technique, r.instrument, r.dynamic, r.selected_model_id, r.selection_reason)
        if key in seen_sel:
            continue
        seen_sel.add(key)
        selection_rows.append(
            {
                "technique": r.technique,
                "instrument": r.instrument,
                "dynamic": r.dynamic,
                "target_quantity": r.target_quantity,
                "model_family": r.model_family,
                "selected_model_id": r.selected_model_id or r.model_id,
                "selection_reason": r.selection_reason,
                "fallback_level": r.fallback_level,
                "model_selection_status": r.model_selection_status,
                "candidate_model_ids": ";".join(r.candidate_model_ids),
                "rejected_model_ids": ";".join(r.rejected_model_ids),
                "available_covariates": ";".join(r.available_covariates),
                "required_covariates": ";".join(r.required_covariates),
                "missing_covariates": ";".join(r.missing_covariates),
                "missing_model_components": ";".join(r.missing_model_components),
                "modal_metadata_status": r.modal_metadata_status,
                "acoustic_calibration_status": r.acoustic_calibration_status,
                "target_technique_observations": r.target_technique_observations,
                "distinct_pitch_count": r.distinct_pitch_count,
                "value_kind": r.value_kind.value,
            }
        )
        # One audit row per candidate / rejected model for this technique cell-set
        candidates = r.candidate_model_ids or [r.selected_model_id or r.model_id]
        rejected_map = {}
        for item in r.rejection_reasons:
            if ":" in item:
                mid, why = item.split(":", 1)
                rejected_map[mid] = why
        for mid in candidates:
            role = "selected" if mid == (r.selected_model_id or r.model_id) else (
                "rejected" if mid in rejected_map or mid in r.rejected_model_ids else "candidate_admissible_or_listed"
            )
            audit_rows.append(
                {
                    "technique": r.technique,
                    "instrument": r.instrument,
                    "dynamic": r.dynamic,
                    "target_quantity": r.target_quantity,
                    "model_family": r.model_family,
                    "mechanism": r.mechanism,
                    "model_id": mid,
                    "role": role,
                    "rejection_reason": rejected_map.get(mid, ""),
                    "selected_model_id": r.selected_model_id or r.model_id,
                    "selection_reason": r.selection_reason,
                    "fallback_level": r.fallback_level,
                    "model_selection_status": r.model_selection_status,
                    "available_covariates": ";".join(r.available_covariates),
                    "required_covariates": ";".join(r.required_covariates),
                    "missing_covariates": ";".join(r.missing_covariates),
                    "missing_model_components": ";".join(r.missing_model_components),
                    "modal_metadata_status": r.modal_metadata_status,
                    "acoustic_calibration_status": r.acoustic_calibration_status,
                    "target_technique_observations": r.target_technique_observations,
                    "distinct_pitch_count": r.distinct_pitch_count,
                    "pitch_span_semitones": r.pitch_span_semitones,
                    "assumption_ids": ";".join(r.assumption_ids),
                }
            )
        # Also list rejected models not in candidate list
        for mid, why in rejected_map.items():
            if mid in candidates:
                continue
            audit_rows.append(
                {
                    "technique": r.technique,
                    "instrument": r.instrument,
                    "dynamic": r.dynamic,
                    "target_quantity": r.target_quantity,
                    "model_family": r.model_family,
                    "mechanism": r.mechanism,
                    "model_id": mid,
                    "role": "rejected",
                    "rejection_reason": why,
                    "selected_model_id": r.selected_model_id or r.model_id,
                    "selection_reason": r.selection_reason,
                    "fallback_level": r.fallback_level,
                    "model_selection_status": r.model_selection_status,
                    "available_covariates": ";".join(r.available_covariates),
                    "required_covariates": ";".join(r.required_covariates),
                    "missing_covariates": ";".join(r.missing_covariates),
                    "missing_model_components": ";".join(r.missing_model_components),
                    "modal_metadata_status": r.modal_metadata_status,
                    "acoustic_calibration_status": r.acoustic_calibration_status,
                    "target_technique_observations": r.target_technique_observations,
                    "distinct_pitch_count": r.distinct_pitch_count,
                    "pitch_span_semitones": r.pitch_span_semitones,
                    "assumption_ids": ";".join(r.assumption_ids),
                }
            )

    selection_df = pd.DataFrame(selection_rows)
    audit_df = pd.DataFrame(audit_rows)

    tech_models = _selected_technique_models(results)
    baseline_models = sorted(
        {
            "ordinary_penalized_register_spline"
            if (r.baseline_n_observations or 0) >= 6
            else "ordinary_baseline_fit"
            for r in results
            if r.baseline_value is not None
        }
        or {"none"}
    )

    run_kv: list[dict[str, str]] = [
        {"key": "exported_at_utc", "value": datetime.now(timezone.utc).isoformat()},
        {"key": "requested_method", "value": str(requested_method)},
        {"key": "baseline_model", "value": ",".join(baseline_models)},
        {"key": "n_results", "value": str(len(results))},
        {
            "key": "n_numeric_results",
            "value": str(sum(1 for r in results if r.value_kind != ValueKind.UNAVAILABLE and r.estimate_mean is not None)),
        },
        {"key": "n_unavailable", "value": str(len(unavailable_df))},
        {
            "key": "n_assumption_distribution_intervals",
            "value": str(sum(1 for r in results if r.interval_type == "assumption_distribution_interval")),
        },
        {
            "key": "data_status_values",
            "value": ",".join(sorted({r.data_status for r in results})),
        },
        {
            "key": "techniques_exported",
            "value": ",".join(sorted({r.technique for r in results})),
        },
    ]
    for tech, mid in sorted(tech_models.items()):
        run_kv.append({"key": f"selected_technique_model.{tech}", "value": mid})
    for k, v in sorted(run_metadata.items()):
        run_kv.append({"key": str(k), "value": str(v)})
    run_summary = pd.DataFrame(run_kv)

    # Per-technique sheets aliasing common GUI expectation
    tech_blocks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tech_blocks[str(row.get("technique") or "unknown")].append(row)

    harm_results = [
        r
        for r in results
        if "harmonic" in str(r.technique or "").lower() or r.support_class is not None
    ]
    coverage_rows = []
    try:
        from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
            build_coverage_manifest_rows,
            write_coverage_manifests,
        )

        write_coverage_manifests()
        for inst in sorted({r.instrument for r in harm_results} or {"vln", "vla", "vlc"}):
            coverage_rows.extend(build_coverage_manifest_rows(instrument=inst))
    except Exception as exc:  # pragma: no cover
        coverage_rows = [{"error": str(exc)}]
    coverage_df = pd.DataFrame(coverage_rows)

    source_sel_rows = []
    transfer_rows = []
    unsupported_rows = []
    for r in harm_results:
        base = {
            "record_id": r.record_id,
            "target_instrument": r.target_instrument or r.instrument,
            "technique": r.technique,
            "target_dynamic": r.target_dynamic or r.dynamic,
            "pitch": r.pitch,
            "sounding_pitch": r.sounding_pitch,
            "support_class": r.support_class,
            "source_instrument": r.source_instrument,
            "source_collection": r.source_collection,
            "source_technique": r.source_technique,
            "source_dynamic": r.source_dynamic,
            "source_record_ids": ";".join(r.source_record_ids_harmonic or []),
            "ordinary_baseline_record_ids": ";".join(r.ordinary_baseline_record_ids or []),
            "transfer_method": r.transfer_method,
            "transfer_formula": r.transfer_formula,
            "transfer_gate_status": r.transfer_gate_status,
            "cross_instrument_transfer_enabled": r.cross_instrument_transfer_enabled,
            "harmonic_selection_reason": r.harmonic_selection_reason,
            "harmonic_rejection_reason": r.harmonic_rejection_reason,
            "estimate_mean": r.estimate_mean,
            "value_kind": r.value_kind.value,
            "na_reason": r.na_reason,
            "model_status": r.model_status,
            "candidates_json": r.harmonic_candidates_json,
            "calibration_processing_version": r.calibration_processing_version,
        }
        source_sel_rows.append(base)
        if r.support_class == "same_instrument_dynamic_transfer":
            transfer_rows.append(base)
        if r.support_class == "unsupported" or r.estimate_mean is None:
            unsupported_rows.append(base)
    source_sel_df = pd.DataFrame(source_sel_rows)
    transfer_df = pd.DataFrame(transfer_rows)
    unsupported_harm_df = pd.DataFrame(unsupported_rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        methodology.to_excel(writer, sheet_name="Methodology", index=False)
        summary_df.to_excel(writer, sheet_name="Posterior_Summary", index=False)
        # Aliases for GUI / older audit filenames
        summary_df.to_excel(writer, sheet_name="All_Results", index=False)
        summary_df.to_excel(writer, sheet_name="Note_Level_Results", index=False)
        selection_df.to_excel(writer, sheet_name="Model_Selection", index=False)
        audit_df.to_excel(writer, sheet_name="Model_Selection_Audit", index=False)
        alpha_df.to_excel(writer, sheet_name="Technique_Effects", index=False)
        by_technique.to_excel(writer, sheet_name="By_Technique", index=False)
        diagnostics_df.to_excel(writer, sheet_name="Diagnostics", index=False)
        unavailable_df.to_excel(writer, sheet_name="Unavailable", index=False)
        run_summary.to_excel(writer, sheet_name="Run_Summary", index=False)
        comparison_df.to_excel(writer, sheet_name="Model_Comparison", index=False)
        priors_df.to_excel(writer, sheet_name="Priors_Used", index=False)
        coverage_df.to_excel(writer, sheet_name="Harmonic_Coverage", index=False)
        source_sel_df.to_excel(writer, sheet_name="Harmonic_Source_Selection", index=False)
        transfer_df.to_excel(writer, sheet_name="Dynamic_Transfers", index=False)
        unsupported_harm_df.to_excel(writer, sheet_name="Unsupported_Harmonic_Targets", index=False)
        for tech, block in tech_blocks.items():
            pd.DataFrame(block).to_excel(writer, sheet_name=str(tech)[:31], index=False)

    return path
