"""Archive PDF identity validation — filename claims are never authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.provenance_classes import VALIDATION_STATUSES

DEFAULT_IDENTITY_PATH = PACKAGE_ROOT / "configs" / "source_identity_validation.yaml"


class SourceIdentityEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    entry_id: str
    file_path_archive: str
    deposited_path: str | None = None
    file_hash_sha256: str | None = None
    page_count: int | None = None
    expected_citation: str | None = None
    internal_title: str | None = None
    internal_authors: list[str] | None = None
    internal_year: int | None = None
    internal_doi: str | None = None
    internal_isbn: str | None = None
    internal_publisher: str | None = None
    identity_match: bool
    validation_status: str
    rejection_reason: str | None = None
    duplicate_of: str | None = None
    associated_source_id: str | None = None
    ingest_decision: str | None = None
    notes: str | None = None

    def is_ingestible(self) -> bool:
        return self.validation_status in {"verified_identity", "partial_identity_match"} and bool(
            self.associated_source_id
        )


class SourceIdentityRegistry:
    def __init__(self, entries: list[SourceIdentityEntry], *, meta: dict[str, Any] | None = None) -> None:
        self.entries = {e.entry_id: e for e in entries}
        self.meta = meta or {}
        if len(self.entries) != len(entries):
            raise ValueError("Duplicate entry_id in source_identity_validation.yaml")
        for entry in entries:
            if entry.validation_status not in VALIDATION_STATUSES:
                raise ValueError(f"Invalid validation_status for {entry.entry_id}: {entry.validation_status}")

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> SourceIdentityRegistry:
        path = resolve_path(path or DEFAULT_IDENTITY_PATH)
        data = load_yaml(path)
        raw = data.get("entries") or []
        entries = [SourceIdentityEntry.model_validate(item) for item in raw]
        meta = {"version": data.get("version"), "archive_root_note": data.get("archive_root_note")}
        return cls(entries, meta=meta)

    def list_entries(self) -> list[SourceIdentityEntry]:
        return [self.entries[k] for k in sorted(self.entries)]

    def by_status(self, status: str) -> list[SourceIdentityEntry]:
        return [e for e in self.list_entries() if e.validation_status == status]

    def verified(self) -> list[SourceIdentityEntry]:
        return self.by_status("verified_identity")

    def rejected(self) -> list[SourceIdentityEntry]:
        return [
            e
            for e in self.list_entries()
            if e.validation_status
            in {"rejected_file_identity_mismatch", "insufficient_metadata", "duplicate_file"}
        ]

    def find_by_hash(self, sha256: str) -> list[SourceIdentityEntry]:
        return [e for e in self.list_entries() if e.file_hash_sha256 == sha256]

    def detect_hash_duplicates(self) -> list[tuple[str, list[str]]]:
        buckets: dict[str, list[str]] = {}
        for entry in self.list_entries():
            if not entry.file_hash_sha256:
                continue
            buckets.setdefault(entry.file_hash_sha256, []).append(entry.entry_id)
        return [(h, ids) for h, ids in buckets.items() if len(ids) > 1]

    def reject_filename_only_claim(self, filename_claim: str, *, require_internal_title: bool = True) -> bool:
        """Return True if a filename claim alone is insufficient for ingestion."""
        matches = [e for e in self.list_entries() if e.file_path_archive == filename_claim]
        if not matches:
            return True
        entry = matches[0]
        if not entry.identity_match:
            return True
        if require_internal_title and not entry.internal_title:
            return True
        if entry.validation_status != "verified_identity":
            return True
        return False

    def doi_present_and_nonempty(self, entry_id: str) -> bool:
        entry = self.entries[entry_id]
        return bool(entry.internal_doi and str(entry.internal_doi).strip())

    def to_markdown_report(self) -> str:
        lines = [
            "# Source identity validation",
            "",
            "Internal title/author/year/DOI/ISBN and page count take precedence over filenames.",
            "File presence does not activate EWSD parameters.",
            "",
            f"**Registry version:** {self.meta.get('version')}",
            "",
            "## Summary",
            "",
            f"- Verified identity: {len(self.verified())}",
            f"- Partial identity match: {len(self.by_status('partial_identity_match'))}",
            f"- Duplicate file: {len(self.by_status('duplicate_file'))}",
            f"- Rejected (identity mismatch): {len(self.by_status('rejected_file_identity_mismatch'))}",
            f"- Insufficient metadata: {len(self.by_status('insufficient_metadata'))}",
            f"- Hash-duplicate groups: {len(self.detect_hash_duplicates())}",
            "",
            "## Entries",
            "",
        ]
        for entry in self.list_entries():
            lines.extend(
                [
                    f"### {entry.entry_id}",
                    "",
                    f"- Archive filename claim: `{entry.file_path_archive}`",
                    f"- Deposited path: `{entry.deposited_path}`",
                    f"- SHA-256: `{entry.file_hash_sha256}`",
                    f"- Pages: {entry.page_count}",
                    f"- Internal title: {entry.internal_title}",
                    f"- Internal authors: {entry.internal_authors}",
                    f"- Internal year: {entry.internal_year}",
                    f"- Internal DOI: {entry.internal_doi}",
                    f"- Internal ISBN: {entry.internal_isbn}",
                    f"- Publisher: {entry.internal_publisher}",
                    f"- Expected citation (claim): {entry.expected_citation}",
                    f"- Identity match: {entry.identity_match}",
                    f"- Validation status: `{entry.validation_status}`",
                    f"- Rejection reason: {entry.rejection_reason}",
                    f"- Duplicate of: {entry.duplicate_of}",
                    f"- Associated source ID: `{entry.associated_source_id}`",
                    f"- Ingest decision: {entry.ingest_decision}",
                    "",
                ]
            )
            if entry.notes:
                lines.extend([f"_Notes:_ {entry.notes}", ""])
        return "\n".join(lines)


def load_source_identity_registry(path: Path | str | None = None) -> SourceIdentityRegistry:
    return SourceIdentityRegistry.from_yaml(path)


def write_source_identity_report(
    output: Path | str | None = None,
    *,
    registry: SourceIdentityRegistry | None = None,
) -> Path:
    registry = registry or load_source_identity_registry()
    out = resolve_path(output or PACKAGE_ROOT / "reports" / "source_identity_validation.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(registry.to_markdown_report(), encoding="utf-8")
    return out
