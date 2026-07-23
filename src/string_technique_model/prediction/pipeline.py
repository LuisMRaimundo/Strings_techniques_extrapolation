"""Evidence-gated technique prediction pipeline (Phase 4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.density.metric import load_density_metric
from string_technique_model.literature.domain import ALLOWED_INSTRUMENTS, ALLOWED_TECHNIQUES
from string_technique_model.literature.evidence_matrix import build_evidence_matrix
from string_technique_model.literature.extracts import load_extracts
from string_technique_model.literature.outputs import write_text
from string_technique_model.literature.package_ingestion import load_physical_mechanisms
from string_technique_model.literature.parameter_ledger import load_parameter_config
from string_technique_model.literature.source_registry import SourceRegistry
from string_technique_model.models.registry import get_model, list_model_keys
from string_technique_model.prediction.activation import resolve_prediction_parameters
from string_technique_model.prediction.links import select_link
from string_technique_model.prediction.manifest import build_run_id, file_checksum, write_run_manifest
from string_technique_model.prediction.modes import PredictionMode, resolve_activate_user_assumptions
from string_technique_model.prediction.outputs import (
    prediction_summary_markdown,
    write_prediction_outputs,
)
from string_technique_model.prediction.reliability import assign_reliability, evidence_grade_for_cell
from string_technique_model.prediction.requests import PredictionRequest, request_from_baseline_row
from string_technique_model.prediction.uncertainty import cell_seed
from string_technique_model.stable_seed import stable_hex

LOGGER = logging.getLogger(__name__)


@dataclass
class PredictionBuildResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    parameter_ledger_rows: list[dict[str, Any]] = field(default_factory=list)
    mechanism_rows: list[dict[str, Any]] = field(default_factory=list)
    output_files: dict[str, str] = field(default_factory=dict)
    run_id: str = ""
    n_active_parameters_global: int = 0
    n_inactive_parameters_global: int = 0
    activation_failure_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_prediction_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or PACKAGE_ROOT / "configs" / "prediction.yaml")


def _load_baseline(path: Path | str) -> pd.DataFrame:
    path = resolve_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Baseline not found: {path}")
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _baseline_density(row: dict[str, Any]) -> float | None:
    for key in ("baseline_value", "baseline_mean", "baseline_median"):
        if row.get(key) is not None and pd.notna(row.get(key)):
            return float(row[key])
    return None


def _na_prediction_row(
    *,
    prediction_id: str,
    baseline: dict[str, Any],
    request: PredictionRequest,
    status: str,
    evidence_grade: str,
    reliability: str,
    backend: str,
    link: str,
    active_ids: list[str],
    inactive_ids: list[str],
    source_ids: list[str],
    extract_ids: list[str],
    applicability_status: str,
    metric_mapping_status: str | None,
    seed: int,
    model_version: str,
    ledger_version: str,
    transfer_used: bool = False,
    transfer_source: str | None = None,
    created_at: str,
) -> dict[str, Any]:
    return {
        "prediction_id": prediction_id,
        "baseline_cell_id": request.baseline_cell_id or baseline.get("baseline_cell_id"),
        "baseline_run_id": baseline.get("run_id"),
        "instrument": request.instrument,
        "technique": request.target_technique,
        "pitch_name_written": request.pitch_name_written,
        "pitch_midi_written": request.pitch_midi_written,
        "pitch_name_sounding": request.pitch_name_sounding or baseline.get("pitch_name_sounding"),
        "pitch_midi_sounding": request.pitch_midi_sounding
        if request.pitch_midi_sounding is not None
        else baseline.get("pitch_midi_sounding"),
        "dynamic": request.dynamic or baseline.get("dynamic"),
        "string_name": request.string_name or baseline.get("string_name"),
        "harmonic_order": request.harmonic_order,
        "stopped_pitch": request.stopped_pitch or request.stopped_pitch_name,
        "touched_pitch": request.touched_pitch or request.touched_pitch_name,
        "mute_type": request.mute_type,
        "bow_position_ratio": request.bow_position_ratio,
        "baseline_density": _baseline_density(baseline),
        "estimated_density_mean": None,
        "estimated_density_median": None,
        "estimated_density_sd": None,
        "estimated_density_q025": None,
        "estimated_density_q050": None,
        "estimated_density_q975": None,
        "probability_above_ordinary": None,
        "probability_below_ordinary": None,
        "difference_from_ordinary_mean": None,
        "ratio_to_ordinary_median": None,
        "modelling_backend": backend,
        "link_function": link,
        "active_parameter_ids": ";".join(active_ids),
        "inactive_parameter_ids": ";".join(inactive_ids),
        "evidence_source_ids": ";".join(source_ids),
        "evidence_extract_ids": ";".join(extract_ids),
        "evidence_grade": evidence_grade,
        "reliability_class": reliability,
        "transfer_used": transfer_used,
        "transfer_source_instrument": transfer_source,
        "applicability_status": applicability_status,
        "prediction_status": status,
        "metric_mapping_status": metric_mapping_status,
        "numerical_safeguard_applied": False,
        "measured_or_estimated": "modelled",
        "result_basis": "evidence_gated_or_unavailable",
        "literature_validated": False,
        "evidence_based": False,
        "assumption_ids_used": None,
        "result_status": status,
        "assumption_status": "none",
        "assumptions_used": None,
        "calculation_trace": f"no numerical prediction: {status}",
        "warnings": "",
        "provenance": "evidence_gated_phase4;no_active_density_parameters"
        if status.startswith("insufficient") or status.startswith("not_estimable") or status.startswith("qualitative")
        else f"evidence_gated_phase4;{status}",
        "random_seed": seed,
        "model_version": model_version,
        "parameter_ledger_version": ledger_version,
        "created_at_utc": created_at,
    }


def build_predictions(
    *,
    baseline_path: Path | str,
    instruments: list[str] | None = None,
    techniques: list[str] | None = None,
    backend: str = "metric-only",
    output_dir: Path | str | None = None,
    n_draws: int | None = None,
    random_seed: int | None = None,
    allow_transfer: bool = False,
    dry_run: bool = False,
    overwrite: bool = True,
    strict: bool = False,
    dynamic: list[str] | None = None,
    pitch_min: float | None = None,
    pitch_max: float | None = None,
    request_extras_by_technique: dict[str, dict[str, Any]] | None = None,
    mode: PredictionMode | str | None = "evidence_only",
    activate_user_assumptions: bool | None = None,
) -> PredictionBuildResult:
    """Build technique predictions from ordinary baseline + activated literature parameters.

    User assumptions are separate from literature. They remain inactive unless
    ``mode="evidence_plus_user_assumptions"`` or the legacy explicit alias is true.
    Assumption-based numerical results are never labelled literature-validated.
    """
    if backend not in {"metric-only", "spectrum-aware"}:
        raise ValueError(f"Unsupported backend: {backend}")

    instruments = list(instruments or sorted(ALLOWED_INSTRUMENTS))
    techniques = list(techniques or sorted(ALLOWED_TECHNIQUES))
    for inst in instruments:
        if inst not in ALLOWED_INSTRUMENTS:
            raise ValueError(f"Unsupported instrument: {inst}")
    for tech in techniques:
        if tech not in ALLOWED_TECHNIQUES:
            raise ValueError(f"Unsupported technique: {tech}")

    # Ensure legacy specialised model grid matches ontology configuration
    from string_technique_model.ontology import legacy_cell_count

    assert len(list_model_keys()) == legacy_cell_count()

    pred_cfg = load_prediction_config()
    n_draws = int(n_draws if n_draws is not None else pred_cfg["prediction"]["n_draws"])
    random_seed = int(random_seed if random_seed is not None else pred_cfg["prediction"]["random_seed"])
    transfers_enabled = bool(allow_transfer or (pred_cfg.get("transfers") or {}).get("enabled"))
    model_version = str(pred_cfg.get("model_version") or "technique_transform_v0.1.0")
    ua_cfg = pred_cfg.get("user_assumptions") or {}
    # Modes are fail-closed. The legacy Boolean remains an explicit opt-in alias.
    user_assumptions_enabled = bool(activate_user_assumptions) or resolve_activate_user_assumptions(mode)
    allow_assumptions_alongside_literature = bool(ua_cfg.get("allow_alongside_literature", False))
    if user_assumptions_enabled:
        LOGGER.warning(
            "User assumptions ACTIVATED for this run — any numerical results that use them "
            "are assumption-based, not literature-validated, not evidence-based."
        )

    metric = load_density_metric()
    link = select_link("ewsd_v1", mathematical_domain=str(metric.config.get("mathematical_domain") or ""))

    registry = SourceRegistry.from_yaml()
    extracts = load_extracts()
    param_cfg = load_parameter_config()
    candidates = list(param_cfg.get("parameters") or [])
    ledger_version = str(param_cfg.get("version") or "unknown")
    mechanisms = load_physical_mechanisms()
    matrix = build_evidence_matrix(registry, extracts, mechanisms=mechanisms, mode="curated_package")

    baseline_df = _load_baseline(baseline_path)
    # Ordinary only
    if "technique" in baseline_df.columns:
        baseline_df = baseline_df[
            baseline_df["technique"].isna()
            | baseline_df["technique"].astype(str).str.lower().isin({"ordinary", "arco", "ordinario", "nan"})
        ]
    baseline_df = baseline_df[baseline_df["instrument"].isin(instruments)]
    if dynamic:
        baseline_df = baseline_df[baseline_df["dynamic"].isin(dynamic)]
    if pitch_min is not None and "pitch_midi_sounding" in baseline_df.columns:
        baseline_df = baseline_df[baseline_df["pitch_midi_sounding"] >= pitch_min]
    if pitch_max is not None and "pitch_midi_sounding" in baseline_df.columns:
        baseline_df = baseline_df[baseline_df["pitch_midi_sounding"] <= pitch_max]

    if baseline_df.empty:
        raise ValueError("No ordinary baseline rows after filters")

    out_dir = Path(output_dir or PACKAGE_ROOT / "outputs" / "predictions")
    created_at = datetime.now(timezone.utc).isoformat()
    ledger_checksum = file_checksum(PACKAGE_ROOT / "configs" / "literature_parameters.yaml")
    matrix_checksum = file_checksum(
        PACKAGE_ROOT / "outputs" / "literature" / "rebuilt_evidence_matrix.csv"
    )
    baseline_run_id = str(baseline_df.iloc[0].get("run_id") or "unknown_baseline")
    run_id = build_run_id(
        baseline_run_id=baseline_run_id,
        instruments=instruments,
        techniques=techniques,
        backend=backend,
        seed=random_seed,
        n_draws=n_draws,
        ledger_checksum=ledger_checksum,
        matrix_checksum=matrix_checksum,
    )

    rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    mechanism_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    all_failure_reasons: set[str] = set()
    n_active_global = 0
    n_inactive_global = 0

    extras_map = request_extras_by_technique or {}

    for _, brow in baseline_df.iterrows():
        baseline: dict[str, Any] = {str(k): v for k, v in brow.to_dict().items()}
        for technique in techniques:
            request = request_from_baseline_row(
                baseline,
                technique=technique,
                backend=backend,
                extras=extras_map.get(technique),
            )
            context = request.to_context()
            model = get_model(request.instrument, technique)
            grade = evidence_grade_for_cell(matrix, request.instrument, technique)
            pred_id = "PRED_" + stable_hex(
                run_id,
                request.instrument,
                technique,
                request.baseline_cell_id or baseline.get("baseline_cell_id"),
                request.pitch_midi_sounding,
                request.dynamic,
                request.harmonic_order,
                request.mute_type,
                n_chars=16,
            )
            seed = cell_seed(run_id, pred_id, random_seed)

            # Spectrum-aware refusal without spectral input
            if backend == "spectrum-aware":
                spec = request.spectral_representation or baseline.get("spectral_representation")
                if not isinstance(spec, dict) or not {
                    "audio",
                    "fft",
                    "psd",
                    "stft",
                    "partial_amplitudes",
                    "band_energy",
                }.intersection(spec.keys()):
                    row = _na_prediction_row(
                        prediction_id=pred_id,
                        baseline=baseline,
                        request=request,
                        status="incompatible_metric",
                        evidence_grade=grade,
                        reliability="NA",
                        backend=backend,
                        link=link,
                        active_ids=[],
                        inactive_ids=[str(p.get("parameter_id")) for p in candidates],
                        source_ids=[],
                        extract_ids=[],
                        applicability_status="insufficient_metadata",
                        metric_mapping_status="insufficient_information",
                        seed=seed,
                        model_version=model_version,
                        ledger_version=ledger_version,
                        created_at=created_at,
                    )
                    row["prediction_status"] = "incompatible_metric"
                    row["provenance"] = "spectrum-aware refused: no spectral representation"
                    rows.append(row)
                    continue

            ctx_result = model.validate_context(baseline, context)
            # For techniques with heavy required metadata (harmonics/mutes), if extras not provided
            # return insufficient_context rather than inventing values.
            if not ctx_result.ok:
                # Still record mechanism-only constraints
                for m in mechanisms:
                    if m.get("instrument") == request.instrument and m.get("technique") == technique:
                        if m.get("supported") in {True, "true", "partially_supported"} or str(
                            m.get("status")
                        ).startswith("support"):
                            mechanism_rows.append(
                                {
                                    "prediction_id": pred_id,
                                    "instrument": request.instrument,
                                    "technique": technique,
                                    "mechanism_name": m.get("mechanism_name"),
                                    "mechanism_supported": True,
                                    "numerical_parameter_available": False,
                                    "missing_parameter": "density_transform_coefficient",
                                    "constraint_note": m.get("reason"),
                                }
                            )
                status = ctx_result.status
                row = _na_prediction_row(
                    prediction_id=pred_id,
                    baseline=baseline,
                    request=request,
                    status=status,
                    evidence_grade=grade,
                    reliability="NA",
                    backend=backend,
                    link=link,
                    active_ids=[],
                    inactive_ids=[],
                    source_ids=[],
                    extract_ids=[],
                    applicability_status="insufficient_metadata",
                    metric_mapping_status=None,
                    seed=seed,
                    model_version=model_version,
                    ledger_version=ledger_version,
                    created_at=created_at,
                )
                rows.append(row)
                if strict and status == "insufficient_context_metadata":
                    warnings.append(f"{pred_id}: {status}: {ctx_result.missing_required}")
                continue

            records = resolve_prediction_parameters(
                candidates,
                registry=registry,
                extracts=extracts,
                context=context,
                backend=backend,
                transfers_enabled=transfers_enabled,
                allow_wider_without_metadata=bool(
                    pred_cfg["prediction"].get("allow_wider_conditional_without_metadata")
                ),
            )
            active = [r.parameter for r in records if r.status == "active"]
            inactive = [r for r in records if r.status == "inactive"]
            n_active_global += len(active)
            n_inactive_global += len(inactive)
            for r in records:
                all_failure_reasons.update(r.reasons)
                ledger_row = r.to_row(pred_id)
                ledger_rows.append(ledger_row)

            used_user_assumptions = False
            assumption_records = []
            if not active or (user_assumptions_enabled and allow_assumptions_alongside_literature):
                from string_technique_model.assumptions import resolve_user_assumptions

                assumption_records = resolve_user_assumptions(
                    context=context,
                    link=link,
                    activation_enabled=user_assumptions_enabled,
                    path=ua_cfg.get("registry_path"),
                )
                for ar in assumption_records:
                    ledger_rows.append(ar.to_row(pred_id))
                    all_failure_reasons.update(ar.reasons)
                    if ar.status != "active":
                        n_inactive_global += 1
                active_assumptions = [ar.assumption for ar in assumption_records if ar.status == "active"]
                if user_assumptions_enabled and active_assumptions and not active:
                    active = active_assumptions
                    used_user_assumptions = True
                    n_active_global += len(active_assumptions)
                elif (
                    user_assumptions_enabled
                    and active_assumptions
                    and active
                    and allow_assumptions_alongside_literature
                ):
                    # Mixing is allowed only when explicitly configured; still label as assumption-tainted.
                    active = list(active) + active_assumptions
                    used_user_assumptions = True
                    n_active_global += len(active_assumptions)

            # Mechanism-only rows
            has_numeric = bool(active)
            for m in mechanisms:
                if m.get("instrument") == request.instrument and m.get("technique") == technique:
                    supported = m.get("supported") in {True, "true", "partially_supported"} or str(
                        m.get("status")
                    ).startswith("support")
                    if supported and not has_numeric:
                        mechanism_rows.append(
                            {
                                "prediction_id": pred_id,
                                "instrument": request.instrument,
                                "technique": technique,
                                "mechanism_name": m.get("mechanism_name"),
                                "mechanism_supported": True,
                                "numerical_parameter_available": False,
                                "missing_parameter": "density_transform_coefficient",
                                "constraint_note": m.get("reason"),
                            }
                        )

            if not active:
                # Do NOT copy ordinary value as technique prediction
                status = (
                    "qualitative_constraints_only"
                    if any(m["prediction_id"] == pred_id for m in mechanism_rows)
                    else "insufficient_active_parameters"
                )
                row = _na_prediction_row(
                    prediction_id=pred_id,
                    baseline=baseline,
                    request=request,
                    status=status,
                    evidence_grade=grade,
                    reliability=assign_reliability(
                        evidence_grade=grade,
                        prediction_status=status,
                        transfer_used=False,
                        n_active=0,
                    ),
                    backend=backend,
                    link=link,
                    active_ids=[],
                    inactive_ids=[r.parameter_id for r in records if r.status != "active"]
                    + [ar.assumption_id for ar in assumption_records if ar.status != "active"],
                    source_ids=[],
                    extract_ids=[],
                    applicability_status="resolved",
                    metric_mapping_status="insufficient_information",
                    seed=seed,
                    model_version=model_version,
                    ledger_version=ledger_version,
                    created_at=created_at,
                )
                # Prove ordinary not copied
                assert row["estimated_density_mean"] is None
                assert row["baseline_density"] is not None or _baseline_density(baseline) is None
                if assumption_records:
                    row["assumption_status"] = "inactive_available"
                    row["calculation_trace"] += "; applicable user assumptions were not activated"
                rows.append(row)
                continue

            # Active path — Monte Carlo
            transfer_used = any(
                p.get("direct_or_transferred") == "transferred" for p in active
            )
            transfer_source = next(
                (p.get("transfer_source_instrument") for p in active if p.get("transfer_source_instrument")),
                None,
            )
            transfer_sd = None
            if transfer_used:
                transfer_cfg = pred_cfg.get("transfers") or {}
                configured_sd = transfer_cfg.get("uncertainty_sd")
                if configured_sd is None:
                    # No hidden default: transfer remains inactive without explicit SD.
                    raise ValueError(
                        "transfer used but transfers.uncertainty_sd is unset in prediction.yaml; "
                        "refusing hidden transfer_sd default"
                    )
                transfer_sd = float(configured_sd)
            dist = model.predict_metric(
                baseline,
                model.sample_parameters(active, n_draws, seed),
                context,
                active_parameters=active,
                link=link,
                n_draws=n_draws,
                random_seed=seed,
                transfer_uncertainty_sd=transfer_sd,
            )
            # Apply Phi identity to predicted densities
            mean = metric.phi(dist.estimated_density_mean)
            if used_user_assumptions:
                from string_technique_model.assumptions import assumption_label_fields

                assumption_ids = [
                    str(p.get("parameter_id"))
                    for p in active
                    if p.get("result_basis") == "user_assumption"
                ]
                label_fields = assumption_label_fields(assumption_ids)
                status = label_fields["prediction_status"]
                reliability = "D"
                source_ids = sorted(
                    {
                        sid
                        for p in active
                        for sid in (p.get("source_ids") or [])
                    }
                )
                extract_ids = []
            else:
                status = (
                    "predicted_with_transfer"
                    if transfer_used
                    else (
                        "predicted_direct_evidence"
                        if grade == "A"
                        else "predicted_with_explicit_mapping"
                    )
                )
                reliability = assign_reliability(
                    evidence_grade=grade,
                    prediction_status=status,
                    transfer_used=transfer_used,
                    n_active=len(active),
                )
                source_ids = sorted(
                    {
                        sid
                        for p in active
                        for sid in (p.get("source_ids") or [])
                    }
                )
                extract_ids = sorted(
                    {
                        eid
                        for p in active
                        for eid in (p.get("evidence_ids") or [])
                    }
                )
                label_fields = {
                    "result_basis": "literature_evidence",
                    "literature_validated": True,
                    "evidence_based": True,
                    "assumption_ids_used": None,
                    "measured_or_estimated": "modelled",
                    "provenance": f"evidence_gated_phase4;{status}",
                    "evidence_grade": grade,
                    "metric_mapping_status": "direct_same_metric",
                }
            for r in records:
                if r.status == "active" and r.parameter_id in dist.parameter_draw_summaries:
                    # enrich ledger
                    for lr in ledger_rows:
                        if lr["prediction_id"] == pred_id and lr["parameter_id"] == r.parameter_id:
                            lr["sampled_parameter_summary"] = str(
                                dist.parameter_draw_summaries[r.parameter_id]
                            )
                            lr["used_or_not_used"] = "used"
            for ar in assumption_records:
                if ar.status == "active" and ar.assumption_id in dist.parameter_draw_summaries:
                    for lr in ledger_rows:
                        if lr["prediction_id"] == pred_id and lr["parameter_id"] == ar.assumption_id:
                            lr["sampled_parameter_summary"] = str(
                                dist.parameter_draw_summaries[ar.assumption_id]
                            )
                            lr["used_or_not_used"] = "used"

            rows.append(
                {
                    "prediction_id": pred_id,
                    "baseline_cell_id": request.baseline_cell_id or baseline.get("baseline_cell_id"),
                    "baseline_run_id": baseline.get("run_id"),
                    "instrument": request.instrument,
                    "technique": technique,
                    "pitch_name_written": request.pitch_name_written,
                    "pitch_midi_written": request.pitch_midi_written,
                    "pitch_name_sounding": request.pitch_name_sounding
                    or baseline.get("pitch_name_sounding"),
                    "pitch_midi_sounding": request.pitch_midi_sounding
                    if request.pitch_midi_sounding is not None
                    else baseline.get("pitch_midi_sounding"),
                    "dynamic": request.dynamic or baseline.get("dynamic"),
                    "string_name": request.string_name,
                    "harmonic_order": request.harmonic_order,
                    "stopped_pitch": request.stopped_pitch or request.stopped_pitch_name,
                    "touched_pitch": request.touched_pitch,
                    "mute_type": request.mute_type,
                    "bow_position_ratio": request.bow_position_ratio,
                    "baseline_density": _baseline_density(baseline),
                    "estimated_density_mean": mean,
                    "estimated_density_median": dist.estimated_density_median,
                    "estimated_density_sd": dist.estimated_density_sd,
                    "estimated_density_q025": dist.estimated_density_q025,
                    "estimated_density_q050": dist.estimated_density_q050,
                    "estimated_density_q975": dist.estimated_density_q975,
                    "probability_above_ordinary": dist.probability_above_ordinary,
                    "probability_below_ordinary": dist.probability_below_ordinary,
                    "difference_from_ordinary_mean": dist.difference_from_ordinary_mean,
                    "ratio_to_ordinary_median": dist.ratio_to_ordinary_median,
                    "modelling_backend": backend,
                    "link_function": link,
                    "active_parameter_ids": ";".join(str(p["parameter_id"]) for p in active),
                    "inactive_parameter_ids": ";".join(
                        [r.parameter_id for r in records if r.status != "active"]
                        + [ar.assumption_id for ar in assumption_records if ar.status != "active"]
                    ),
                    "evidence_source_ids": ";".join(str(x) for x in source_ids),
                    "evidence_extract_ids": ";".join(str(x) for x in extract_ids),
                    "evidence_grade": label_fields.get("evidence_grade", grade),
                    "reliability_class": reliability,
                    "transfer_used": transfer_used,
                    "transfer_source_instrument": transfer_source,
                    "applicability_status": "matched",
                    "prediction_status": status,
                    "metric_mapping_status": label_fields.get(
                        "metric_mapping_status",
                        active[0].get("density_mapping_status"),
                    ),
                    "numerical_safeguard_applied": dist.numerical_safeguard_applied,
                    "measured_or_estimated": label_fields.get(
                        "measured_or_estimated", "modelled"
                    ),
                    "result_basis": label_fields.get("result_basis"),
                    "literature_validated": bool(label_fields.get("literature_validated")),
                    "evidence_based": bool(label_fields.get("evidence_based")),
                    "assumption_ids_used": label_fields.get("assumption_ids_used"),
                    "result_status": status,
                    "assumption_status": "applied" if used_user_assumptions else "none",
                    "assumptions_used": label_fields.get("assumption_ids_used"),
                    "calculation_trace": (
                        f"Monte Carlo density transform using {len(active)} active parameter(s); "
                        f"mode={'evidence_plus_user_assumptions' if user_assumptions_enabled else 'evidence_only'}"
                    ),
                    "warnings": (
                        "ASSUMPTION-BASED: not literature-validated or evidence-based."
                        if used_user_assumptions
                        else ""
                    ),
                    "provenance": label_fields.get(
                        "provenance", f"evidence_gated_phase4;active={len(active)}"
                    ),
                    "random_seed": seed,
                    "model_version": model_version,
                    "parameter_ledger_version": ledger_version,
                    "created_at_utc": created_at,
                }
            )

    result = PredictionBuildResult(
        rows=rows,
        parameter_ledger_rows=ledger_rows,
        mechanism_rows=mechanism_rows,
        run_id=run_id,
        n_active_parameters_global=n_active_global,
        n_inactive_parameters_global=n_inactive_global,
        activation_failure_reasons=sorted(all_failure_reasons),
        warnings=warnings,
    )

    # Domain guard
    if any(r["instrument"] not in ALLOWED_INSTRUMENTS for r in rows):
        raise RuntimeError("Unsupported instrument entered prediction output")
    if any(r["technique"] not in ALLOWED_TECHNIQUES for r in rows):
        raise RuntimeError("Unsupported technique entered prediction output")
    if any(r.get("measured_or_estimated") == "measured" for r in rows):
        raise RuntimeError("Estimates must not be marked measured")

    if not dry_run:
        if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
            raise FileExistsError(f"Output exists and overwrite=False: {out_dir}")
        out_dir.mkdir(parents=True, exist_ok=True)
        files = write_prediction_outputs(
            rows, ledger_rows, mechanism_rows, output_dir=out_dir
        )
        manifest_path = out_dir / "run_manifest.json"
        write_run_manifest(
            manifest_path,
            {
                "run_id": run_id,
                "baseline_run_id": baseline_run_id,
                "metric_definition": metric.name,
                "selected_instruments": instruments,
                "selected_techniques": techniques,
                "model_backend": backend,
                "link_function": link,
                "active_parameter_ledger_checksum": ledger_checksum,
                "evidence_matrix_checksum": matrix_checksum,
                "n_monte_carlo_draws": n_draws,
                "random_seed": random_seed,
                "transfer_configuration": pred_cfg.get("transfers"),
                "user_assumptions_activation_enabled": user_assumptions_enabled,
                "output_files": files,
                "warnings": warnings,
                "exclusions": [],
                "n_rows": len(rows),
                "n_numerical_estimates": sum(
                    1 for r in rows if r.get("estimated_density_mean") is not None
                ),
                "n_na": sum(1 for r in rows if r.get("estimated_density_mean") is None),
            },
        )
        files["run_manifest.json"] = str(manifest_path)
        reports = PACKAGE_ROOT / "reports"
        files["prediction_summary.md"] = write_text(
            reports / "prediction_summary.md", prediction_summary_markdown(rows)
        )
        result.output_files = files
        LOGGER.info(
            "Predictions written run_id=%s rows=%s numerical=%s",
            run_id,
            len(rows),
            sum(1 for r in rows if r.get("estimated_density_mean") is not None),
        )
    return result
