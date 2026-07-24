#!/usr/bin/env python3
"""Run Spectral_Analyser Stage 1–3 on a staged harmonic batch and export measured CSV."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALIB = ROOT / "data" / "harmonic_calibration"
SSA = Path(r"E:\PYTHON CODES\CÓDIGOS FINAIS - GIT HUB\Spectral_Analyser")
EXPORT = ROOT / "tools" / "harmonic_calibration" / "export_ewsd_table_from_research_xlsx.py"

# batch_name -> (collection, technique, dynamic, pattern, instrument)
BATCH_META = {
    # Violin
    "orchidea_artificial_harmonic_mf": ("orchidea", "artificial_harmonic", "mf", "*.wav", "vln"),
    "philharmonia_artificial_harmonic_mf": ("philharmonia", "artificial_harmonic", "mf", "*.wav", "vln"),
    "philharmonia_artificial_harmonic_mf_wav": ("philharmonia", "artificial_harmonic", "mf", "*.wav", "vln"),
    "philharmonia_natural_harmonic_mf": ("philharmonia", "natural_harmonic", "mf", "*.wav", "vln"),
    "philharmonia_natural_harmonic_mf_wav": ("philharmonia", "natural_harmonic", "mf", "*.wav", "vln"),
    "philharmonia_natural_harmonic_p": ("philharmonia", "natural_harmonic", "p", "*.wav", "vln"),
    "philharmonia_natural_harmonic_p_wav": ("philharmonia", "natural_harmonic", "p", "*.wav", "vln"),
    "mcgill_artificial_harmonic_mf": ("mcgill", "artificial_harmonic", "mf", "*.wav", "vln"),
    "mcgill_natural_harmonic_mf": ("mcgill", "natural_harmonic", "mf", "*.wav", "vln"),
    # Viola
    "viola_orchidea_artificial_harmonic_mf": ("orchidea", "artificial_harmonic", "mf", "*.wav", "vla"),
    "viola_philharmonia_artificial_harmonic_mf": ("philharmonia", "artificial_harmonic", "mf", "*.wav", "vla"),
    "viola_philharmonia_natural_harmonic_mf": ("philharmonia", "natural_harmonic", "mf", "*.wav", "vla"),
    "viola_mcgill_artificial_harmonic_mf": ("mcgill", "artificial_harmonic", "mf", "*.wav", "vla"),
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("batch_name", choices=sorted(BATCH_META))
    p.add_argument("--skip-ssa", action="store_true", help="Only export if research xlsx exists")
    args = p.parse_args()

    collection, technique, dynamic, pattern, instrument = BATCH_META[args.batch_name]
    audio_dir = CALIB / "batches" / args.batch_name
    out_dir = CALIB / "ssa_outputs" / args.batch_name
    research = out_dir / "compiled_density_metrics_research.xlsx"
    measured = CALIB / "measured" / f"{args.batch_name}.csv"

    if not args.skip_ssa:
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(SSA / "run_orchestrator.py"),
            "--audio-dir",
            str(audio_dir),
            "--pattern",
            pattern,
            "--main-output",
            str(out_dir),
        ]
        print("Running:", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(SSA))
        if proc.returncode != 0:
            return proc.returncode

    if not research.exists():
        print(f"Missing research workbook: {research}", file=sys.stderr)
        return 1

    export_cmd = [
        sys.executable,
        str(EXPORT),
        str(research),
        "--instrument",
        instrument,
        "--technique",
        technique,
        "--dynamic",
        dynamic,
        "--collection",
        collection,
        "--out",
        str(measured),
    ]
    print("Exporting:", " ".join(export_cmd))
    return subprocess.run(export_cmd, cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
