"""Downloadable data-entry templates for manual metric entry."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from string_technique_model.manual_entry.constants import ALLOWED_INSTRUMENTS

LONG_COLUMNS = [
    "instrument",
    "technique",
    "pitch_name_sounding",
    "pitch_midi_sounding",
    "dynamic",
    "density_value",
    "metric_definition_id",
    "measured_or_estimated",
    "uncertainty_type",
    "uncertainty_value",
    "string_name",
    "harmonic_order",
    "mute_type",
    "notes",
]


def write_templates(output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    long = pd.DataFrame(columns=LONG_COLUMNS)
    # example rows restricted to four instruments
    long = pd.concat(
        [
            long,
            pd.DataFrame(
                [
                    {
                        "instrument": "vln",
                        "technique": "ordinary",
                        "pitch_name_sounding": "A4",
                        "pitch_midi_sounding": 69,
                        "dynamic": "mf",
                        "density_value": "",
                        "metric_definition_id": "ewsd_v1",
                        "measured_or_estimated": "measured",
                        "uncertainty_type": "",
                        "uncertainty_value": "",
                        "string_name": "A",
                        "harmonic_order": "",
                        "mute_type": "",
                        "notes": "",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    p = out / "template_long_format.csv"
    long.to_csv(p, index=False)
    paths["long"] = p

    # Pitch × dynamic grid
    pitches = ["G3", "G#3", "A3", "A#3", "B3", "C4"]
    dynamics = ["pp", "mf", "ff"]
    grid = pd.DataFrame({"pitch": pitches})
    for d in dynamics:
        grid[d] = ""
    p = out / "template_pitch_dynamic_grid.csv"
    grid.to_csv(p, index=False)
    paths["grid"] = p

    # Artificial harmonics
    ah = pd.DataFrame(
        columns=[
            *LONG_COLUMNS,
            "harmonic_type",
            "stopped_pitch",
            "touched_pitch",
            "touched_interval",
        ]
    )
    ah.loc[0] = {
        "instrument": "vln",
        "technique": "artificial_harmonic",
        "pitch_name_sounding": "A5",
        "pitch_midi_sounding": 81,
        "dynamic": "mf",
        "density_value": "",
        "metric_definition_id": "ewsd_v1",
        "measured_or_estimated": "measured",
        "uncertainty_type": "",
        "uncertainty_value": "",
        "string_name": "A",
        "harmonic_order": 4,
        "mute_type": "",
        "notes": "",
        "harmonic_type": "artificial",
        "stopped_pitch": "A4",
        "touched_pitch": "D5",
        "touched_interval": "P4",
    }
    p = out / "template_artificial_harmonics.csv"
    ah.to_csv(p, index=False)
    paths["artificial_harmonic"] = p

    # Con sordino
    cs = pd.DataFrame(columns=[*LONG_COLUMNS, "mute_material", "mute_mass"])
    cs.loc[0] = {
        "instrument": "vla",
        "technique": "con_sordino",
        "pitch_name_sounding": "A3",
        "pitch_midi_sounding": 57,
        "dynamic": "p",
        "density_value": "",
        "metric_definition_id": "ewsd_v1",
        "measured_or_estimated": "measured",
        "uncertainty_type": "",
        "uncertainty_value": "",
        "string_name": "A",
        "harmonic_order": "",
        "mute_type": "orchestral",
        "notes": "",
        "mute_material": "",
        "mute_mass": "",
    }
    p = out / "template_con_sordino.csv"
    cs.to_csv(p, index=False)
    paths["con_sordino"] = p

    # Repeated measurements
    reps = pd.DataFrame(
        columns=[*LONG_COLUMNS, "replicate_id", "take_id", "standard_deviation", "sample_size"]
    )
    for i in range(1, 4):
        reps.loc[i - 1] = {
            "instrument": "vlc",
            "technique": "sul_ponticello",
            "pitch_name_sounding": "C3",
            "pitch_midi_sounding": 48,
            "dynamic": "ff",
            "density_value": "",
            "metric_definition_id": "ewsd_v1",
            "measured_or_estimated": "measured",
            "uncertainty_type": "",
            "uncertainty_value": "",
            "string_name": "C",
            "harmonic_order": "",
            "mute_type": "",
            "notes": "replicate",
            "replicate_id": f"r{i}",
            "take_id": f"t{i}",
            "standard_deviation": "",
            "sample_size": "",
        }
    p = out / "template_repeated_measurements.csv"
    reps.to_csv(p, index=False)
    paths["repeated"] = p

    # Guard: no instruments outside domain in templates
    for path in paths.values():
        df = pd.read_csv(path)
        if "instrument" in df.columns:
            insts = {str(x) for x in df["instrument"].dropna().unique()}
            if not insts.issubset(ALLOWED_INSTRUMENTS):
                raise RuntimeError(f"Template {path} contains out-of-domain instruments")

    return paths
