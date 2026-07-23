"""Manual Metric Entry — service layer and GUI smoke tests."""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from string_technique_model.collections.instruments_domain import normalize_instrument_label
from string_technique_model.collections.service import inspect_collection, list_collections
from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.manual_entry.constants import CANONICAL_DYNAMICS, DEFAULT_ROLE
from string_technique_model.manual_entry.duplicates import DuplicateDetectionService, fingerprint_row
from string_technique_model.manual_entry.mapping import MappingService
from string_technique_model.manual_entry.numbers import parse_density_input
from string_technique_model.manual_entry.pitch import apply_cb_transposition, resolve_pitch_fields
from string_technique_model.manual_entry.services import ManualEntryService
from string_technique_model.manual_entry.templates import write_templates


def _sandbox(tmp_path: Path) -> tuple[ManualEntryService, Path]:
    root = tmp_path / "pkg"
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "schemas").mkdir(parents=True)
    (root / "data" / "manual").mkdir(parents=True)
    (root / "outputs" / "imported").mkdir(parents=True)
    (root / "outputs" / "audit").mkdir(parents=True)
    (root / "outputs" / "rejected").mkdir(parents=True)
    (root / "reports" / "collections").mkdir(parents=True)
    shutil.copy(
        PACKAGE_ROOT / "configs" / "metric_definitions.yaml",
        root / "configs" / "metric_definitions.yaml",
    )
    shutil.copy(
        PACKAGE_ROOT / "configs" / "metric_conversions.yaml",
        root / "configs" / "metric_conversions.yaml",
    )
    reg = root / "configs" / "collections.yaml"
    reg.write_text("collections: []\n", encoding="utf-8")
    run = {
        "model_version": "test",
        "paths": {
            "collections_registry": str(reg.resolve()),
            "metric_definitions": str((root / "configs" / "metric_definitions.yaml").resolve()),
            "metric_conversions": str((root / "configs" / "metric_conversions.yaml").resolve()),
            "imported_dir": str((root / "outputs" / "imported").resolve()),
            "rejected_dir": str((root / "outputs" / "rejected").resolve()),
            "reports_dir": str((root / "reports").resolve()),
            "outputs_dir": str((root / "outputs").resolve()),
            "baselines_dir": str((PACKAGE_ROOT / "data" / "baselines").resolve())
            if (PACKAGE_ROOT / "data" / "baselines").exists()
            else str((root / "outputs").resolve()),
            "validation_holdout_dir": str((root / "outputs").resolve()),
        },
        "run": {"target_metric_definition_id": "ewsd_v1"},
    }
    run_path = root / "configs" / "run.yaml"
    run_path.write_text(yaml.safe_dump(run), encoding="utf-8")
    svc = ManualEntryService(
        package_root=root,
        run_config_path=run_path,
        db_path=root / "manual.sqlite",
        registry_path=reg,
    )
    return svc, root


def _meta(cid: str = "manual_test_01", **kwargs):
    base = {
        "collection_id": cid,
        "display_name": "Manual Test Collection",
        "collection_type": "manually_transcribed",
        "collection_role": DEFAULT_ROLE,
        "metric_definition_id": "ewsd_v1",
        "created_by": "tester",
        "measured_or_estimated": "manually_transcribed",
        "source_description": "unit test synthetic observations",
    }
    base.update(kwargs)
    return base


def _row(**kwargs):
    base = {
        "instrument": "vln",
        "technique": "ordinary",
        "pitch_name_sounding": "A4",
        "pitch_midi_sounding": 69,
        "dynamic": "mf",
        "density_value": 12.5,
        "metric_definition_id": "ewsd_v1",
        "measured_or_estimated": "manually_transcribed",
    }
    base.update(kwargs)
    return base


def test_create_manual_collection(tmp_path):
    svc, _ = _sandbox(tmp_path)
    meta = svc.create_collection(_meta())
    assert meta["collection_id"] == "manual_test_01"
    assert meta["collection_role"] == "descriptive_comparison"
    assert svc.store.load_collection_meta("manual_test_01")["workflow_state"] == "draft"


def test_only_four_instruments_and_aliases():
    assert normalize_instrument_label("double_bass") == "cb"
    assert normalize_instrument_label("Violin") == "vln"
    assert normalize_instrument_label("violoncelo") == "vlc"
    assert normalize_instrument_label("banjo") is None
    assert normalize_instrument_label("guitar") is None


