"""Scientific parameter provenance — relational resolution via foreign keys.

Canonical representation:
    LiteratureParameter.source_ids  -> LiteratureSource
    LiteratureParameter.evidence_ids -> EvidenceExtract

Full citations resolve from sources; extraction methods resolve from extracts.
Embedded duplication on the parameter row is optional, not required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from string_technique_model.config import resolve_path

PLACEHOLDER_CITATIONS = frozenset(
    {
        "",
        "meyer book",
        "some_source",
        "unknown",
        "n/a",
        "na",
        "tbd",
        "todo",
        "placeholder",
    }
)

PLACEHOLDER_METHODS = frozenset(
    {
        "",
        "unknown",
        "n/a",
        "na",
        "tbd",
        "todo",
        "placeholder",
        "some_method",
    }
)


@dataclass(frozen=True)
class ParameterProvenance:
    """Legacy flat provenance view (optional embedded fields)."""

    parameter_id: str
    parameter_name: str
    instrument: str
    technique: str
    model_component: str
    numerical_value: float | None
    distribution: str | None
    uncertainty: str | dict[str, Any] | None
    unit: str | None
    frequency_range: str | None
    pitch_range: str | None
    register: str | None
    dynamic: str | None
    string: str | None
    temporal_region: str | None
    source_id: str
    full_citation: str
    page: str | None
    table: str | None
    figure: str | None
    equation: str | None
    extraction_method: str
    direct_or_transferred: str
    transfer_source: str | None
    transfer_equation: str | None
    evidence_grade: str
    confidence_level: str
    curator_notes: str


@dataclass
class ResolvedParameterProvenance:
    parameter_id: str
    source_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    full_citations: list[str] = field(default_factory=list)
    source_verification_statuses: list[str] = field(default_factory=list)
    extraction_methods: list[str] = field(default_factory=list)
    source_locations: list[str] = field(default_factory=list)
    curator_verification_statuses: list[str] = field(default_factory=list)
    ok: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProvenanceError(ValueError):
    pass


def _as_id_list(value: Any) -> list[str]:
    """Normalise source_id/source_ids and evidence_id/evidence_ids."""
    if value is None:
        return []
    if isinstance(value, list):
        out = [str(x).strip() for x in value if x is not None and str(x).strip()]
        return out
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # JSON-ish list or semicolon/comma separated CSV serialisation
        if text.startswith("[") and text.endswith("]"):
            try:
                import ast

                parsed = ast.literal_eval(text)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:  # noqa: BLE001
                pass
        if ";" in text:
            return [p.strip() for p in text.split(";") if p.strip()]
        if "," in text and " " not in text.split(",")[0]:
            return [p.strip() for p in text.split(",") if p.strip()]
        return [text]
    return [str(value).strip()] if str(value).strip() else []


def normalize_source_ids(param: dict[str, Any]) -> list[str]:
    """Canonical plural list; migrate unambiguous singular source_id."""
    ids = _as_id_list(param.get("source_ids"))
    if not ids:
        ids = _as_id_list(param.get("source_id"))
    # Reject empty-string placeholders
    return [i for i in ids if i and i.lower() not in PLACEHOLDER_CITATIONS]


def normalize_evidence_ids(param: dict[str, Any]) -> list[str]:
    ids = _as_id_list(param.get("evidence_ids"))
    if not ids:
        ids = _as_id_list(param.get("evidence_id"))
    return [i for i in ids if i and i.lower() not in PLACEHOLDER_CITATIONS]


def _is_placeholder_text(value: str | None, placeholders: frozenset[str]) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    return text.lower() in placeholders


def _location_label(extract: Any) -> str:
    parts: list[str] = []
    if getattr(extract, "page_start", None) is not None:
        pe = getattr(extract, "page_end", None)
        if pe is not None:
            parts.append(f"pages {extract.page_start}-{pe}")
        else:
            parts.append(f"page {extract.page_start}")
    for attr, label in (
        ("table_number", "table"),
        ("figure_number", "figure"),
        ("equation_number", "equation"),
        ("section_title", "section"),
    ):
        val = getattr(extract, attr, None)
        if val:
            parts.append(f"{label} {val}")
    return "; ".join(parts) if parts else ""


def resolve_parameter_provenance(
    parameter: dict[str, Any],
    source_registry: Any,
    evidence_registry: list[Any] | dict[str, Any],
) -> ResolvedParameterProvenance:
    """Resolve citations and extraction methods through foreign keys."""
    pid = str(parameter.get("parameter_id") or "")
    source_ids = normalize_source_ids(parameter)
    evidence_ids = normalize_evidence_ids(parameter)
    reasons: list[str] = []

    if not source_ids:
        reasons.append("missing_source_id")
    if not evidence_ids:
        reasons.append("missing_evidence_id")

    # Index extracts
    if isinstance(evidence_registry, dict):
        by_eid = {str(k): v for k, v in evidence_registry.items()}
    else:
        by_eid = {
            str(getattr(e, "evidence_id", None) or e.get("evidence_id")): e  # type: ignore[union-attr]
            for e in evidence_registry
            if (getattr(e, "evidence_id", None) if not isinstance(e, dict) else e.get("evidence_id"))
        }

    sources_map = getattr(source_registry, "sources", None)
    if sources_map is None and isinstance(source_registry, dict):
        sources_map = source_registry
    if sources_map is None:
        sources_map = {}

    full_citations: list[str] = []
    source_statuses: list[str] = []
    for sid in source_ids:
        src = sources_map.get(sid)
        if src is None:
            reasons.append("missing_source_record")
            continue
        citation = getattr(src, "full_citation", None) if not isinstance(src, dict) else src.get("full_citation")
        status = getattr(src, "evidence_status", None) if not isinstance(src, dict) else src.get("evidence_status")
        if _is_placeholder_text(citation, PLACEHOLDER_CITATIONS):
            reasons.append("placeholder_or_empty_citation")
        else:
            full_citations.append(str(citation).strip())
        source_statuses.append(str(status or ""))
        if status in {"incomplete_reference", "excluded"}:
            reasons.append("incomplete_or_excluded_source")
        if status != "verified_local_source":
            # Not a hard schema failure for inactive params; recorded for activation.
            reasons.append("source_not_verified_local")

    extraction_methods: list[str] = []
    locations: list[str] = []
    curator_statuses: list[str] = []
    for eid in evidence_ids:
        ext = by_eid.get(eid)
        if ext is None:
            reasons.append("missing_evidence_record")
            continue
        if isinstance(ext, dict):
            method = ext.get("extraction_method")
            curator = ext.get("curator_verification_status")
            loc = ""
            if ext.get("page_start") is not None:
                loc = f"pages {ext.get('page_start')}-{ext.get('page_end')}" if ext.get("page_end") else f"page {ext.get('page_start')}"
            elif ext.get("section_title"):
                loc = f"section {ext.get('section_title')}"
        else:
            method = getattr(ext, "extraction_method", None)
            curator = getattr(ext, "curator_verification_status", None)
            loc = _location_label(ext)
            has_loc = ext.has_location() if hasattr(ext, "has_location") else bool(loc)
            if not has_loc:
                reasons.append("missing_source_location")
        if _is_placeholder_text(method, PLACEHOLDER_METHODS):
            reasons.append("placeholder_or_empty_extraction_method")
        else:
            extraction_methods.append(str(method).strip())
        if loc:
            locations.append(loc)
        curator_statuses.append(str(curator or ""))
        if str(curator or "").lower() not in {"validated", "verified"}:
            reasons.append("evidence_not_curator_verified")

    # Deduplicate reasons preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    # Schema-ok when FKs resolve to non-placeholder citation + method + location
    schema_ok = (
        bool(source_ids)
        and bool(evidence_ids)
        and bool(full_citations)
        and bool(extraction_methods)
        and "missing_source_record" not in uniq
        and "missing_evidence_record" not in uniq
        and "placeholder_or_empty_citation" not in uniq
        and "placeholder_or_empty_extraction_method" not in uniq
        and "missing_source_id" not in uniq
        and "missing_evidence_id" not in uniq
    )

    return ResolvedParameterProvenance(
        parameter_id=pid,
        source_ids=source_ids,
        evidence_ids=evidence_ids,
        full_citations=full_citations,
        source_verification_statuses=source_statuses,
        extraction_methods=extraction_methods,
        source_locations=locations,
        curator_verification_statuses=curator_statuses,
        ok=schema_ok,
        reasons=uniq,
    )


def provenance_allows_density_activation(resolved: ResolvedParameterProvenance) -> bool:
    """Activation still requires verified local source + curator-validated extract."""
    if not resolved.ok:
        return False
    if any(s != "verified_local_source" for s in resolved.source_verification_statuses):
        return False
    if any(c.lower() not in {"validated", "verified"} for c in resolved.curator_verification_statuses):
        return False
    if "incomplete_or_excluded_source" in resolved.reasons:
        return False
    return True


def validate_parameter_provenance(
    param: dict[str, Any],
    *,
    source_registry: Any | None = None,
    evidence_registry: list[Any] | dict[str, Any] | None = None,
    require_density_activation_grade: bool = False,
) -> ResolvedParameterProvenance:
    """Validate provenance.

    When registries are supplied, resolve relationally.
    When absent, attempt to load package defaults.
    Does not require duplicated citation text on the parameter row.
    """
    if source_registry is None or evidence_registry is None:
        from string_technique_model.literature.extracts import load_extracts
        from string_technique_model.literature.source_registry import SourceRegistry

        source_registry = source_registry or SourceRegistry.from_yaml()
        evidence_registry = evidence_registry if evidence_registry is not None else load_extracts()

    # Minimal identity fields still required on the parameter itself
    for field_name in (
        "parameter_id",
        "instrument",
        "technique",
        "model_component",
        "direct_or_transferred",
    ):
        if not param.get(field_name) and not (
            field_name == "model_component" and param.get("parameter_name")
        ):
            if field_name == "model_component" and param.get("parameter_role"):
                continue
            raise ProvenanceError(
                f"Scientific parameter missing identity field '{field_name}': "
                f"{param.get('parameter_id')}"
            )

    resolved = resolve_parameter_provenance(param, source_registry, evidence_registry)
    if not resolved.ok:
        raise ProvenanceError(
            f"Unresolved scientific provenance for {param.get('parameter_id')}: "
            f"{';'.join(resolved.reasons)}"
        )

    if require_density_activation_grade and not provenance_allows_density_activation(resolved):
        raise ProvenanceError(
            f"Parameter {param.get('parameter_id')} provenance is schema-valid but "
            f"not activation-grade: {';'.join(resolved.reasons)}"
        )

    if param.get("direct_or_transferred") == "transferred":
        if not (param.get("transfer_source") or param.get("transfer_source_instrument")):
            raise ProvenanceError(
                f"Transferred parameter {param.get('parameter_id')} requires transfer_source"
            )
        if not param.get("transfer_equation"):
            raise ProvenanceError(
                f"Transferred parameter {param.get('parameter_id')} requires transfer_equation"
            )

    # Value presence: reported_value OR bounds OR distribution
    has_value = (
        param.get("numerical_value") is not None
        or param.get("reported_value") is not None
        or param.get("reported_lower_bound") is not None
        or param.get("distribution") is not None
        or param.get("proposed_distribution") is not None
    )
    if not has_value and param.get("parameter_status") not in {"qualitative_only", "prohibited"}:
        raise ProvenanceError(
            f"Parameter {param.get('parameter_id')} has neither numerical value nor distribution"
        )
    return resolved


def validate_all_parameters(
    path: Path | str,
    *,
    strict: bool = False,
    source_registry: Any | None = None,
    evidence_registry: list[Any] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the ledger without crashing on inactive/indirect candidates.

    Strict mode raises only when an *active* density parameter has unresolved provenance.
    """
    from string_technique_model.literature.extracts import load_extracts
    from string_technique_model.literature.source_registry import SourceRegistry

    params = load_literature_parameters(path)
    source_registry = source_registry or SourceRegistry.from_yaml()
    evidence_registry = evidence_registry if evidence_registry is not None else load_extracts()

    results: list[dict[str, Any]] = []
    active_failures: list[str] = []
    inactive_failures: list[dict[str, Any]] = []

    for p in params:
        resolved = resolve_parameter_provenance(p, source_registry, evidence_registry)
        active = bool(p.get("active_for_density_prediction"))
        mapping = p.get("density_mapping_status")
        row = {
            "parameter_id": p.get("parameter_id"),
            "active_for_density_prediction": active,
            "density_mapping_status": mapping,
            "provenance_ok": resolved.ok,
            "activation_grade_ok": provenance_allows_density_activation(resolved),
            "reasons": list(resolved.reasons),
            "source_ids": resolved.source_ids,
            "evidence_ids": resolved.evidence_ids,
            "full_citations": resolved.full_citations,
            "extraction_methods": resolved.extraction_methods,
        }
        # Indirect proxies: never activate; record reason without hard-failing the pipeline
        if mapping == "indirect_proxy":
            row["reasons"] = sorted(set(row["reasons"] + ["indirect_density_proxy"]))
            inactive_failures.append(row)
        elif not resolved.ok:
            if active:
                active_failures.append(
                    f"{p.get('parameter_id')}: unresolved_scientific_provenance "
                    f"({';'.join(resolved.reasons)})"
                )
            else:
                row["reasons"] = sorted(set(row["reasons"] + ["unresolved_scientific_provenance"]))
                inactive_failures.append(row)
        elif active and not provenance_allows_density_activation(resolved):
            active_failures.append(
                f"{p.get('parameter_id')}: unresolved_scientific_provenance "
                f"({';'.join(resolved.reasons)})"
            )
            inactive_failures.append(row)
        results.append(row)

    if strict and active_failures:
        raise ProvenanceError("; ".join(active_failures))

    return {
        "ok": not active_failures,
        "parameters": params,
        "results": results,
        "active_failures": active_failures,
        "inactive_failures": inactive_failures,
    }


