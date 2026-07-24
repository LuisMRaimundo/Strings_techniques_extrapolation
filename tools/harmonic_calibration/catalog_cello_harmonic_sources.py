#!/usr/bin/env python3
"""Catalog Philharmonia / McGill / Orchidea cello harmonic + ordinario audio."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[2] / "data" / "harmonic_calibration"

BASE = Path(
    r"F:\DOUTORAMENTO_22\INSTRUMENTOS\Instrumentos_espectro_versão 3\CORDAS\VIOLONCELO"
)
MCGILL_ART = BASE / "McGill" / "CELLO ARTIFICIAL HARMONICS"
MCGILL_ORD = BASE / "McGill" / "CELLO"
ORCH_ORD = BASE / "Orchidea_Vlc" / "Violoncello" / "ordinario"
ORCH_ART = BASE / "Orchidea_Vlc" / "Violoncello" / "artificial_harmonic"
PHIL_ROOT = BASE / "Phillarmonia" / "cello"

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


def _skip_deriv(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(
        part.startswith("_") or part.lower() in {"attacks", "decays", "sustains"}
        for part in rel.parts
    )


def catalog_philharmonia(rows: list[dict]) -> None:
    harm = PHIL_ROOT / "violoncelo_harmonic"
    if harm.is_dir():
        for f in harm.rglob("*"):
            if f.suffix.lower() not in {".mp3", ".wav"}:
                continue
            if _skip_deriv(f, harm):
                continue
            # Philharmonia cello uses undifferentiated ``arco-harmonic`` (mf only).
            m = re.search(
                r"cello_([A-G]#?\d)_[^_]+_([a-z\-]+)_arco-harmonic",
                f.name,
                re.I,
            )
            if not m:
                continue
            dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
            _add(
                rows,
                collection="philharmonia",
                instrument="vlc",
                technique="natural_harmonic",
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
                label_raw="arco-harmonic",
            )

    for sub in PHIL_ROOT.iterdir():
        if not sub.is_dir() or "arco-normal" not in sub.name.lower():
            continue
        for f in sub.rglob("*"):
            if f.suffix.lower() not in {".mp3", ".wav"}:
                continue
            if _skip_deriv(f, sub):
                continue
            m = re.search(
                r"cello_([A-G]#?\d)_[^_]+_([a-z\-]+)_arco-normal",
                f.name,
                re.I,
            )
            if not m:
                continue
            dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
            _add(
                rows,
                collection="philharmonia",
                instrument="vlc",
                technique="ordinario",
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
                label_raw="arco-normal",
            )


def catalog_mcgill(rows: list[dict]) -> None:
    if MCGILL_ART.is_dir():
        for f in MCGILL_ART.glob("*.wav"):
            m = re.search(r"Cel\.?([A-G]#?\d)", f.name, re.I)
            if not m:
                continue
            _add(
                rows,
                collection="mcgill",
                instrument="vlc",
                technique="artificial_harmonic",
                dynamic="mf",
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
                label_raw="artificial_harmonics",
            )
    if MCGILL_ORD.is_dir():
        for f in MCGILL_ORD.glob("*.wav"):
            m = re.search(r"Cel\.?([A-G]#?\d)", f.name, re.I)
            if not m:
                continue
            _add(
                rows,
                collection="mcgill",
                instrument="vlc",
                technique="ordinario",
                dynamic="unknown",
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
                label_raw="cello",
            )


def catalog_orchidea(rows: list[dict]) -> None:
    if ORCH_ART.is_dir():
        for f in ORCH_ART.glob("*.wav"):
            m = re.search(
                r"Vc-art_harm-([A-G]#?\d)-([a-z]+)-",
                f.name,
                re.I,
            )
            if not m:
                continue
            _add(
                rows,
                collection="orchidea",
                instrument="vlc",
                technique="artificial_harmonic",
                dynamic=m.group(2).lower(),
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
                label_raw="artificial_harmonic",
            )
    if ORCH_ORD.is_dir():
        for f in ORCH_ORD.rglob("*.wav"):
            m = re.search(
                r"Vc-ord-([A-G]#?\d)-(pp|p|mp|mf|f|ff)-",
                f.name,
                re.I,
            )
            if not m:
                continue
            _add(
                rows,
                collection="orchidea",
                instrument="vlc",
                technique="ordinario",
                dynamic=m.group(2).lower(),
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
                label_raw="ordinario",
            )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    catalog_philharmonia(rows)
    catalog_mcgill(rows)
    catalog_orchidea(rows)
    df = pd.DataFrame(rows)
    csv_path = OUT / "cello_harmonic_audio_catalog.csv"
    df.to_csv(csv_path, index=False)
    summary = (
        df.groupby(["collection", "technique", "dynamic"])
        .agg(n_files=("path", "count"), n_notes=("note", "nunique"))
        .reset_index()
        .sort_values(["collection", "technique", "dynamic"])
    )
    summary.to_csv(OUT / "cello_harmonic_audio_catalog_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"TOTAL rows {len(df)} -> {csv_path}")
    harm = df[df["source_kind"] == "harmonic"]
    print("\nHarmonic unique notes by collection×technique×dynamic:")
    print(
        harm.groupby(["collection", "technique", "dynamic"])["note"]
        .nunique()
        .reset_index(name="n_notes")
        .to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
