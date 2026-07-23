"""CLI for specialised-literature evidence layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def register_literature_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    lit = subparsers.add_parser("literature", help="Specialised-literature evidence layer (Phase 3)")
    sub = lit.add_subparsers(dest="literature_command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--source-dir", type=Path, default=None)
    common.add_argument("--output-dir", type=Path, default=None)
    common.add_argument("--strict", action="store_true")
    common.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=True)
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--instrument", nargs="+", default=None)
    common.add_argument("--technique", nargs="+", default=None)
    common.add_argument("--run-config", type=Path, default=None)

    sub.add_parser("inventory", parents=[common], help="Build literature inventory")
    sub.add_parser("validate-sources", parents=[common], help="Validate source registry")
    sub.add_parser("build-evidence-matrix", parents=[common], help="Build 16-cell evidence matrix")
    sub.add_parser("build-parameter-ledger", parents=[common], help="Build parameter evidence ledger")
    sub.add_parser("report-gaps", parents=[common], help="Report literature gaps")
    sub.add_parser("export-bibtex", parents=[common], help="Export verified sources BibTeX")
    sub.add_parser("validate-all", parents=[common], help="Validate entire literature layer")
    sub.add_parser("build-all", parents=[common], help="Build all literature artefacts")
    sub.add_parser(
        "ingest-package",
        parents=[common],
        help="Ingest/validate curated evidence package (no density prediction)",
    )
    sub.add_parser("scan-corpus", parents=[common], help="Scan local literature/corpus files")

    reg = sub.add_parser("register-source", help="Register a local corpus file to a source_id")
    reg.add_argument("--source-id", required=True)
    reg.add_argument("--file", required=True, type=Path, dest="file_path")
    reg.add_argument("--citation-file", type=Path, default=None)
    reg.add_argument("--full-citation", default=None)
    reg.add_argument("--title", default=None)
    reg.add_argument("--year", type=int, default=None)
    reg.add_argument("--authors", nargs="+", default=None)
    reg.add_argument("--journal-or-publisher", default=None)
    reg.add_argument("--instruments", nargs="+", default=None)
    reg.add_argument("--techniques", nargs="+", default=None)
    reg.add_argument("--dry-run", action="store_true")

    add = sub.add_parser("add-extract", help="Curate a page-level evidence extract")
    add.add_argument("--source-id", required=True)
    add.add_argument("--instrument", required=True)
    add.add_argument("--technique", required=True)
    add.add_argument("--paraphrased-claim", required=True)
    add.add_argument("--quantitative-or-qualitative", required=True)
    add.add_argument("--measured-variable", required=True)
    add.add_argument("--directness", required=True)
    add.add_argument("--curator-verification-status", required=True)
    add.add_argument("--page", dest="page_start", default=None)
    add.add_argument("--page-end", default=None)
    add.add_argument("--table-number", default=None)
    add.add_argument("--figure-number", default=None)
    add.add_argument("--equation-number", default=None)
    add.add_argument("--section-title", default=None)
    add.add_argument("--unit", default=None)
    add.add_argument("--reported-value", type=float, default=None)
    add.add_argument("--dry-run", action="store_true")


def run_literature_command(args: argparse.Namespace) -> int:
    from string_technique_model.literature import corpus, pipeline

    cmd = args.literature_command
    if cmd == "validate-sources":
        print(json.dumps(pipeline.validate_sources_only(), indent=2, default=str))
        return 0
    if cmd == "validate-all":
        payload = pipeline.validate_all(strict=bool(args.strict))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1
    if cmd == "ingest-package":
        from string_technique_model.literature.package_ingestion import ingest_evidence_package

        result = ingest_evidence_package(
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run),
            overwrite=bool(args.overwrite),
        )
        print(json.dumps(result.summary, indent=2, default=str))
        return 0
    if cmd == "scan-corpus":
        scan = corpus.scan_corpus(args.source_dir)
        report = corpus.local_corpus_status_markdown(scan)
        from string_technique_model.config import PACKAGE_ROOT

        out = PACKAGE_ROOT / "reports" / "local_corpus_status.md"
        if not args.dry_run:
            out.write_text(report, encoding="utf-8")
        print(json.dumps(scan.to_dict(), indent=2, default=str))
        return 0
    if cmd == "register-source":
        result = corpus.register_source(
            source_id=args.source_id,
            file_path=args.file_path,
            citation_file=args.citation_file,
            full_citation=args.full_citation,
            title=args.title,
            year=args.year,
            authors=args.authors,
            journal_or_publisher=args.journal_or_publisher,
            instruments=args.instruments,
            techniques=args.techniques,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0
    if cmd == "add-extract":
        result = corpus.add_extract(
            source_id=args.source_id,
            instrument=args.instrument,
            technique=args.technique,
            paraphrased_claim=args.paraphrased_claim,
            quantitative_or_qualitative=args.quantitative_or_qualitative,
            measured_variable=args.measured_variable,
            directness=args.directness,
            curator_verification_status=args.curator_verification_status,
            page_start=args.page_start,
            page_end=args.page_end,
            table_number=args.table_number,
            figure_number=args.figure_number,
            equation_number=args.equation_number,
            section_title=args.section_title,
            unit=args.unit,
            reported_value=args.reported_value,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, indent=2, default=str))
        return 0

    build = pipeline.build_literature_layer(
        run_config_path=args.run_config,
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        dry_run=bool(args.dry_run),
        overwrite=bool(args.overwrite),
        strict=bool(args.strict),
        instrument=args.instrument,
        technique=args.technique,
    )
    summary: dict[str, Any] = {
        "command": cmd,
        "n_sources_inventory": len(build.inventory_rows),
        "n_verified_sources": build.n_verified_sources,
        "n_incomplete_sources": build.n_incomplete_sources,
        "n_excluded_sources": build.n_excluded_sources,
        "n_extracts": len(build.extract_rows),
        "n_matrix_rows": len(build.matrix_rows),
        "n_parameter_rows": len(build.parameter_rows),
        "n_transfer_candidates": len(build.transfer_rows_data),
        "n_conflicts": len(build.conflict_rows_data),
        "n_gaps": len(build.gap_rows),
        "validation_ok": build.validation.get("ok"),
        "output_files": build.output_files,
        "prediction_values_generated": False,
        "n_active_density_parameters": build.n_active_density_parameters,
        "n_inactive_parameters": build.n_inactive_parameters,
        "package_summary": build.package_summary,
        "framework_note": (
            "Auditable evidence framework; curated package is scientific authority; "
            "no technique-density prediction in this phase."
        ),
    }
    if cmd == "build-evidence-matrix":
        summary["matrix"] = build.matrix_rows
    if cmd == "report-gaps":
        summary["gaps"] = build.gap_rows
    if cmd == "export-bibtex":
        summary["verified_bibtex"] = build.output_files.get("verified_sources.bib")
    print(json.dumps(summary, indent=2, default=str))
    return 0 if build.validation.get("ok") else 1