def load_literature_parameters(path: Path | str) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(resolve_path(path)).read_text(encoding="utf-8")) or {}
    params = data.get("parameters") or []
    if not isinstance(params, list):
        raise ProvenanceError("literature_parameters.parameters must be a list")
    # Deterministic singular→plural migration for in-memory use
    for p in params:
        p["source_ids"] = normalize_source_ids(p)
        p["evidence_ids"] = normalize_evidence_ids(p)
        if "source_id" in p and not p.get("source_ids"):
            pass  # already handled
        # Drop empty singular placeholders so they cannot "satisfy" old checks
        if p.get("source_id") is not None and str(p.get("source_id")).strip() == "":
            p["source_id"] = None
        if p.get("full_citation") is not None and _is_placeholder_text(
            str(p.get("full_citation")), PLACEHOLDER_CITATIONS
        ):
            p["full_citation"] = None
        if p.get("extraction_method") is not None and _is_placeholder_text(
            str(p.get("extraction_method")), PLACEHOLDER_METHODS
        ):
            p["extraction_method"] = None
    return params


def assert_no_hidden_scientific_constants(
    module_globals: dict[str, Any],
    banned_prefixes: tuple[str, ...] = ("TECH_", "LIT_", "CDM_RATIO"),
) -> None:
    offenders = [k for k in module_globals if k.startswith(banned_prefixes)]
    if offenders:
        raise ProvenanceError(f"Hidden scientific constants forbidden in code: {offenders}")


def parameter_to_ledger_row(param: dict[str, Any]) -> dict[str, Any]:
    row = {f: param.get(f) for f in ParameterProvenance.__annotations__}
    row.update({k: param.get(k) for k in param if k not in row})
    row["source_ids"] = normalize_source_ids(param)
    row["evidence_ids"] = normalize_evidence_ids(param)
    return row


def meyer_dynamic_range_is_not_density(param: dict[str, Any]) -> bool:
    """Guard: Meyer dB dynamic range must remain an indirect proxy."""
    return (
        param.get("parameter_id") == "MEYER_VLN_HARMONIC_DYNAMIC_RANGE"
        and param.get("density_mapping_status") == "indirect_proxy"
        and param.get("active_for_density_prediction") is False
        and param.get("operation_type") == "validity_bound"
        and param.get("numerical_scale") == "decibel_power"
    )
