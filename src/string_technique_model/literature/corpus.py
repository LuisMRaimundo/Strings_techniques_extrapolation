"""Local literature corpus discovery, registration, and extract curation.

Presence of a PDF must never automatically create scientific evidence extracts
or raise evidence grades.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.domain import (
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
    DIRECTNESS_VALUES,
    EXTRACT_VERIFICATION_STATUSES,
)
from string_technique_model.literature.extracts import EvidenceExtract
from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry

LOGGER = logging.getLogger(__name__)

CORPUS_ROOT = PACKAGE_ROOT / "literature" / "corpus"
CORPUS_SUBDIRS = ("books", "articles", "theses", "reports", "metadata")
CORPUS_MANIFEST = CORPUS_ROOT / "metadata" / "corpus_manifest.yaml"
EXTRACTS_PATH = PACKAGE_ROOT / "configs" / "literature_evidence_extracts.yaml"
SOURCES_PATH = PACKAGE_ROOT / "configs" / "literature_sources.yaml"
SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".text"}


@dataclass
class CorpusFileRecord:
    path: str
    sha256: str
    size_bytes: int
    page_count: int | None
    associated_source_id: str | None
    registration_status: str  # registered | unregistered | missing_for_registered_source


@dataclass
class CorpusScanResult:
    corpus_root: str
    n_files_found: int
    n_registered_with_file: int
    n_unregistered_files: int
    n_registered_missing_file: int
    files: list[CorpusFileRecord] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def ensure_corpus_directories() -> list[Path]:
    created: list[Path] = []
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    for name in CORPUS_SUBDIRS:
        path = CORPUS_ROOT / name
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
            created.append(path)
    return created


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def estimate_page_count(path: Path) -> int | None:
    """Best-effort page count. Never invents scientific content."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            # Prefer pypdf if installed; otherwise leave null.
            from pypdf import PdfReader

            return len(PdfReader(str(path)).pages)
        except Exception:  # noqa: BLE001
            return None
    if suffix in {".txt", ".md", ".text"}:
        # Text files: no page count
        return None
    return None


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PACKAGE_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def associate_source_id(path: Path, registry: SourceRegistry) -> str | None:
    rel = _relative(path)
    name = path.name.lower()
    stem = path.stem.lower()
    for source in registry.list_sources():
        local = source.local_file_path
        if local:
            local_resolved = resolve_path(local)
            if local_resolved.exists() and local_resolved.resolve() == path.resolve():
                return source.source_id
            if _relative(local_resolved).lower() == rel.lower():
                return source.source_id
        # Weak filename association only for manifest bookkeeping — not evidence activation
        sid = source.source_id.lower().replace("src_", "")
        if sid and sid in stem:
            return source.source_id
        if source.source_id.lower() in name:
            return source.source_id
    return None


def scan_corpus(
    corpus_root: Path | str | None = None,
    *,
    registry: SourceRegistry | None = None,
) -> CorpusScanResult:
    ensure_corpus_directories()
    root = Path(corpus_root or CORPUS_ROOT)
    registry = registry or SourceRegistry.from_yaml()
    files: list[CorpusFileRecord] = []
    found_paths: set[Path] = set()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == ".gitkeep":
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if "metadata" in path.parts and path.suffix.lower() in {".yaml", ".yml", ".bib"}:
            # metadata sidecars are not corpus evidence files
            if path.suffix.lower() != ".txt":
                continue
        found_paths.add(path.resolve())
        sid = associate_source_id(path, registry)
        files.append(
            CorpusFileRecord(
                path=_relative(path),
                sha256=file_sha256(path),
                size_bytes=int(path.stat().st_size),
                page_count=estimate_page_count(path),
                associated_source_id=sid,
                registration_status="registered" if sid else "unregistered",
            )
        )

    missing = 0
    for source in registry.list_sources():
        if source.evidence_status in {"excluded", "incomplete_reference"}:
            continue
        local = source.local_file_path
        if not local:
            if source.evidence_status in {
                "pending_local_source",
                "bibliographically_verified_but_not_locally_available",
                "pending_verification",
            }:
                missing += 1
                files.append(
                    CorpusFileRecord(
                        path="",
                        sha256="",
                        size_bytes=0,
                        page_count=None,
                        associated_source_id=source.source_id,
                        registration_status="missing_for_registered_source",
                    )
                )
            continue
        path = resolve_path(local)
        if not path.exists():
            missing += 1
            files.append(
                CorpusFileRecord(
                    path=_relative(path) if path else str(local),
                    sha256="",
                    size_bytes=0,
                    page_count=None,
                    associated_source_id=source.source_id,
                    registration_status="missing_for_registered_source",
                )
            )

    n_reg = sum(1 for f in files if f.registration_status == "registered")
    n_unreg = sum(1 for f in files if f.registration_status == "unregistered")
    notes = [
        "File presence does not create evidence extracts or change evidence grades.",
        "Scientific activation requires validated extracts via literature add-extract "
        "with curator_verification_status=validated, then matrix rebuild.",
    ]
    if n_reg + n_unreg == 0:
        notes.append("No local PDF/text corpus files were found under literature/corpus/.")

    result = CorpusScanResult(
        corpus_root=_relative(root),
        n_files_found=n_reg + n_unreg,
        n_registered_with_file=n_reg,
        n_unregistered_files=n_unreg,
        n_registered_missing_file=missing,
        files=files,
        notes=notes,
    )
    _write_manifest(result)
    return result


