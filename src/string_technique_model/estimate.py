"""Legacy estimation shim — evidence-gated; no name-based multipliers.

Prefer: python -m string_technique_model predict build ...
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from string_technique_model.density.metric import DensityMetric, load_density_metric
from string_technique_model.literature.activation import DENSITY_ACTIVATING_MAPPINGS
from string_technique_model.prediction.operations import is_density_transform_operation
from string_technique_model.prediction.uncertainty import propagate_metric_only
from string_technique_model.provenance import (
    ProvenanceError,
    provenance_allows_density_activation,
    resolve_parameter_provenance,
)


@dataclass(frozen=True)
class EstimationResult:
    instrument: str
    technique: str
    note: str
    dynamic: str
    ordinary_density: float | None
    estimated_density: float | None
    estimated_mean: float | None
    estimated_std: float | None
    ci_low: float | None
    ci_high: float | None
    estimation_status: str
    evidence_note: str
    n_draws: int
    baseline_collection_ids: tuple[str, ...] = ()
    n_contributing_collections: int = 0
    n_observations_per_collection: dict[str, int] = field(default_factory=dict)
    pooling_method: str | None = None
    collection_weights: dict[str, float] = field(default_factory=dict)
    excluded_collections: dict[str, str] = field(default_factory=dict)
    collection_heterogeneity: float | None = None
    collection_effect_estimates: dict[str, float] = field(default_factory=dict)
    metric_compatibility_status: str | None = None
    target_metric_definition_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["baseline_collection_ids"] = list(self.baseline_collection_ids)
        return payload


def _gate_active_parameters(
    parameters: list[dict[str, Any]],
    instrument: str,
    technique: str,
    *,
    source_registry: Any | None = None,
    extracts: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Only parameters that are explicitly density-active may affect estimates."""
    from string_technique_model.literature.extracts import load_extracts
    from string_technique_model.literature.source_registry import SourceRegistry

    registry = source_registry or SourceRegistry.from_yaml()
    evidence = extracts if extracts is not None else load_extracts()

    out: list[dict[str, Any]] = []
    for param in parameters:
        if param.get("instrument") != instrument or param.get("technique") != technique:
            instruments = param.get("instruments") or [param.get("instrument")]
            techniques = param.get("techniques") or [param.get("technique")]
            if instrument not in instruments or technique not in techniques:
                continue
        if not param.get("active_for_density_prediction"):
            continue
        if param.get("density_mapping_status") not in set(DENSITY_ACTIVATING_MAPPINGS) | {
            "approved_explicit_metric_mapping"
        }:
            continue
        if not is_density_transform_operation(str(param.get("operation_type") or "")):
            continue
        if param.get("parameter_status") in {"prohibited", "unresolved", "qualitative_only"}:
            continue
        resolved = resolve_parameter_provenance(param, registry, evidence)
        if not provenance_allows_density_activation(resolved):
            continue
        out.append(param)
    return out


