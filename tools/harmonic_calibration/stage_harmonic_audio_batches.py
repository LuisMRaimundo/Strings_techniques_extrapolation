#!/usr/bin/env python3
"""Stage technique-separated, note-deduplicated harmonic audio batches for Spectral_Analyser."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CALIB = ROOT / "data" / "harmonic_calibration"
BATCHES = CALIB / "batches"
FFMPEG = Path(r"C:\ffmpeg\bin\ffmpeg.exe")

# (catalog_csv, collection, technique, dynamic, batch_name, convert_mp3_to_wav)
BATCH_SPECS = (
    # Violin
    ("violin_harmonic_audio_catalog.csv", "orchidea", "artificial_harmonic", "mf", "orchidea_artificial_harmonic_mf", False),
    ("violin_harmonic_audio_catalog.csv", "philharmonia", "artificial_harmonic", "mf", "philharmonia_artificial_harmonic_mf", False),
    ("violin_harmonic_audio_catalog.csv", "philharmonia", "natural_harmonic", "mf", "philharmonia_natural_harmonic_mf", False),
    ("violin_harmonic_audio_catalog.csv", "philharmonia", "natural_harmonic", "p", "philharmonia_natural_harmonic_p", False),
    ("violin_harmonic_audio_catalog.csv", "mcgill", "artificial_harmonic", "mf", "mcgill_artificial_harmonic_mf", False),
    ("violin_harmonic_audio_catalog.csv", "mcgill", "natural_harmonic", "mf", "mcgill_natural_harmonic_mf", False),
    # Viola
    ("viola_harmonic_audio_catalog.csv", "orchidea", "artificial_harmonic", "mf", "viola_orchidea_artificial_harmonic_mf", False),
    ("viola_harmonic_audio_catalog.csv", "philharmonia", "artificial_harmonic", "mf", "viola_philharmonia_artificial_harmonic_mf", True),
    ("viola_harmonic_audio_catalog.csv", "philharmonia", "natural_harmonic", "mf", "viola_philharmonia_natural_harmonic_mf", True),
    ("viola_harmonic_audio_catalog.csv", "mcgill", "artificial_harmonic", "mf", "viola_mcgill_artificial_harmonic_mf", False),
)


def _score(path: Path) -> tuple[int, int]:
    name = path.name
    prefer_n = 0 if ("-N." in name or name.endswith("-N.wav")) else 1
    return (prefer_n, len(name))


def _to_wav(src: Path, dest_wav: Path) -> None:
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".wav":
        try:
            dest_wav.hardlink_to(src)
        except OSError:
            shutil.copy2(src, dest_wav)
        return
    cmd = [
        str(FFMPEG),
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(dest_wav),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stage_batch(
    catalog: pd.DataFrame,
    collection: str,
    technique: str,
    dynamic: str,
    batch_name: str,
    *,
    convert_mp3_to_wav: bool,
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
        if convert_mp3_to_wav or src.suffix.lower() == ".mp3":
            dest = out / f"{note}__{collection}__{technique}__{dynamic}.wav"
            _to_wav(src, dest)
        else:
            dest = out / f"{note}__{collection}__{technique}__{dynamic}{src.suffix.lower()}"
            try:
                dest.hardlink_to(src)
            except OSError:
                shutil.copy2(src, dest)
        n += 1
    print(f"{batch_name}: staged {n} unique notes -> {out}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        nargs="*",
        help="Optional batch_name filter(s), e.g. viola_orchidea_artificial_harmonic_mf",
    )
    args = p.parse_args()
    only = set(args.only or [])

    BATCHES.mkdir(parents=True, exist_ok=True)
    for catalog_name, collection, technique, dynamic, batch_name, convert in BATCH_SPECS:
        if only and batch_name not in only:
            continue
        catalog_path = CALIB / catalog_name
        if not catalog_path.exists():
            print(f"SKIP missing catalog: {catalog_path}")
            continue
        catalog = pd.read_csv(catalog_path)
        stage_batch(
            catalog,
            collection,
            technique,
            dynamic,
            batch_name,
            convert_mp3_to_wav=convert,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
