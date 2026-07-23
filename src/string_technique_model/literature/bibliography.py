"""Bibliographic exports (verified vs incomplete)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.literature.source_registry import LiteratureSource, SourceRegistry


def _bibtex_key(source: LiteratureSource) -> str:
    author = "Unknown"
    if source.authors:
        author = str(source.authors[0]).split(",")[0].replace(" ", "")
    year = source.year or "n.d."
    return f"{author}{year}_{source.source_id}"


def to_bibtex_entry(source: LiteratureSource) -> str:
    key = _bibtex_key(source)
    fields = {
        "author": " and ".join(source.authors or []),
        "title": source.title or "",
        "year": str(source.year) if source.year is not None else "",
        "journal": source.journal_or_publisher or "",
        "volume": source.volume or "",
        "number": source.issue or "",
        "pages": source.pages or "",
        "doi": source.DOI or "",
        "isbn": source.ISBN or "",
        "url": source.stable_url or "",
        "note": (source.verification_notes or "").replace("\n", " ").strip(),
    }
    lines = [f"@article{{{key},"]
    for k, v in fields.items():
        if v:
            safe = v.replace("{", "").replace("}", "")
            lines.append(f"  {k} = {{{safe}}},")
    lines.append("}")
    return "\n".join(lines)


def export_verified_bibtex(registry: SourceRegistry, path: Path) -> int:
    """Export only verified_local_source entries (may be zero)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    verified = registry.verified()
    blocks = [to_bibtex_entry(s) for s in verified]
    header = (
        "% Verified local specialised-literature sources only.\n"
        "% Incomplete / unread / excluded sources are intentionally omitted.\n\n"
    )
    path.write_text(header + ("\n\n".join(blocks) + ("\n" if blocks else "")), encoding="utf-8")
    return len(verified)


def verified_source_rows(registry: SourceRegistry) -> list[dict[str, Any]]:
    rows = []
    for s in registry.verified():
        rows.append(
            {
                "source_id": s.source_id,
                "full_citation": s.full_citation,
                "DOI": s.DOI,
                "ISBN": s.ISBN,
                "year": s.year,
                "title": s.title,
                "evidence_status": s.evidence_status,
                "local_file_path": s.local_file_path,
            }
        )
    return rows


def incomplete_source_rows(registry: SourceRegistry) -> list[dict[str, Any]]:
    rows = []
    for s in registry.list_sources():
        incomplete = s.evidence_status == "incomplete_reference" or not s.citation_complete()
        if not incomplete:
            continue
        rows.append(
            {
                "source_id": s.source_id,
                "full_citation": s.full_citation,
                "evidence_status": s.evidence_status,
                "missing_title": s.title is None or str(s.title).strip() == "",
                "missing_year": s.year is None,
                "missing_authors": not bool(s.authors),
                "missing_journal_or_publisher": not bool(s.journal_or_publisher),
                "missing_volume": not bool(s.volume),
                "missing_issue": not bool(s.issue),
                "missing_pages": not bool(s.pages),
                "missing_DOI": not bool(s.DOI),
                "missing_ISBN": not bool(s.ISBN),
                "missing_stable_url": not bool(s.stable_url),
                "notes": s.verification_notes,
            }
        )
    return rows