def estimate_cell(
    *,
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
    ordinary_density: float | None,
    parameters: list[dict[str, Any]],
    n_draws: int,
    random_seed: int,
    metric: DensityMetric | None = None,
    unsupported_reasons: list[dict[str, Any]] | None = None,
    baseline_provenance: dict[str, Any] | None = None,
    strict: bool = False,
) -> EstimationResult:
    metric = metric or load_density_metric()
    prov = baseline_provenance or {}

    def _with_prov(**kwargs: Any) -> EstimationResult:
        return EstimationResult(
            baseline_collection_ids=tuple(prov.get("baseline_collection_ids") or ()),
            n_contributing_collections=int(prov.get("n_contributing_collections") or 0),
            n_observations_per_collection=dict(prov.get("n_observations_per_collection") or {}),
            pooling_method=prov.get("pooling_method"),
            collection_weights=dict(prov.get("collection_weights") or {}),
            excluded_collections=dict(prov.get("excluded_collections") or {}),
            collection_heterogeneity=prov.get("collection_heterogeneity"),
            collection_effect_estimates=dict(prov.get("collection_effect_estimates") or {}),
            metric_compatibility_status=prov.get("metric_compatibility_status"),
            target_metric_definition_id=prov.get("target_metric_definition_id"),
            **kwargs,
        )

    if ordinary_density is None:
        return _with_prov(
            instrument=instrument,
            technique=technique,
            note=note,
            dynamic=dynamic,
            ordinary_density=None,
            estimated_density=None,
            estimated_mean=None,
            estimated_std=None,
            ci_low=None,
            ci_high=None,
            estimation_status="missing_ordinary_baseline",
            evidence_note="No ordinary CDM baseline for this note/dynamic in selected collections.",
            n_draws=n_draws,
        )

    d_ord = float(metric.phi(ordinary_density))

    # Strict mode: only required active params with unresolved provenance fail the call.
    if strict:
        from string_technique_model.literature.extracts import load_extracts
        from string_technique_model.literature.source_registry import SourceRegistry

        registry = SourceRegistry.from_yaml()
        extracts = load_extracts()
        for param in parameters:
            if not param.get("active_for_density_prediction"):
                continue
            if param.get("instrument") not in {instrument, None} and instrument not in (
                param.get("instruments") or []
            ):
                continue
            if param.get("technique") not in {technique, None} and technique not in (
                param.get("techniques") or []
            ):
                continue
            resolved = resolve_parameter_provenance(param, registry, extracts)
            if not provenance_allows_density_activation(resolved):
                raise ProvenanceError(
                    f"unresolved_scientific_provenance for required active parameter "
                    f"{param.get('parameter_id')}: {';'.join(resolved.reasons)}"
                )

    active = _gate_active_parameters(parameters, instrument, technique)
    if not active:
        reason = (
            "No literature-derived technique effect parameters are active after the evidence gate. "
            "Use `predict build` for full Phase-4 outputs."
        )
        if unsupported_reasons:
            hits = [
                u
                for u in unsupported_reasons
                if instrument in (u.get("instruments") or [])
                and technique in (u.get("techniques") or [])
            ]
            if hits:
                reason = hits[0].get("reason") or reason
        return _with_prov(
            instrument=instrument,
            technique=technique,
            note=note,
            dynamic=dynamic,
            ordinary_density=d_ord,
            estimated_density=None,
            estimated_mean=None,
            estimated_std=None,
            ci_low=None,
            ci_high=None,
            estimation_status="not_estimable_from_current_evidence",
            evidence_note=str(reason),
            n_draws=n_draws,
        )

    dist = propagate_metric_only(
        baseline={"baseline_value": d_ord, "baseline_mean": d_ord},
        active_params=active,
        link="log",
        n_draws=n_draws,
        random_seed=random_seed,
    )
    return _with_prov(
        instrument=instrument,
        technique=technique,
        note=note,
        dynamic=dynamic,
        ordinary_density=d_ord,
        estimated_density=float(metric.phi(dist.estimated_density_mean)),
        estimated_mean=dist.estimated_density_mean,
        estimated_std=dist.estimated_density_sd,
        ci_low=dist.estimated_density_q025,
        ci_high=dist.estimated_density_q975,
        estimation_status="estimated",
        evidence_note=f"Applied {len(active)} evidence-gated parameter(s).",
        n_draws=n_draws,
    )


def compare_to_holdout(
    result: EstimationResult,
    holdout_density: float | None,
) -> dict[str, Any]:
    if holdout_density is None:
        return {
            "holdout_density": None,
            "abs_error": None,
            "signed_error": None,
            "comparison_status": "no_holdout",
        }
    if result.estimated_density is None:
        return {
            "holdout_density": float(holdout_density),
            "abs_error": None,
            "signed_error": None,
            "comparison_status": "prediction_unavailable",
        }
    err = float(result.estimated_density - holdout_density)
    return {
        "holdout_density": float(holdout_density),
        "abs_error": abs(err),
        "signed_error": err,
        "comparison_status": "compared",
    }
