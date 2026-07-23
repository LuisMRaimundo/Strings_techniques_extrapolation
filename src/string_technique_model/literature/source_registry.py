"""Literature source registry loading and citation completeness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.domain import EVIDENCE_STATUSES


class LiteratureSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str
    source_type: str
    full_citation: str
    authors: list[str] | None = None
    year: int | None = None
    title: str | None = None
    journal_or_publisher: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    DOI: str | None = None
    ISBN: str | None = None
    stable_url: str | None = None
    local_file_path: str | None = None
    language: str | None = None
    peer_reviewed: bool | None = None
    instruments_covered: list[str] = Field(default_factory=list)
    techniques_covered: list[str] = Field(default_factory=list)
    acoustic_variables_covered: list[str] = Field(default_factory=list)
    evidence_status: str
    verification_notes: str | None = None

    def citation_complete(self) -> bool:
        # Secondary synthesis with explicitly unresolved author/year: local file + pages suffice.
        author_year_status = getattr(self, "author_year_status", None)
        evidence_class = getattr(self, "evidence_class", None)
        if (
            author_year_status == "unresolved"
            and evidence_class == "secondary_synthesis"
            and self.full_citation
            and self.title
            and self.pages
            and self.local_file_path
        ):
            return True

        required = [self.full_citation, self.title, self.year, self.journal_or_publisher]
        if any(v is None or str(v).strip() == "" for v in required):
            return False
        if not self.authors:
            return False
        # Need at least one stable identifier or pages+volume
        has_id = bool(self.DOI or self.ISBN or self.stable_url)
        has_locus = bool(self.volume and self.pages)
        return has_id or has_locus

    def may_support_parameters(self) -> bool:
        if self.evidence_status != "verified_local_source":
            return False
        if not self.local_file_path:
            return False
        path = resolve_path(self.local_file_path)
        return path.exists()


class SourceRegistry:
    def __init__(self, sources: list[LiteratureSource], *, meta: dict[str, Any] | None = None) -> None:
        self.sources = {s.source_id: s for s in sources}
        self.meta = meta or {}
        if len(self.sources) != len(sources):
            raise ValueError("Duplicate source_id in literature_sources.yaml")

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> SourceRegistry:
        path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_sources.yaml")
        data = load_yaml(path)
        raw = data.get("sources") or []
        sources = [LiteratureSource.model_validate(item) for item in raw]
        for s in sources:
            if s.evidence_status not in EVIDENCE_STATUSES:
                raise ValueError(f"Invalid evidence_status for {s.source_id}: {s.evidence_status}")
        meta = {
            "pending_local_corpus_curation": data.get("pending_local_corpus_curation"),
            "corpus_search_completed": data.get("corpus_search_completed"),
            "corpus_search_notes": data.get("corpus_search_notes"),
            "version": data.get("version"),
        }
        return cls(sources, meta=meta)

    def get(self, source_id: str) -> LiteratureSource:
        if source_id not in self.sources:
            raise KeyError(f"Unknown source_id: {source_id}")
        return self.sources[source_id]

    def list_sources(self) -> list[LiteratureSource]:
        return [self.sources[k] for k in sorted(self.sources)]

    def verified(self) -> list[LiteratureSource]:
        return [s for s in self.list_sources() if s.evidence_status == "verified_local_source"]

    def incomplete(self) -> list[LiteratureSource]:
        return [
            s
            for s in self.list_sources()
            if s.evidence_status == "incomplete_reference" or not s.citation_complete()
        ]

    def excluded(self) -> list[LiteratureSource]:
        return [s for s in self.list_sources() if s.evidence_status == "excluded"]
