#!/usr/bin/env python3
"""Catalog Philharmonia / McGill / Orchidea viola harmonic + ordinario audio."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[2] / "data" / "harmonic_calibration"

ORCH_ORD = Path(r"D:\CORDAS\Orchidea\ORCH_VLA\ordinario")
ORCH_ART = Path(r"D:\CORDAS\Orchidea\ORCH_VLA\artificial_harmonic")
MCGILL_NONVIB = Path(r"D:\CORDAS\McGill\VIOLAS\VIOLA NON-VIBRATO")
MCGILL_ART = Path(r"D:\CORDAS\McGill\VIOLAS\VIOLA ARTIFICIAL HARMONICS")
PHIL_ROOT = Path(
    r"F:\DOUTORAMENTO_22\INSTRUMENTOS\Instrumentos_espectro_versão 3\CORDAS\VIOLA"
    r"\Phillarmonia\viola"
)

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
    return any(part.startswith("_") or part.lower() in {"attacks", "decays", "sustains"} for part in rel.parts)


def catalog_philharmonia(rows: list[dict]) -> None:
    harm = PHIL_ROOT / "viola_harmonics"
    if harm.is_dir():
        for f in harm.rglob("*"):
            if f.suffix.lower() not in {".mp3", ".wav"}:
                continue
            if _skip_deriv(f, harm):
                continue
            m = re.search(
                r"viola_([A-G]#?\d)_[^_]+_([a-z\-]+)_(natural|artificial)-harmonic",
                f.name,
                re.I,
            )
            if not m:
                continue
            dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
            _add(
                rows,
                collection="philharmonia",
                instrument="vla",
                technique=f"{m.group(3).lower()}_harmonic",
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
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
                r"viola_([A-G]#?\d)_[^_]+_([a-z\-]+)_arco-normal",
                f.name,
                re.I,
            )
            if not m:
                continue
            dyn = DYN_MAP.get(m.group(2).lower(), m.group(2).lower())
            _add(
                rows,
                collection="philharmonia",
                instrument="vla",
                technique="ordinario",
                dynamic=dyn,
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
            )


def catalog_mcgill(rows: list[dict]) -> None:
    if MCGILL_ART.is_dir():
        for f in MCGILL_ART.glob("*.wav"):
            m = re.search(r"Vla\.?([A-G]#?\d)", f.name, re.I)
            if not m:
                continue
            _add(
                rows,
                collection="mcgill",
                instrument="vla",
                technique="artificial_harmonic",
                dynamic="mf",
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
            )
    if MCGILL_NONVIB.is_dir():
        for f in MCGILL_NONVIB.glob("*.wav"):
            m = re.search(r"Vla\.?([A-G]#?\d)", f.name, re.I)
            if not m:
                continue
            _add(
                rows,
                collection="mcgill",
                instrument="vla",
                technique="ordinario",
                dynamic="unknown",
                note=m.group(1),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="ordinario",
            )


def catalog_orchidea(rows: list[dict]) -> None:
    if ORCH_ART.is_dir():
        for f in ORCH_ART.glob("*.wav"):
            m = re.search(
                r"Vla-art_harm-([a-z]+)-([A-G]#?\d)",
                f.name,
                re.I,
            )
            if not m:
                continue
            _add(
                rows,
                collection="orchidea",
                instrument="vla",
                technique="artificial_harmonic",
                dynamic=m.group(1).lower(),
                note=m.group(2),
                path=str(f),
                ext=f.suffix.lower(),
                source_kind="harmonic",
            )
    if ORCH_ORD.is_dir():
        for f in ORCH_ORD.rglob("*.wav"):
            m = re.search(
                r"Vla_Arco-([A-G]#?\d)-(pp|p|mp|mf|f|ff)-",
                f.name,
                re.I,
            )
            if not m:
                continue
            _add(
                rows,
                collection="orchidea",
                instrument="vla",
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
    csv_path = OUT / "viola_harmonic_audio_catalog.csv"
    df.to_csv(csv_path, index=False)
    summary = (
        df.groupby(["collection", "technique", "dynamic"])
        .agg(n_files=("path", "count"), n_notes=("note", "nunique"))
        .reset_index()
        .sort_values(["collection", "technique", "dynamic"])
    )
    summary.to_csv(OUT / "viola_harmonic_audio_catalog_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"TOTAL rows {len(df)} -> {csv_path}")
    # Harmonic-only unique notes for calibration planning
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
