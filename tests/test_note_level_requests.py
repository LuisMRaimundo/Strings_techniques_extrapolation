"""Note-level Measured → Requests workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from string_technique_model.extrapolation.note_level import (
    export_note_level_workbook,
    run_from_workbook,
    run_note_level_requests,
    write_request_template,
)


def test_template_and_viola_a4_requests(tmp_path: Path) -> None:
    template = write_request_template(tmp_path / "template.xlsx")
    # Replace example with the user's mental model: viola A4 = 67
    with pd.ExcelWriter(template, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "note": "A4",
                    "value": 67.0,
                    "instrument": "vla",
                    "dynamic": "pp",
                    "technique": "ordinary",
                    "quantity": "EWSD_score_acoustic_balanced",
                }
            ]
        ).to_excel(writer, sheet_name="Measured", index=False)
        pd.DataFrame(
            [
                {"note": "A4", "technique": "con_sordino", "instrument": "vla", "dynamic": "pp"},
                {"note": "A4", "technique": "sul_tasto", "instrument": "vla", "dynamic": "pp"},
                {"note": "A4", "technique": "sul_ponticello", "instrument": "vla", "dynamic": "pp"},
                {"note": "A4", "technique": "artificial_harmonic", "instrument": "vla", "dynamic": "pp"},
            ]
        ).to_excel(writer, sheet_name="Requests", index=False)

    result = run_from_workbook(template)
    assert result["summary"]["n_requests"] == 4
    assert result["summary"]["n_matched_baseline"] == 4
    by_tech = {r["request_technique"]: r for r in result["results"]}
    assert by_tech["con_sordino"]["baseline_value"] == 67.0
    assert by_tech["con_sordino"]["attenuation_db_power"] == 4.0  # viola literature-bounded
    assert by_tech["con_sordino"]["value"] is not None  # provisional numeric estimate
    assert by_tech["con_sordino"]["value_kind"] == "extrapolated"
    assert by_tech["sul_tasto"]["baseline_value"] == 67.0
    assert by_tech["sul_tasto"]["value"] is not None
    assert by_tech["sul_tasto"]["value"] < 67.0
    assert by_tech["artificial_harmonic"]["value"] is not None
    assert "PROVISIONAL" in ";".join(by_tech["sul_tasto"]["warnings"])

    out = export_note_level_workbook(result, tmp_path / "out.xlsx")
    assert out.exists()
    frame = pd.read_excel(out, sheet_name="All_Results")
    assert "baseline_value" in frame.columns
    assert "request_note" in frame.columns
    assert "con_sordino" in pd.ExcelFile(out).sheet_names


def test_missing_note_returns_na() -> None:
    measured = [
        {
            "note": "G3",
            "value": 50.0,
            "instrument": "vla",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        }
    ]
    requests = [
        {
            "note": "A4",
            "technique": "sul_tasto",
            "instrument": "vla",
            "dynamic": "pp",
            "quantity": "EWSD_score_acoustic_balanced",
        }
    ]
    result = run_note_level_requests(measured, requests)
    assert result["results"][0]["na_reason"] == "note_not_found_in_measured"
    assert result["results"][0]["baseline_value"] is None
