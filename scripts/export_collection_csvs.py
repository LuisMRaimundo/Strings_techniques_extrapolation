"""Export honest legacy midpoint + helper fixtures (does not invent separate IOWA/ORCHIDEA)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INSTR_DISPLAY = {
    "violin": "Violin",
    "viola": "Viola",
    "cello": "Cello",
    "double_bass": "Contrabass",
}
DYN_DISPLAY = {"pp": "pianissimo", "mf": "mezzo-forte", "ff": "fortissimo"}


def main() -> None:
    rows: list[dict] = []
    for path in sorted((ROOT / "data" / "baselines").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        instrument = data["instrument"]
        for note, dyns in data["spectral_data"].items():
            for dynamic, value in dyns.items():
                rows.append(
                    {
                        "sample_id": f"{instrument}_{note}_{dynamic}",
                        "instr": instrument,
                        "playing_mode": "ordinary",
                        "sounding_note": note,
                        "dyn": dynamic,
                        "acoustic_density": value,
                        "filename": path.name,
                    }
                )

    legacy = ROOT / "data" / "collections" / "legacy_iowa_orchidea_midpoint"
    legacy.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(legacy / "ordinary_metrics.csv", index=False)

    # Keep a copy under the old path name for transition only (same content).
    midpoint = ROOT / "data" / "collections" / "textural_density_midpoint"
    midpoint.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(midpoint / "ordinary_metrics.csv", index=False)

    preferred = [r for r in rows if r["instr"] == "violin"][:48]
    extras = [r for r in rows if r["instr"] != "violin"][:12]
    custom_rows = []
    for row in preferred + extras:
        custom_rows.append(
            {
                "sample_identifier": "lab_" + row["sample_id"],
                "instr": INSTR_DISPLAY[row["instr"]],
                "playing_mode": "normale",
                "sounding_note": row["sounding_note"],
                "midi_sounding": None,
                "dyn": DYN_DISPLAY[row["dyn"]],
                "string": None,
                "acoustic_density": row["acoustic_density"],
                "density_unit": "dimensionless",
                "filename": row["filename"],
            }
        )
    custom = ROOT / "data" / "collections" / "custom_lab_01"
    custom.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(custom_rows).to_csv(custom / "results.csv", index=False)

    holdout_rows = []
    holdout_dir = ROOT / "data" / "validation_holdout" / "measured_techniques"
    for path in sorted(holdout_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for note, dyns in data["spectral_data"].items():
            for dynamic, value in dyns.items():
                holdout_rows.append(
                    {
                        "record": f"{data['instrument']}_{data['technique']}_{note}_{dynamic}",
                        "instrument_name": data["instrument"],
                        "tech": data["technique"],
                        "note": note,
                        "dynamic_marking": dynamic,
                        "cdm": value,
                        "src": path.name,
                    }
                )
    vdir = ROOT / "data" / "collections" / "violin_technique_holdout"
    vdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(holdout_rows).to_csv(vdir / "measured.csv", index=False)
    print(
        {
            "legacy_iowa_orchidea_midpoint": len(rows),
            "custom_lab_01": len(custom_rows),
            "holdout": len(holdout_rows),
            "note": "Did not fabricate separate iowa/orchidea measured tables.",
        }
    )


if __name__ == "__main__":
    main()
