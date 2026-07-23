"""Load curated literature-evidence table for extrapolation."""

from __future__ import annotations

from pathlib import Path

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.models import LiteratureEvidenceEntry

DEFAULT_EVIDENCE = PACKAGE_ROOT / "configs" / "extrapolation" / "literature_evidence_v1.yaml"


def load_literature_evidence(path: Path | str | None = None) -> list[LiteratureEvidenceEntry]:
    data = load_yaml(resolve_path(path or DEFAULT_EVIDENCE))
    entries = data.get("entries") or []
    return [LiteratureEvidenceEntry.model_validate(e) for e in entries]


def select_evidence(
    entries: list[LiteratureEvidenceEntry],
    *,
    technique: str,
    quantity: str,
    instrument: str,
) -> LiteratureEvidenceEntry | None:
    """Pick the best matching evidence row: instrument-specific first, then generic."""
    exact = [
        e
        for e in entries
        if e.target_quantity == quantity
        and e.technique == technique
        and e.instrument == instrument
    ]
    if exact:
        return exact[0]
    generic = [
        e
        for e in entries
        if e.target_quantity == quantity and e.technique == technique and e.instrument is None
    ]
    if generic:
        return generic[0]
    # EWSD global prohibition entry
    global_q = [
        e
        for e in entries
        if e.target_quantity == quantity and e.technique is None
    ]
    if global_q:
        return global_q[0]
    return None
