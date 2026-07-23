"""Regenerate nonlinear_extrapolation_results.xlsx for audit review."""

from pathlib import Path

import pandas as pd

from string_technique_model.extrapolation.nonlinear import export_nonlinear_workbook, predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes

reg = build_register_from_notes("G3", "G7", "vln", "ff")
rows = [
    {
        "note": r["note"],
        "midi": r["midi"],
        "value": 40 * (0.985**i),
        "instrument": "vln",
        "dynamic": "ff",
        "technique": "ordinary",
        "quantity": "EWSD_score_acoustic_balanced",
        "source_path": f"synthetic_integration_test://{r['note']}",
        "data_status": "synthetic_integration_test",
        "scientific_use": "prohibited_for_doctoral_evidence",
        "import_run_id": "regen_audit_script",
    }
    for i, r in enumerate(reg)
]
all_r = []
for t in ["con_sordino", "sul_tasto", "sul_ponticello", "artificial_harmonic", "natural_harmonic"]:
    all_r.extend(
        predict_register(
            rows,
            technique=t,
            instrument="vln",
            dynamic="ff",
            harmonic_selection_mode="configured_physically_plausible_harmonics",
            harmonic_sounding_max="C8",
            include_low_harmonics=True,
        )
    )
out = export_nonlinear_workbook(
    all_r,
    Path("outputs/nonlinear_extrapolation_results.xlsx"),
    run_metadata={
        "requested_method": "automatic",
        "gui_displayed_method": "hierarchical_spline",
        "effective_selection_mode": "automatic",
        "harmonic_selection_mode": "configured_physically_plausible_harmonics",
    },
)
run = pd.read_excel(out, sheet_name="Run_Summary")
print(run.to_string(index=False))
notes = pd.read_excel(out, sheet_name="Note_Level_Results")
print("n_rows", len(notes), notes["technique"].value_counts().to_dict())
un = pd.read_excel(out, sheet_name="Unavailable")
print("unavailable", len(un))
print("out", out)
