#!/usr/bin/env python3
"""Export STE-ready measured EWSD rows from a Spectral_Analyser research workbook."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def export_table(
    research_xlsx: Path,
    *,
    instrument: str,
    technique: str,
    dynamic: str,
    collection: str,
    out_csv: Path,
) -> pd.DataFrame:
    df = pd.read_excel(research_xlsx, sheet_name="Spectral_Density_Metrics")
    need = {"Note", "EWSD_score_acoustic_balanced"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns in {research_xlsx}: {sorted(missing)}")

    out = pd.DataFrame(
        {
            "instrument": instrument,
            "technique": technique,
            "dynamic": dynamic,
            "note": df["Note"].astype(str).str.strip(),
            "quantity": "EWSD_score_acoustic_balanced",
            "value": pd.to_numeric(df["EWSD_score_acoustic_balanced"], errors="coerce"),
            "collection": collection,
            "ewsd_primary_analysis_eligible": df.get("ewsd_primary_analysis_eligible"),
            "source_workbook": str(research_xlsx),
        }
    )
    out = out[out["value"].notna()].copy()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"wrote {len(out)} rows -> {out_csv}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("research_xlsx", type=Path)
    p.add_argument("--instrument", default="vln")
    p.add_argument("--technique", required=True)
    p.add_argument("--dynamic", required=True)
    p.add_argument("--collection", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    export_table(
        args.research_xlsx,
        instrument=args.instrument,
        technique=args.technique,
        dynamic=args.dynamic,
        collection=args.collection,
        out_csv=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
