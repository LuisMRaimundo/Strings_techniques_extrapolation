"""Load measured ordinary/ordinario baselines (research Excel preferred, CDM JSON fallback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, resolve_path

_INSTRUMENT_CDM = {
    "vln": "violin_ordinary_cdm.json",
    "vla": "viola_ordinary_cdm.json",
    "vlc": "cello_ordinary_cdm.json",
    "cb": "double_bass_ordinary_cdm.json",
}

_INSTRUMENT_ALIASES = {
    "violin": "vln",
    "viola": "vla",
    "cello": "vlc",
    "violoncello": "vlc",
    "double_bass": "cb",
    "contrabass": "cb",
    "bass": "cb",
}


def normalize_instrument(label: str) -> str:
    key = str(label).strip().lower()
    return _INSTRUMENT_ALIASES.get(key, key)


class OrdinaryBaselineStore:
    """In-memory ordinary EWSD baselines keyed by instrument × note × dynamic.

    Measured Spectral_Analyser research Excel rows take precedence over bundled CDM JSON.
    """

    def __init__(self) -> None:
        self.by_instrument: dict[str, dict[str, Any]] = {}
        self.research_rows: list[dict[str, Any]] = []
        self.metric_name: str = "EWSD_score_acoustic_balanced"
        self.baseline_source: str = "none"
        self.load_warnings: list[str] = []

    def load_cdm_directory(self, directory: Path | str | None = None) -> None:
        root = resolve_path(directory or (PACKAGE_ROOT / "data" / "baselines"))
        for inst, filename in _INSTRUMENT_CDM.items():
            path = root / filename
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            self.by_instrument[inst] = data
            if data.get("metric"):
                self.metric_name = str(data["metric"])
        if self.by_instrument and self.baseline_source == "none":
            self.baseline_source = "ordinary_cdm_json"

    def ingest_research_rows(self, rows: list[dict[str, Any]]) -> None:
        """Merge measured research rows; prefer these for EWSD means."""
        if not rows:
            return
        self.research_rows.extend(rows)
        # Build spectral_data overlay per instrument
        for row in rows:
            inst = normalize_instrument(row["instrument"])
            note = row.get("note") or "unknown"
            dyn = str(row["dynamic"]).lower()
            bucket = self.by_instrument.setdefault(
                inst,
                {"metric": self.metric_name, "spectral_data": {}, "source": "research_excel"},
            )
            spectral = bucket.setdefault("spectral_data", {})
            note_map = spectral.setdefault(str(note), {})
            note_map[dyn] = float(row["ewsd"])
            note_map.setdefault("_components", {})[dyn] = row.get("components") or {}
            note_map.setdefault("_provenance", {})[dyn] = {
                "source_path": row.get("source_path"),
                "sheet": row.get("sheet"),
                "ewsd_column": row.get("ewsd_column") or self.metric_name,
                "ci_low": row.get("ci_low"),
                "ci_high": row.get("ci_high"),
            }
        self.baseline_source = "spectral_analyser_research_excel"
        self.metric_name = "EWSD_score_acoustic_balanced"

    def load_research_excel(self, path: Path | str) -> list[str]:
        """Load one Spectral_Analyser research workbook as measured baseline."""
        from string_technique_model.extrapolation.research_excel import parse_research_workbook

        rows, warnings = parse_research_workbook(path)
        self.ingest_research_rows(rows)
        self.load_warnings.extend(warnings)
        return warnings

    def load_orchidea_manifest(
        self,
        manifest_path: Path | str | None = None,
        *,
        orchidea_root: Path | str | None = None,
    ) -> list[str]:
        from string_technique_model.extrapolation.research_excel import load_orchidea_manifest

        rows, warnings, meta = load_orchidea_manifest(
            manifest_path, orchidea_root=orchidea_root
        )
        self.ingest_research_rows(rows)
        self.load_warnings.extend(warnings)
        self.load_warnings.append(
            f"orchidea manifest loaded_rows={meta.get('n_rows')} "
            f"files={len(meta.get('loaded_paths') or [])} "
            f"missing={len(meta.get('missing_paths') or [])}"
        )
        return warnings

    def dynamic_mean_ewsd(self, instrument: str, dynamic: str) -> tuple[float | None, list[str]]:
        """Mean ordinary EWSD across notes for instrument×dynamic; return record ids."""
        inst = normalize_instrument(instrument)
        # Prefer research rows when present for this instrument×dynamic
        research = [
            r
            for r in self.research_rows
            if normalize_instrument(r["instrument"]) == inst and str(r["dynamic"]).lower() == dynamic
        ]
        if research:
            values = [float(r["ewsd"]) for r in research]
            ids = [
                f"{inst}|ordinary|{r.get('note')}|{dynamic}|EWSD|research_excel"
                for r in research
            ]
            return sum(values) / len(values), ids

        data = self.by_instrument.get(inst)
        if not data:
            return None, []
        spectral = data.get("spectral_data") or {}
        values: list[float] = []
        ids: list[str] = []
        for note, dyn_map in spectral.items():
            if not isinstance(dyn_map, dict):
                continue
            if dynamic not in dyn_map:
                continue
            try:
                val = float(dyn_map[dynamic])
            except (TypeError, ValueError):
                continue
            values.append(val)
            ids.append(f"{inst}|ordinary|{note}|{dynamic}|EWSD")
        if not values:
            return None, []
        return sum(values) / len(values), ids

    def dynamic_mean_component(
        self, instrument: str, dynamic: str, quantity: str
    ) -> tuple[float | None, list[str]]:
        """Mean of a measured component column across research notes, if available."""
        inst = normalize_instrument(instrument)
        vals: list[float] = []
        ids: list[str] = []
        for r in self.research_rows:
            if normalize_instrument(r["instrument"]) != inst:
                continue
            if str(r["dynamic"]).lower() != dynamic:
                continue
            comps = r.get("components") or {}
            if quantity not in comps or comps[quantity] is None:
                continue
            vals.append(float(comps[quantity]))
            ids.append(f"{inst}|ordinary|{r.get('note')}|{dynamic}|{quantity}|research_excel")
        if not vals:
            return None, []
        return sum(vals) / len(vals), ids

    def has_instrument(self, instrument: str) -> bool:
        inst = normalize_instrument(instrument)
        if any(normalize_instrument(r["instrument"]) == inst for r in self.research_rows):
            return True
        return inst in self.by_instrument
