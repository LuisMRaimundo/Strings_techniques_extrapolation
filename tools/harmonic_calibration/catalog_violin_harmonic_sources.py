#!/usr/bin/env python3
"""Catalog Philharmonia / McGill / Orchidea violin harmonic + ordinario audio."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

AUDIO_ROOT = Path(
    r"F:\DOUTORAMENTO_22\INSTRUMENTOS\Instrumentos_espectro_versão 3\CORDAS\VIOLINO"
)
OUT = Path(__file__).resolve().parents[2] / "data" / "harmonic_calibration"

DYN_MAP = {
    "pianissimo": "pp",
    "piano": "p",
    "mezzo-piano": "mp",
    "mezzo-forte": "mf",
    "forte": "f",
    "fortissimo": "ff",
}


def _add(rows: list[dict], **kwargs) -> None:
    rows.append(kwargs)


def catalog_philharmonia(rows: list[dict]) -> None:
    phil_root = AUDIO_ROOT / "Phillarmonia" / "violin"
    harm = next(p for p in phil_root.iterdir() if "Harm" in p.name)
    for f in harm.rglob("*"):
        if f.suffix.lower() not in {".mp3", ".wav"}:
            continue
        if any(part.startswith("_") for part in f.parts):
            continue
        m = re.search(
            r"violin_([A-G]#?\d)_\d+_([a-z\-]+)_(natural|artificial)-harmonic",
            f.name,
            re.I,
        )
        if not m:
            continue
        dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
        _add(
            rows,
            collection="philharmonia",
            technique=f"{m.group(3).lower()}_harmonic",
            dynamic=dyn,
            note=m.group(1),
            path=str(f),
            ext=f.suffix.lower(),
            source_kind="harmonic",
        )

    for sub in phil_root.iterdir():
        if not sub.is_dir() or "arco-normal" not in sub.name.lower():
            continue
        for f in sub.rglob("*"):
            if f.suffix.lower() not in {".mp3", ".wav"}:
                continue
            if any(part.startswith("_") for part in f.relative_to(sub).parts):
                continue
            m = re.search(
                r"violin_([A-G]#?\d)_\d+_([a-z\-]+)_arco-normal",
                f.name,
                re.I,
            )
            if not m:
                continue
            dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
            _add(
                rows,
                collection="philharmonia",
                technique="ordinario",
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
            )


def catalog_mcgill(rows: list[dict]) -> None:
    mg = AUDIO_ROOT / "Vln_McGill"
    specs = (
        ("natural_harmonic", "VIOLIN HARMONICS_NATURAL", "mf", "harmonic"),
        ("artificial_harmonic", "VIOLIN HARMONICS_ARTIFICIAL", "mf", "harmonic"),
        ("ordinario", "VIOLIN 1 NON VIBRATO", "unknown", "ordinario"),
    )
    for tech, folder, dyn, kind in specs:
        d = mg / folder
        if not d.exists():
            continue
        for f in d.glob("*.wav"):
            m = re.search(r"Vln([A-G]#?\d)", f.name)
            if not m:
                continue
            _add(
                rows,
                collection="mcgill",
                technique=tech,
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind=kind,
            )


def catalog_orchidea(rows: list[dict]) -> None:
    orch = AUDIO_ROOT / "Vln_Orchidea"
    for f in (orch / "artificial_harmonic").glob("*.wav"):
        m = re.search(r"Vn-art_harm-([A-G]#?\d)-(pp|p|mp|mf|f|ff)-", f.name, re.I)
        if not m:
            continue
        _add(
            rows,
            collection="orchidea",
            technique="artificial_harmonic",
            dynamic=m.group(2).lower(),
            note=m.group(1),
            path=str(f),
            ext=f.suffix.lower(),
            source_kind="harmonic",
        )
    for f in (orch / "ordinario").rglob("*.wav"):
        m = re.search(r"Vn-ord-([A-G]#?\d)-(pp|p|mp|mf|f|ff)-", f.name, re.I)
        if not m:
            continue
        _add(
            rows,
            collection="orchidea",
            technique="ordinario",
            dynamic=m.group(2).lower(),
            note=m.group(1),
            path=str(f),
            ext=f.suffix.lower(),
            source_kind="ordinario",
        )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    catalog_philharmonia(rows)
    catalog_mcgill(rows)
    catalog_orchidea(rows)
    df = pd.DataFrame(rows)
    csv_path = OUT / "violin_harmonic_audio_catalog.csv"
    df.to_csv(csv_path, index=False)
    summary = (
        df.groupby(["collection", "technique", "dynamic"])
        .agg(n_files=("path", "count"), n_notes=("note", "nunique"))
        .reset_index()
    )
    summary.to_csv(OUT / "violin_harmonic_audio_catalog_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"TOTAL rows {len(df)} -> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
