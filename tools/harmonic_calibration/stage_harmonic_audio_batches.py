#!/usr/bin/env python3
"""Stage technique-separated, note-deduplicated harmonic audio batches for Spectral_Analyser."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CALIB = ROOT / "data" / "harmonic_calibration"
CATALOG = CALIB / "violin_harmonic_audio_catalog.csv"
BATCHES = CALIB / "batches"

BATCH_SPECS = (
    ("orchidea", "artificial_harmonic", "mf", "orchidea_artificial_harmonic_mf"),
    ("philharmonia", "artificial_harmonic", "mf", "philharmonia_artificial_harmonic_mf"),
    ("philharmonia", "natural_harmonic", "mf", "philharmonia_natural_harmonic_mf"),
    ("philharmonia", "natural_harmonic", "p", "philharmonia_natural_harmonic_p"),
    ("mcgill", "artificial_harmonic", "mf", "mcgill_artificial_harmonic_mf"),
    ("mcgill", "natural_harmonic", "mf", "mcgill_natural_harmonic_mf"),
)


def _score(path: Path) -> tuple[int, int]:
    name = path.name
    prefer_n = 0 if ("-N." in name or name.endswith("-N.wav")) else 1
    return (prefer_n, len(name))


def stage_batch(
    catalog: pd.DataFrame,
    collection: str,
    technique: str,
    dynamic: str,
    batch_name: str,
) -> Path:
    sub = catalog[
        (catalog["collection"] == collection)
        & (catalog["technique"] == technique)
        & (catalog["dynamic"] == dynamic)
    ].copy()
    out = BATCHES / batch_name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    n = 0
    for note, group in sub.groupby("note"):
        paths = sorted((Path(p) for p in group["path"]), key=_score)
        src = paths[0]
        dest = out / f"{note}__{collection}__{technique}__{dynamic}{src.suffix.lower()}"
        try:
            dest.hardlink_to(src)
        except OSError:
            shutil.copy2(src, dest)
        n += 1
    print(f"{batch_name}: staged {n} unique notes -> {out}")
    return out


def main() -> int:
    if not CATALOG.exists():
        raise SystemExit(f"Missing catalog: {CATALOG}")
    catalog = pd.read_csv(CATALOG)
    BATCHES.mkdir(parents=True, exist_ok=True)
    for collection, technique, dynamic, batch_name in BATCH_SPECS:
        stage_batch(catalog, collection, technique, dynamic, batch_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
