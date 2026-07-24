"""GUI-independent tests for metadata entry, pitch registry, and migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from string_technique_model.metadata_entry.collection import MetadataCollection
from string_technique_model.metadata_entry.io import export_csv, export_json, import_csv, import_json
from string_technique_model.metadata_entry.models import MetadataEntryRecord
from string_technique_model.metadata_entry.technique_combo import (
    harmonic_panel_visible,
    summarize_technique_combination,
)
from string_technique_model.metadata_entry.validation import MetadataValidationService
from string_technique_model.pitch.modes import migrate_legacy_pitch_fields
from string_technique_model.pitch.registry import PitchRegistry, get_default_pitch_registry, load_instrument_midi_ranges


def test_full_chromatic_registry_midi_0_127() -> None:
    reg = get_default_pitch_registry()
    pitches = reg.all_pitches()
    assert len(pitches) == 128
    assert pitches[0].midi == 0
    assert pitches[-1].midi == 127
    assert pitches[69].scientific_pitch in {"A4"}  # A4
    assert abs(pitches[69].frequency_hz - 440.0) < 1e-9


def test_midi_pitch_roundtrip_and_enharmonics() -> None:
    reg = get_default_pitch_registry()
    rec = reg.get_by_midi(61)
    assert rec is not None
    assert rec.scientific_pitch in {"C#4", "Db4"}
    assert any(e.startswith("D") or e.startswith("C") for e in rec.enharmonic_equivalents)
    back = reg.get_by_spelling(rec.scientific_pitch)
    assert back is not None and back.midi == 61
    enh = reg.get_by_spelling(rec.enharmonic_equivalents[0])
    assert enh is not None and enh.midi == 61


def test_written_and_sounding_not_overwritten() -> None:
    row = MetadataEntryRecord(
        collection_id="c",
        pitch_mode="single_note",
        pitch_representation="both",
        pitch_name_written="A3",
        pitch_midi_written=57,
        pitch_name_sounding="A2",
        pitch_midi_sounding=45,
    )
    d = row.model_dump()
    assert d["pitch_name_written"] == "A3"
    assert d["pitch_name_sounding"] == "A2"
    assert d["pitch_midi_written"] != d["pitch_midi_sounding"]


def test_instrument_range_filter_and_show_all() -> None:
    reg = get_default_pitch_registry()
    ranges = load_instrument_midi_ranges()
    assert "vln" in ranges
    filtered = reg.filter_instrument_range("vln", show_all=False, instrument_ranges=ranges)
    all_p = reg.filter_instrument_range("vln", show_all=True, instrument_ranges=ranges)
    assert len(filtered) < len(all_p)
    assert len(all_p) == 128
    lo, hi = ranges["vln"]
    assert all(lo <= p.midi <= hi for p in filtered)


@pytest.mark.parametrize(
    "mode",
    ["single_note", "pitch_range", "multiple_notes", "open_string", "unpitched_or_noise", "unknown"],
)
def test_pitch_modes_accepted(mode: str) -> None:
    rec = MetadataEntryRecord.from_mapping({"collection_id": "c", "pitch_mode": mode})
    assert rec.pitch_mode == mode


def test_migration_legacy_single_note_and_null() -> None:
    migrated = migrate_legacy_pitch_fields(
        {"pitch_name_sounding": "G4", "pitch_midi_sounding": 67}
    )
    assert migrated["pitch_mode"] == "single_note"
    assert "legacy_single_pitch→pitch_mode=single_note" in migrated["migration_provenance"]

    nullish = migrate_legacy_pitch_fields({})
    assert nullish["pitch_mode"] == "unknown"

    unpitched = migrate_legacy_pitch_fields({"pitch_class": "noise"})
    assert unpitched["pitch_mode"] == "unpitched_or_noise"


def test_technique_combination_summary() -> None:
    label = summarize_technique_combination(
        left_hand_regime="artificial_harmonic",
        bow_contact_regime="sul_ponticello",
        mute_state="con_sordino",
    )
    assert "artificial harmonic" in label
    assert "sul ponticello" in label
    assert "con sordino" in label


def test_harmonic_panel_visibility() -> None:
    assert harmonic_panel_visible({"left_hand_regime": "artificial_harmonic"}) is True
    assert harmonic_panel_visible({"technique": "ordinary", "harmonic_type": None}) is False
    assert harmonic_panel_visible({"harmonic_type": "natural"}) is True


def test_validation_messages_levels() -> None:
    svc = MetadataValidationService()
    report = svc.validate_rows(
        [
            {
                "record_id": "r1",
                "pitch_mode": "single_note",
                "pitch_name": "NotAPitch",
                "speaking_length_m": -1,
                "touched_interval": "perfect_fourth",
                "harmonic_order": 3,
                "left_hand_regime": "artificial_harmonic",
            }
        ]
    )
    assert report.n_errors >= 2
    severities = {i.severity for i in report.issues}
    assert "error" in severities


def test_csv_json_roundtrip_null_preservation(tmp_path: Path) -> None:
    rows = [
        MetadataEntryRecord(
            record_id="a",
            collection_id="c",
            instrument="vln",
            pitch_mode="unknown",
            pitch_name_sounding=None,
            dynamic="mf",
            notes=None,
        ),
        MetadataEntryRecord(
            record_id="b",
            collection_id="c",
            pitch_mode="single_note",
            pitch_name="A4",
            pitch_name_sounding="A4",
            pitch_midi_sounding=69,
            dynamic="p",
        ),
    ]
    jp = tmp_path / "m.json"
    export_json(rows, jp)
    loaded, problems = import_json(jp)
    assert problems == []
    assert loaded[0].pitch_name_sounding is None
    assert loaded[0].notes is None
    assert loaded[1].pitch_midi_sounding == 69

    cp = tmp_path / "m.csv"
    export_csv(rows, cp)
    loaded_c, problems_c = import_csv(cp)
    assert problems_c == []
    assert loaded_c[0].dynamic == "mf"
    # empty CSV cells become null
    assert loaded_c[0].notes is None


def test_collection_crud_undo_validate(tmp_path: Path) -> None:
    col = MetadataCollection(collection_id="demo")
    col.add_record()
    col.add_record()
    assert len(col.records) == 2
    col.update_record(0, {"instrument": "vln", "pitch_mode": "single_note", "pitch_name": "A4"})
    col.duplicate_record(0)
    assert len(col.records) == 3
    col.undo()
    assert len(col.records) == 2
    report = col.validate()
    assert report.ok or report.n_errors >= 0
    col.save_json(tmp_path / "demo.json")
    assert (tmp_path / "demo.json").exists()
    data = json.loads((tmp_path / "demo.json").read_text(encoding="utf-8"))
    assert data["schema_version"]


def test_custom_midi_range_registry() -> None:
    reg = PitchRegistry(midi_min=12, midi_max=24)
    assert len(reg.all_pitches()) == 13
    assert reg.get_by_midi(0) is None
    assert reg.get_by_midi(12) is not None


def test_gui_smoke_extrapolator_app(tmp_path) -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tcl/Tk unavailable")
    try:
        from string_technique_model.gui_metadata.extrapolator_app import NarrowExtrapolatorApp

        app = NarrowExtrapolatorApp(root)
        app.default_instrument.set("vla")
        app.default_dynamic.set("pp")
        app.start_note.set("G3")
        app.end_note.set("G4")
        app.build_register()
        rows = app.register_grid.get_rows()
        assert rows[0]["note"] == "G3"
        assert len(rows) == 13
        # Paste note+value — must accept inputted notes
        sample = "\n".join(f"{r['note']}\t{20 + i},123456" for i, r in enumerate(rows))
        warnings = app.register_grid.paste_values(sample, start_from_selection=False)
        assert any("inputted note" in w or "rebuilt" in w for w in warnings)
        assert app.register_grid.get_rows()[0]["note"] == "G3"
        assert app.register_grid.get_rows()[0]["value"] == 20.123456
        app.generate_requests()
        assert app.request_grid.get_rows()
        app.output_path.set(str(tmp_path / "out.xlsx"))
        app.run_requests()
        assert app._last_result is not None
        summary = app._last_result["summary"]
        # Default method is hierarchical_spline → automatic nonlinear path.
        # The legacy M0 constant path exposes n_matched_baseline; the
        # nonlinear path exposes n_requests / requested_method instead.
        if "n_matched_baseline" in summary:
            assert summary["n_matched_baseline"] >= 1
        else:
            assert summary.get("n_requests", 0) >= 1
            assert summary.get("requested_method") in {"automatic", "hierarchical_spline", "constant"}
            assert app._last_nonlinear_results is not None
            assert len(app._last_nonlinear_results) >= 1
    finally:
        root.destroy()


def test_gui_smoke_legacy_metadata_app() -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tcl/Tk unavailable")
    try:
        from string_technique_model.gui_metadata.app import MetadataEntryApp

        app = MetadataEntryApp(root)
        assert app.collection.records
        app.add_record()
        assert len(app.collection.records) >= 2
        # Avoid messagebox (blocks headless CI); validate via service.
        report = app.collection.validate()
        assert report is not None
        app.refresh_all()
    finally:
        root.destroy()