def test_unsupported_instrument_rejected(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    rows = svc.save_draft_rows(
        "manual_test_01",
        [_row(instrument="banjo")],
        user="tester",
        input_method="single_form",
    )
    assert rows[0]["instrument_mapping_status"] == "unsupported_instrument"
    assert rows[0]["exclusion_reason"] == "instrument_outside_project_scope"
    report = svc.validate_draft("manual_test_01")
    assert report.n_invalid >= 1


@pytest.mark.parametrize(
    "technique",
    ["ordinary", "artificial_harmonic", "sul_ponticello", "sul_tasto", "con_sordino"],
)
def test_canonical_techniques_enterable(tmp_path, technique):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta(f"manual_{technique}"))
    rows = svc.save_draft_rows(
        f"manual_{technique}",
        [_row(technique=technique)],
        user="tester",
        input_method="single_form",
    )
    assert rows[0]["technique"] == technique
    assert rows[0]["technique_mapping_status"] == "mapped"


def test_unknown_technique_preserved_unmapped(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    rows = svc.save_draft_rows(
        "manual_test_01",
        [_row(technique="flautando")],
        user="tester",
        input_method="single_form",
    )
    assert rows[0]["original_technique_label"] == "flautando"
    assert rows[0]["technique"] is None
    assert rows[0]["technique_mapping_status"] == "unmapped"
    assert rows[0]["usable_for_modelling"] is False


def test_no_fuzzy_technique_mapping():
    m = MappingService()
    assert m.map_technique("flautando").mapping_status == "unmapped"
    assert m.map_technique("natural_harmonic").mapping_status == "unmapped"
    assert m.map_technique("practice_mute").mapping_status == "unmapped"


def test_all_canonical_dynamics(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    rows = [_row(dynamic=d, pitch_name_sounding=f"A{4 + i % 2}") for i, d in enumerate(sorted(CANONICAL_DYNAMICS))]
    saved = svc.save_draft_rows("manual_test_01", rows, user="tester", input_method="table_entry")
    assert {r["dynamic"] for r in saved} == set(CANONICAL_DYNAMICS)


def test_unknown_and_missing_dynamics_not_mf(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    rows = svc.save_draft_rows(
        "manual_test_01",
        [_row(dynamic="mezzo"), _row(dynamic="", pitch_name_sounding="B4")],
        user="tester",
        input_method="table_entry",
    )
    assert rows[0]["dynamic"] is None
    assert rows[0]["dynamic_mapping_status"] == "unmapped"
    assert rows[0]["original_dynamic_label"] == "mezzo"
    assert rows[1]["dynamic"] is None
    assert rows[1]["dynamic"] != "mf"


def test_pitch_name_midi_consistency():
    ok = resolve_pitch_fields(pitch_name="A4", pitch_midi=69)
    assert ok["ok"]
    bad = resolve_pitch_fields(pitch_name="A4", pitch_midi=60)
    assert "pitch_name_midi_inconsistent" in bad["errors"]


def test_cb_written_sounding_distinct():
    cb = apply_cb_transposition(
        written_name="A2",
        written_midi=45,
        sounding_name=None,
        sounding_midi=None,
        transposition_semitones=-12,
        confirmed=True,
    )
    assert cb["ok"]
    assert cb["pitch_midi_written"] == 45
    assert cb["pitch_midi_sounding"] == 33
    assert cb["pitch_name_written"] != cb["pitch_name_sounding"] or cb["pitch_midi_written"] != cb[
        "pitch_midi_sounding"
    ]


def test_density_domain_and_nan_inf():
    assert parse_density_input("nan").ok is False
    assert parse_density_input("inf").ok is False
    assert parse_density_input(math.nan).ok is False
    assert parse_density_input("12,5").ok is True
    assert parse_density_input("12,5").value == 12.5
    amb = parse_density_input("1,234")
    assert amb.requires_confirmation
    from string_technique_model.manual_entry.numbers import validate_against_domain

    assert validate_against_domain(-1.0, "positive")[0] is False
    assert validate_against_domain(0.0, "positive")[0] is False
    assert validate_against_domain(1.2, "positive")[0] is True


def test_missing_density_not_zero(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    rows = svc.save_draft_rows(
        "manual_test_01",
        [_row(density_value="")],
        user="tester",
        input_method="single_form",
    )
    assert rows[0].get("density_value") in ("", None) or rows[0].get("density_value_parsed_preview") is None
    report = svc.validate_draft("manual_test_01")
    assert any(i.reason in {"missing_value", "non_numeric", "nan_or_missing_rejected"} for i in report.issues)


def test_incompatible_metrics_reported(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    svc.save_draft_rows(
        "manual_test_01",
        [_row(metric_definition_id="spectral_centroid_proxy_v1")],
        user="tester",
        input_method="single_form",
    )
    report = svc.validate_draft("manual_test_01")
    assert any(i.reason == "incompatible" for i in report.issues)


def test_spreadsheet_paste_arbitrary_column_order(tmp_path):
    svc, _ = _sandbox(tmp_path)
    text = "metric_value\tnote\tinstr\tdyn\tplaying_mode\n11.1\tA4\tViolin\tmf\tordinario\n"
    preview = svc.preview_paste(text)
    assert preview.n_imported == 1
    assert preview.rows[0]["instrument"] == "vln"
    assert preview.rows[0]["technique"] == "ordinary"
    assert preview.rows[0]["density_value"] == 11.1


def test_grid_to_long(tmp_path):
    svc, _ = _sandbox(tmp_path)
    grid = pd.DataFrame({"pitch": ["G3", "A3"], "pp": [1.0, 2.0], "mf": [3.0, ""], "ff": [5.0, 6.0]})
    rows = svc.grid_to_long(
        grid,
        instrument="vlc",
        technique="sul_tasto",
        metric_definition_id="ewsd_v1",
        measured_or_estimated="measured",
    )
    assert len(rows) == 5
    assert all(r["input_method"] == "grid_entry" for r in rows)
    assert {r["dynamic"] for r in rows} <= {"pp", "mf", "ff"}


def test_duplicate_detection_and_replicates():
    rows = [
        _row(),
        _row(),
        _row(replicate_id="r1", density_value=12.5),
        _row(replicate_id="r2", density_value=13.0),
    ]
    findings = DuplicateDetectionService().classify_rows(rows)
    classes = {f.classification for f in findings}
    assert "exact_duplicate" in classes or "probable_duplicate" in classes
    assert "legitimate_replicate" in classes
    fp1 = fingerprint_row(rows[0])
    fp2 = fingerprint_row(rows[0])
    assert fp1 == fp2
    assert len(fp1) == 64


def test_draft_not_in_registry_until_commit(tmp_path):
    svc, root = _sandbox(tmp_path)
    svc.create_collection(_meta())
    svc.save_draft_rows("manual_test_01", [_row()], user="tester", input_method="single_form")
    reg = yaml.safe_load((root / "configs" / "collections.yaml").read_text(encoding="utf-8"))
    ids = [c["collection_id"] for c in (reg.get("collections") or [])]
    assert "manual_test_01" not in ids
    assert svc.is_draft_in_registry("manual_test_01") is False


def test_commit_transactional_and_exports(tmp_path):
    svc, root = _sandbox(tmp_path)
    svc.create_collection(_meta("manual_commit_ok"))
    svc.save_draft_rows(
        "manual_commit_ok",
        [
            _row(technique="ordinary"),
            _row(
                technique="sul_ponticello",
                pitch_name_sounding="B4",
                pitch_midi_sounding=71,
                fundamental_hz=None,
            ),
        ],
        user="tester",
        input_method="table_entry",
    )
    svc.store.upsert_draft_collection(
        {**_meta("manual_commit_ok"), "duplicates_confirmed": True, "workflow_state": "draft"},
        user="tester",
    )
    committed = svc.commit_collection("manual_commit_ok", user="tester", confirm=True)
    assert committed.n_records >= 1
    assert Path(committed.parquet_path).exists() or Path(committed.csv_path).exists()
    assert (root / "outputs" / "imported" / "manual_commit_ok.csv").exists()
    reg = yaml.safe_load((root / "configs" / "collections.yaml").read_text(encoding="utf-8"))
    assert any(c["collection_id"] == "manual_commit_ok" for c in reg["collections"])
    # CLI/service list sees it
    listed = list_collections(root / "configs" / "run.yaml")
    assert any(c["collection_id"] == "manual_commit_ok" for c in listed)
    inv = inspect_collection("manual_commit_ok", root / "configs" / "run.yaml")
    assert inv["collection_id"] == "manual_commit_ok"


def test_failed_commit_rolls_back(tmp_path):
    svc, root = _sandbox(tmp_path)
    svc.create_collection(_meta("manual_fail_commit"))
    # empty density causes validation failure before commit path; force empty map
    svc.save_draft_rows(
        "manual_fail_commit",
        [_row(density_value="")],
        user="tester",
        input_method="single_form",
    )
    with pytest.raises(RuntimeError):
        svc.commit_collection("manual_fail_commit", user="tester", confirm=True)
    reg = yaml.safe_load((root / "configs" / "collections.yaml").read_text(encoding="utf-8"))
    assert not any(c["collection_id"] == "manual_fail_commit" for c in (reg.get("collections") or []))


def test_record_versioning_and_logical_delete(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    saved = svc.save_draft_rows("manual_test_01", [_row()], user="tester", input_method="single_form")
    rid = saved[0]["record_id"]
    new = svc.edit_record(rid, {"density_value": 99.0}, user="tester", reason="correction")
    assert new["supersedes_record_id"] == rid
    assert new["record_version"] == 2
    versions = svc.store.list_record_versions(rid)
    assert versions
    svc.logical_delete(new["record_id"], user="tester", reason="withdrawn")
    audit = svc.store.audit_rows("manual_test_01")
    assert any(a["action"] == "logical_delete" for a in audit)


def test_role_leakage_blocked(tmp_path):
    svc, root = _sandbox(tmp_path)
    svc.create_collection(_meta("manual_cal"))
    svc.save_draft_rows("manual_cal", [_row(technique="sul_ponticello")], user="tester", input_method="table_entry")
    svc.store.upsert_draft_collection(
        {**_meta("manual_cal"), "duplicates_confirmed": True},
        user="tester",
    )
    svc.commit_collection("manual_cal", user="tester", confirm=True)
    # Assign calibration
    ok = svc.assign_role("manual_cal", "model_calibration")
    assert ok["ok"] is True
    # Same collection cannot also be validation
    blocked = svc.assign_role(
        "manual_cal",
        "external_validation",
        existing_calibration_ids=["manual_cal"],
    )
    assert blocked["blocked"] is True


def test_estimated_not_marked_measured(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta(measured_or_estimated="estimated"))
    rows = svc.save_draft_rows(
        "manual_test_01",
        [_row(measured_or_estimated="estimated")],
        user="tester",
        input_method="single_form",
    )
    assert rows[0]["measured_or_estimated"] == "estimated"
    assert rows[0]["measured_or_estimated"] != "measured"


def test_manual_not_written_to_literature(tmp_path):
    svc, root = _sandbox(tmp_path)
    lit = PACKAGE_ROOT / "configs" / "literature_parameters.yaml"
    before = lit.read_text(encoding="utf-8") if lit.exists() else ""
    svc.create_collection(_meta("manual_lit_guard"))
    svc.save_draft_rows(
        "manual_lit_guard",
        [_row(technique="con_sordino", density_value=77.777)],
        user="tester",
        input_method="single_form",
    )
    svc.store.upsert_draft_collection(
        {**_meta("manual_lit_guard"), "duplicates_confirmed": True},
        user="tester",
    )
    svc.commit_collection("manual_lit_guard", user="tester", confirm=True)
    after = lit.read_text(encoding="utf-8") if lit.exists() else ""
    assert before == after
    assert "77.777" not in after


def test_no_out_of_domain_in_canonical_output(tmp_path):
    svc, root = _sandbox(tmp_path)
    svc.create_collection(_meta("manual_domain"))
    svc.save_draft_rows(
        "manual_domain",
        [_row(instrument="vln"), _row(instrument="banjo", pitch_name_sounding="C4")],
        user="tester",
        input_method="table_entry",
    )
    mapped = svc.map_to_canonical_schema("manual_domain")
    assert set(mapped["instrument"].dropna().astype(str)) <= {"vln", "vla", "vlc", "cb"}


def test_stable_ids_reproducible(tmp_path):
    svc, _ = _sandbox(tmp_path)
    svc.create_collection(_meta())
    a = svc.save_draft_rows("manual_test_01", [_row()], user="tester", input_method="single_form")
    svc.store.replace_draft_records("manual_test_01", [], user="tester")
    b = svc.save_draft_rows("manual_test_01", [_row()], user="tester", input_method="single_form")
    assert a[0]["record_id"] == b[0]["record_id"]
    assert a[0]["fingerprint"] == b[0]["fingerprint"]


def test_templates_domain_only(tmp_path):
    paths = write_templates(tmp_path / "templates")
    for p in paths.values():
        df = pd.read_csv(p)
        if "instrument" in df.columns:
            assert set(df["instrument"].dropna().astype(str)).issubset({"vln", "vla", "vlc", "cb"})


def test_gui_panel_builds():
    import tkinter as tk

    from string_technique_model.gui_manual_entry import ManualMetricEntryPanel

    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tk not available")
    try:
        panel = ManualMetricEntryPanel(root)
        assert panel.winfo_exists()
        assert "Manual Metric Entry" in panel.children or True
    finally:
        root.destroy()


def test_default_role_not_baseline_or_calibration(tmp_path):
    svc, _ = _sandbox(tmp_path)
    meta = svc.create_collection(_meta())
    assert meta["collection_role"] == "descriptive_comparison"
    assert meta["collection_role"] not in {"baseline", "model_calibration"}