def _write_manifest(result: CorpusScanResult) -> None:
    ensure_corpus_directories()
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scan": result.to_dict(),
        "scientific_note": (
            "This manifest records file presence and checksums only. "
            "It does not constitute verified scientific evidence."
        ),
    }
    CORPUS_MANIFEST.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def local_corpus_status_markdown(scan: CorpusScanResult) -> str:
    empty = scan.n_files_found == 0
    lines = [
        "# Local literature corpus status",
        "",
    ]
    if empty:
        lines.extend(
            [
                "No local literature corpus was available during this run.",
                "Consequently, the sixteen-cell evidence matrix represents the current",
                "verification state of this repository and not the global state of the",
                "scientific literature.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"Local corpus files found: {scan.n_files_found}.",
                "File presence alone does not activate evidence grades or parameters.",
                "",
            ]
        )
    lines.extend(
        [
            f"- corpus root: `{scan.corpus_root}`",
            f"- files found: {scan.n_files_found}",
            f"- registered with file: {scan.n_registered_with_file}",
            f"- unregistered files: {scan.n_unregistered_files}",
            f"- registered sources missing file: {scan.n_registered_missing_file}",
            "",
            "Absence of evidence in the local corpus must not be interpreted as",
            "evidence of absence in the specialised literature.",
            "",
        ]
    )
    for note in scan.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def register_source(
    *,
    source_id: str,
    file_path: Path | str,
    citation_file: Path | str | None = None,
    full_citation: str | None = None,
    title: str | None = None,
    year: int | None = None,
    authors: list[str] | None = None,
    journal_or_publisher: str | None = None,
    instruments: list[str] | None = None,
    techniques: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register a local corpus file against a source_id.

    Sets evidence_status to pending_verification until a curator verifies the
    file was read. Never creates extracts.
    """
    ensure_corpus_directories()
    path = resolve_path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")

    citation = full_citation
    if citation_file:
        citation_path = resolve_path(citation_file)
        if citation_path.exists():
            text = citation_path.read_text(encoding="utf-8", errors="replace")
            # Use first non-empty line / @article block as citation stub if needed
            if not citation:
                citation = text.strip().splitlines()[0] if text.strip() else None

    data = load_yaml(SOURCES_PATH)
    sources = list(data.get("sources") or [])
    rel = _relative(path)
    checksum = file_sha256(path)
    entry = {
        "source_id": source_id,
        "source_type": "local_corpus_file",
        "full_citation": citation or f"{source_id} (citation pending)",
        "authors": authors,
        "year": year,
        "title": title,
        "journal_or_publisher": journal_or_publisher,
        "volume": None,
        "issue": None,
        "pages": None,
        "DOI": None,
        "ISBN": None,
        "stable_url": None,
        "local_file_path": rel,
        "language": None,
        "peer_reviewed": None,
        "instruments_covered": instruments or [],
        "techniques_covered": techniques or [],
        "acoustic_variables_covered": [],
        "evidence_status": "pending_verification",
        "verification_notes": (
            f"Local file registered at {rel}; sha256={checksum}. "
            "File presence does not activate evidence. Curator must verify reading "
            "and add validated extracts before the matrix grade can change."
        ),
        "local_file_sha256": checksum,
    }

    replaced = False
    for i, existing in enumerate(sources):
        if existing.get("source_id") == source_id:
            sources[i] = {**existing, **entry}
            replaced = True
            break
    if not replaced:
        sources.append(entry)
    data["sources"] = sources

    if dry_run:
        return {
            "dry_run": True,
            "entry": entry,
            "replaced": replaced,
            "evidence_activated": False,
        }

    SOURCES_PATH.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    # Validate round-trip
    LiteratureSource.model_validate(entry)
    LOGGER.info("Registered source_id=%s file=%s (no evidence activated)", source_id, rel)
    return {"dry_run": False, "entry": entry, "replaced": replaced, "evidence_activated": False}


def add_extract(
    *,
    source_id: str,
    instrument: str,
    technique: str,
    paraphrased_claim: str,
    quantitative_or_qualitative: str,
    measured_variable: str,
    directness: str,
    curator_verification_status: str,
    page_start: int | str | None = None,
    page_end: int | str | None = None,
    table_number: str | None = None,
    figure_number: str | None = None,
    equation_number: str | None = None,
    section_title: str | None = None,
    unit: str | None = None,
    reported_value: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Append a curated evidence extract. Does not auto-validate."""
    if instrument not in ALLOWED_INSTRUMENTS:
        raise ValueError(f"Unsupported instrument: {instrument}")
    if technique not in ALLOWED_TECHNIQUES:
        raise ValueError(f"Unsupported technique: {technique}")
    if directness not in DIRECTNESS_VALUES:
        raise ValueError(f"Invalid directness: {directness}")
    status = str(curator_verification_status).lower()
    if status not in EXTRACT_VERIFICATION_STATUSES:
        raise ValueError(f"Invalid curator_verification_status: {curator_verification_status}")

    registry = SourceRegistry.from_yaml()
    if source_id not in registry.sources:
        raise KeyError(f"Unknown source_id: {source_id}. Register the source first.")

    location_ok = any(
        [
            page_start is not None,
            table_number,
            figure_number,
            equation_number,
            section_title,
        ]
    )
    if not location_ok:
        raise ValueError("Exact location required (page, table, figure, equation, or section).")

    is_quant = str(quantitative_or_qualitative).lower().startswith("quant")
    if is_quant and not unit:
        raise ValueError("Quantitative extracts require a unit.")

    now = datetime.now(timezone.utc).isoformat()
    ext = EvidenceExtract(
        source_id=source_id,
        instrument=instrument,
        technique=technique,
        paraphrased_claim=paraphrased_claim,
        quantitative_or_qualitative=quantitative_or_qualitative,
        original_variable_name=measured_variable,
        canonical_variable_name=measured_variable,
        original_unit=unit,
        canonical_unit=unit,
        reported_value=reported_value,
        directness=directness,
        page_start=page_start,
        page_end=page_end,
        table_number=table_number,
        figure_number=figure_number,
        equation_number=equation_number,
        section_title=section_title,
        curator_verification_status=status,
        extraction_method="manual_curation",
        evidence_last_evaluated_utc=now,
    )
    ext.assign_deterministic_id()

    data = load_yaml(EXTRACTS_PATH) if EXTRACTS_PATH.exists() else {"extracts": []}
    extracts = list(data.get("extracts") or [])
    # Deduplicate by evidence_id
    extracts = [e for e in extracts if e.get("evidence_id") != ext.evidence_id]
    extracts.append(ext.model_dump(by_alias=True))
    data["extracts"] = extracts
    data["version"] = data.get("version") or "0.1.0-phase3-corpus-gap"

    activates_matrix = status == "validated"
    if dry_run:
        return {
            "dry_run": True,
            "extract": ext.model_dump(by_alias=True),
            "activates_matrix_on_rebuild": activates_matrix,
        }

    EXTRACTS_PATH.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    LOGGER.info(
        "Added extract %s verification=%s activates_on_rebuild=%s",
        ext.evidence_id,
        status,
        activates_matrix,
    )
    return {
        "dry_run": False,
        "extract": ext.model_dump(by_alias=True),
        "activates_matrix_on_rebuild": activates_matrix,
        "note": (
            "Matrix grade changes only after rebuild with curator_verification_status=validated."
        ),
    }
