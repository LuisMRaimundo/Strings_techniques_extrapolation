"""Ordinary-baseline → technique forecast workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.baseline.pitch import pitch_name_to_midi
from string_technique_model.config import PACKAGE_ROOT, resolve_path
from string_technique_model.constraints import QualitativeConstraintEngine
from string_technique_model.data_io import INSTRUMENT_FILE_MAP, normalize_instrument
from string_technique_model.literature.domain import ALLOWED_TECHNIQUES
from string_technique_model.prediction.modes import PredictionMode, resolve_activate_user_assumptions
from string_technique_model.prediction.pipeline import PredictionBuildResult, build_predictions
from string_technique_model.stable_seed import stable_hex


@dataclass
class FromOrdinaryResult:
    baseline_path: str
    prediction: PredictionBuildResult
    qualitative_rows: list[dict[str, Any]] = field(default_factory=list)
    summary_rows: list[dict[str, Any]] = field(default_factory=list)
    output_files: dict[str, str] = field(default_factory=dict)
    activation_mode: str = "evidence_and_qualitative_only"
    warnings: list[str] = field(default_factory=list)


def resolve_instrument_code(instrument: str) -> str:
    return normalize_instrument(instrument)


def ordinary_cdm_to_baseline_long(
    *,
    instrument: str,
    dynamic: str | None = None,
    source_json: Path | str | None = None,
) -> pd.DataFrame:
    """Flatten legacy ordinary CDM JSON into a prediction-ready baseline long table."""
    code = resolve_instrument_code(instrument)
    if source_json is None:
        fname = INSTRUMENT_FILE_MAP[code]
        source_json = PACKAGE_ROOT / "data" / "baselines" / fname
    path = resolve_path(source_json)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    spectral = payload.get("spectral_data") or {}
    rows: list[dict[str, Any]] = []
    created = datetime.now(timezone.utc).isoformat()
    run_id = f"ordcdm_{stable_hex(code, str(path), n_chars=10)}"

    for note, dyn_map in spectral.items():
        for dyn, value in (dyn_map or {}).items():
            if dynamic is not None and str(dyn) != str(dynamic):
                continue
            if value is None:
                continue
            midi = pitch_name_to_midi(str(note))
            cell_id = f"cell_{stable_hex(code, note, dyn, n_chars=12)}"
            rows.append(
                {
                    "baseline_cell_id": cell_id,
                    "target_metric_definition_id": "ewsd_v1",
                    "instrument": code,
                    "technique": "ordinary",
                    "pitch_name_sounding": str(note),
                    "pitch_midi_sounding": midi,
                    "pitch_name_written": str(note),
                    "pitch_midi_written": midi,
                    "dynamic": str(dyn),
                    "articulation": "arco",
                    "string_name": None,
                    "baseline_value": float(value),
                    "baseline_mean": float(value),
                    "baseline_median": float(value),
                    "baseline_sd": None,
                    "baseline_se": None,
                    "number_of_observations": 1,
                    "number_of_collections": 1,
                    "contributing_collection_ids": Path(path).name,
                    "pooling_method": "single_source_cdm_json",
                    "baseline_reliability_grade": "C",
                    "baseline_status": "available",
                    "measured_or_estimated": "derived",
                    "provenance": f"ordinary_cdm:{Path(path).as_posix()}",
                    "run_id": run_id,
                    "created_at_utc": created,
                }
            )
    if not rows:
        raise ValueError(
            f"No ordinary baseline rows for instrument={code} dynamic={dynamic!r} from {path}"
        )
    return pd.DataFrame(rows)


def _attach_qualitative(pred_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = QualitativeConstraintEngine.load()
    out: list[dict[str, Any]] = []
    for row in pred_rows:
        matches = engine.match(
            {
                "technique": row.get("technique"),
                "instrument": row.get("instrument"),
                "mute_type": row.get("mute_type"),
                "dynamic": row.get("dynamic"),
            },
            str(row.get("instrument") or "vln"),
        )
        if not matches:
            out.append(
                {
                    "prediction_id": row.get("prediction_id"),
                    "instrument": row.get("instrument"),
                    "technique": row.get("technique"),
                    "pitch_name_sounding": row.get("pitch_name_sounding"),
                    "dynamic": row.get("dynamic"),
                    "constraint_id": None,
                    "descriptor": None,
                    "tendency": None,
                    "strength": None,
                    "numerical_prediction_allowed": False,
                    "note": "no_matching_qualitative_constraint",
                }
            )
            continue
        for m in matches:
            out.append(
                {
                    "prediction_id": row.get("prediction_id"),
                    "instrument": row.get("instrument"),
                    "technique": row.get("technique"),
                    "pitch_name_sounding": row.get("pitch_name_sounding"),
                    "dynamic": row.get("dynamic"),
                    "constraint_id": m.constraint_id,
                    "descriptor": m.descriptor,
                    "tendency": m.tendency,
                    "strength": m.strength,
                    "numerical_prediction_allowed": m.numerical_prediction_allowed,
                    "note": "qualitative_only_not_ewsd",
                }
            )
    return out


def _summary_table(
    pred_rows: list[dict[str, Any]],
    qualitative_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    q_by_pred: dict[str, list[str]] = {}
    for q in qualitative_rows:
        pid = str(q.get("prediction_id") or "")
        if not pid or not q.get("constraint_id"):
            continue
        q_by_pred.setdefault(pid, []).append(
            f"{q.get('descriptor')}:{q.get('tendency')}({q.get('strength')})"
        )
    rows: list[dict[str, Any]] = []
    for r in pred_rows:
        pid = str(r.get("prediction_id") or "")
        rows.append(
            {
                "instrument": r.get("instrument"),
                "technique": r.get("technique"),
                "pitch_name_sounding": r.get("pitch_name_sounding"),
                "pitch_midi_sounding": r.get("pitch_midi_sounding"),
                "dynamic": r.get("dynamic"),
                "ordinary_baseline_density": r.get("baseline_density"),
                "estimated_technique_density": r.get("estimated_density_mean"),
                "result_basis": r.get("result_basis") or "evidence_gated_or_unavailable",
                "literature_validated": bool(r.get("literature_validated"))
                if r.get("literature_validated") is not None
                else False,
                "assumption_ids_used": r.get("assumption_ids_used"),
                "prediction_status": r.get("prediction_status"),
                "qualitative_tendencies": "; ".join(q_by_pred.get(pid, [])),
                "provenance": r.get("provenance"),
            }
        )
    return rows


def predict_from_ordinary(
    *,
    instrument: str,
    dynamic: str = "mf",
    techniques: list[str] | None = None,
    source_json: Path | str | None = None,
    baseline_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    mode: PredictionMode | str | None = "evidence_only",
    activate_user_assumptions: bool = False,
    n_draws: int | None = None,
    random_seed: int | None = None,
    request_extras_by_technique: dict[str, dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> FromOrdinaryResult:
    """Run ordinary → technique forecast.

    Default: qualitative constraints + NA numerical EWSD.
    Numerical assumption-based estimates only if ``activate_user_assumptions``
    and individual assumptions are flagged active in the user registry.
    """
    code = resolve_instrument_code(instrument)
    techniques = list(techniques or sorted(ALLOWED_TECHNIQUES))
    out_dir = resolve_path(output_dir or PACKAGE_ROOT / "outputs" / "predictions" / "from_ordinary")
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    if baseline_path is not None:
        bl_path = resolve_path(baseline_path)
        if not bl_path.exists():
            raise FileNotFoundError(bl_path)
    else:
        frame = ordinary_cdm_to_baseline_long(
            instrument=code, dynamic=dynamic, source_json=source_json
        )
        bl_path = out_dir / f"ordinary_baseline_{code}_{dynamic}.csv"
        frame.to_csv(bl_path, index=False)
        warnings.append(f"wrote_ordinary_baseline:{bl_path}")

    assumptions_enabled = bool(activate_user_assumptions) or resolve_activate_user_assumptions(mode)
    if assumptions_enabled:
        warnings.append(
            "USER ASSUMPTIONS ACTIVATED FOR THIS RUN — numerical results are "
            "assumption-based, not literature-validated, not evidence-based."
        )
        activation_mode = "user_assumptions_explicitly_activated"
    else:
        activation_mode = "evidence_and_qualitative_only"

    prediction = build_predictions(
        baseline_path=bl_path,
        instruments=[code],
        techniques=techniques,
        backend="metric-only",
        output_dir=out_dir / "technique_predictions",
        n_draws=n_draws,
        random_seed=random_seed,
        allow_transfer=False,
        dry_run=dry_run,
        overwrite=True,
        dynamic=[dynamic] if dynamic else None,
        request_extras_by_technique=request_extras_by_technique,
        mode=mode,
        activate_user_assumptions=activate_user_assumptions,
    )

    qualitative_rows = _attach_qualitative(prediction.rows)
    summary_rows = _summary_table(prediction.rows, qualitative_rows)

    files = dict(prediction.output_files)
    if not dry_run:
        q_path = out_dir / "qualitative_tendencies.csv"
        s_path = out_dir / "ordinary_to_technique_summary.csv"
        pd.DataFrame(qualitative_rows).to_csv(q_path, index=False)
        pd.DataFrame(summary_rows).to_csv(s_path, index=False)
        files["qualitative_tendencies.csv"] = str(q_path)
        files["ordinary_to_technique_summary.csv"] = str(s_path)
        files["ordinary_baseline_used"] = str(bl_path)
        readme = out_dir / "README_RESULT_BASIS.md"
        readme.write_text(
            "\n".join(
                [
                    "# Ordinary → technique forecast",
                    "",
                    f"- activation_mode: `{activation_mode}`",
                    "- Evidence-backed numerical EWSD technique parameters remain inactive by default.",
                    "- Qualitative tendencies are not EWSD numbers.",
                    "- If any row has `result_basis=user_assumption`, that numerical estimate is",
                    "  **assumption-based only** — not literature-validated and not evidence-based.",
                    "- See `assumption_ids_used` and `configs/user_assumptions.yaml` for units,",
                    "  scope, uncertainty, provenance, and operation/link compatibility.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        files["README_RESULT_BASIS.md"] = str(readme)

    return FromOrdinaryResult(
        baseline_path=str(bl_path),
        prediction=prediction,
        qualitative_rows=qualitative_rows,
        summary_rows=summary_rows,
        output_files=files,
        activation_mode=activation_mode,
        warnings=warnings + list(prediction.warnings),
    )
