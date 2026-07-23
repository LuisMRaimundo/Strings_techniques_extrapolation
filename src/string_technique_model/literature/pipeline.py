"""Orchestrate literature inventory, matrix, ledger, gaps, and validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_run_config
from string_technique_model.literature.bibliography import (
    export_verified_bibtex,
    incomplete_source_rows,
    verified_source_rows,
)
from string_technique_model.literature.conflicts import conflict_rows, load_conflicts
from string_technique_model.literature.corpus import (
    local_corpus_status_markdown,
    scan_corpus,
)
from string_technique_model.literature.density_mapping import (
    load_density_mappings,
    mapping_markdown,
    mapping_matrix_rows,
)
from string_technique_model.literature.evidence_matrix import matrix_markdown
from string_technique_model.literature.extracts import extracts_to_rows, load_extracts
from string_technique_model.literature.gaps import build_gap_rows, gaps_markdown
from string_technique_model.literature.inventory import build_inventory_rows, inventory_markdown
from string_technique_model.literature.outputs import write_csv, write_text
from string_technique_model.literature.package_ingestion import ingest_evidence_package
from string_technique_model.literature.parameter_ledger import (
    build_parameter_ledger_rows,
    load_parameter_config,
)
from string_technique_model.literature.source_registry import SourceRegistry
from string_technique_model.literature.transfers import load_transfer_candidates, transfer_rows
from string_technique_model.literature.validation import (
    LiteratureValidationError,
    validate_literature_layer,
    validation_report_markdown,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class LiteratureBuildResult:
    inventory_rows: list[dict[str, Any]]
    extract_rows: list[dict[str, Any]]
    matrix_rows: list[dict[str, Any]]
    parameter_rows: list[dict[str, Any]]
    transfer_rows_data: list[dict[str, Any]]
    conflict_rows_data: list[dict[str, Any]]
    gap_rows: list[dict[str, Any]]
    mapping_rows: list[dict[str, Any]]
    validation: dict[str, Any]
    output_files: dict[str, str] = field(default_factory=dict)
    n_verified_sources: int = 0
    n_incomplete_sources: int = 0
    n_excluded_sources: int = 0
    package_summary: dict[str, Any] = field(default_factory=dict)
    n_active_density_parameters: int = 0
    n_inactive_parameters: int = 0


def _default_output_dir(run_config_path: Path | str | None = None) -> Path:
    try:
        cfg = load_run_config(run_config_path)
        paths = cfg.get("paths_resolved") or {}
        if paths.get("outputs_dir"):
            return Path(paths["outputs_dir"]) / "literature"
    except Exception:  # noqa: BLE001
        pass
    return PACKAGE_ROOT / "outputs" / "literature"


def build_literature_layer(
    *,
    run_config_path: Path | str | None = None,
    source_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    dry_run: bool = False,
    overwrite: bool = True,
    strict: bool = False,
    instrument: list[str] | None = None,
    technique: list[str] | None = None,
) -> LiteratureBuildResult:
    """Build all Phase-3 literature artefacts. Does not produce technique densities."""
    registry = SourceRegistry.from_yaml()
    extracts = load_extracts()
    param_cfg = load_parameter_config()
    transfers = load_transfer_candidates()
    conflicts = load_conflicts()
    mappings = load_density_mappings()
    corpus_scan = scan_corpus(source_dir, registry=registry)

    package = ingest_evidence_package(
        output_dir=output_dir or _default_output_dir(run_config_path),
        dry_run=True,
        overwrite=overwrite,
    )

    inventory = build_inventory_rows(registry)
    extract_rows = extracts_to_rows(extracts)
    full_matrix = package.rebuilt_matrix
    matrix = full_matrix
    if instrument:
        matrix = [r for r in matrix if r["instrument"] in set(instrument)]
    if technique:
        matrix = [r for r in matrix if r["technique"] in set(technique)]
    parameters = build_parameter_ledger_rows(param_cfg)
    trows = transfer_rows(transfers)
    crows = conflict_rows(conflicts)
    grows = build_gap_rows(full_matrix)
    mrows = mapping_matrix_rows(mappings)

    validation = validate_literature_layer(
        registry=registry,
        extracts=extracts,
        matrix_rows=full_matrix,
        parameter_rows=parameters,
        transfer_rows=trows,
        strict=strict,
    )

    out = Path(output_dir or _default_output_dir(run_config_path))
    reports = PACKAGE_ROOT / "reports"
    files: dict[str, str] = {}

    if not dry_run:
        # Write curated package validation artefacts (scientific authority outputs).
        package_written = ingest_evidence_package(
            output_dir=out,
            reports_dir=reports,
            dry_run=False,
            overwrite=overwrite,
        )
        files.update(package_written.output_files)

        if out.exists() and any(out.iterdir()) and not overwrite:
            raise FileExistsError(f"Output directory exists and overwrite=False: {out}")
        out.mkdir(parents=True, exist_ok=True)

        files["literature_inventory.csv"] = write_csv(out / "literature_inventory.csv", inventory)
        # evidence_extracts / matrix / ledger / density_mapping written by package ingestion
        files["transfer_candidates.csv"] = write_csv(out / "transfer_candidates.csv", trows)
        files["evidence_conflicts.csv"] = write_csv(
            out / "evidence_conflicts.csv",
            crows,
            columns=[
                "conflict_id",
                "instrument",
                "technique",
                "acoustic_variable",
                "source_ids",
                "evidence_ids",
                "nature_of_conflict",
                "proposed_resolution_status",
            ],
        )
        files["literature_gaps.csv"] = write_csv(out / "literature_gaps.csv", grows)
        files["verified_sources.csv"] = write_csv(
            out / "verified_sources.csv",
            verified_source_rows(registry),
            columns=[
                "source_id",
                "full_citation",
                "DOI",
                "ISBN",
                "year",
                "title",
                "evidence_status",
                "local_file_path",
            ],
        )
        files["incomplete_references.csv"] = write_csv(
            out / "incomplete_references.csv",
            incomplete_source_rows(registry),
            columns=[
                "source_id",
                "full_citation",
                "evidence_status",
                "missing_title",
                "missing_year",
                "missing_authors",
                "missing_journal_or_publisher",
                "missing_volume",
                "missing_issue",
                "missing_pages",
                "missing_DOI",
                "missing_ISBN",
                "missing_stable_url",
                "notes",
            ],
        )
        n_bib = export_verified_bibtex(registry, out / "verified_sources.bib")
        files["verified_sources.bib"] = str(out / "verified_sources.bib")

        search_done = bool(registry.meta.get("corpus_search_completed"))
        files["literature_inventory.md"] = write_text(
            reports / "literature_inventory.md",
            inventory_markdown(inventory, corpus_search_completed=search_done),
        )
        files["instrument_technique_evidence_matrix.md"] = write_text(
            reports / "instrument_technique_evidence_matrix.md",
            matrix_markdown(full_matrix),
        )
        files["literature_to_density_mapping.md"] = write_text(
            reports / "literature_to_density_mapping.md",
            mapping_markdown(mappings),
        )
        files["literature_gaps.md"] = write_text(
            reports / "literature_gaps.md",
            gaps_markdown(grows, search_completed=search_done),
        )
        files["literature_validation_report.md"] = write_text(
            reports / "literature_validation_report.md",
            validation_report_markdown(validation),
        )
        files["local_corpus_status.md"] = write_text(
            reports / "local_corpus_status.md",
            local_corpus_status_markdown(corpus_scan),
        )
        LOGGER.info(
            "Literature layer written: verified=%s incomplete=%s extracts=%s matrix=%s bib=%s corpus_files=%s",
            len(registry.verified()),
            len(incomplete_source_rows(registry)),
            len(extract_rows),
            len(full_matrix),
            n_bib,
            corpus_scan.n_files_found,
        )
    else:
        LOGGER.info("Literature layer dry-run: matrix=%s extracts=%s", len(full_matrix), len(extracts))

    return LiteratureBuildResult(
        inventory_rows=inventory,
        extract_rows=extract_rows,
        matrix_rows=full_matrix if not (instrument or technique) else matrix,
        parameter_rows=parameters,
        transfer_rows_data=trows,
        conflict_rows_data=crows,
        gap_rows=grows,
        mapping_rows=mrows,
        validation=validation,
        output_files=files,
        n_verified_sources=len(registry.verified()),
        n_incomplete_sources=len(incomplete_source_rows(registry)),
        n_excluded_sources=len(registry.excluded()),
        package_summary=package.summary,
        n_active_density_parameters=len(package.active_parameters),
        n_inactive_parameters=len(package.inactive_parameters),
    )


def validate_sources_only() -> dict[str, Any]:
    registry = SourceRegistry.from_yaml()
    incomplete = incomplete_source_rows(registry)
    return {
        "n_sources": len(registry.list_sources()),
        "n_verified": len(registry.verified()),
        "n_incomplete": len(incomplete),
        "n_excluded": len(registry.excluded()),
        "incomplete_source_ids": [r["source_id"] for r in incomplete],
        "verified_source_ids": [s.source_id for s in registry.verified()],
        "excluded_source_ids": [s.source_id for s in registry.excluded()],
        "ok": True,
    }


def validate_all(*, strict: bool = False) -> dict[str, Any]:
    try:
        result = build_literature_layer(dry_run=True, strict=strict)
        return result.validation
    except LiteratureValidationError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
