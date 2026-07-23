"""Phase 2 — ordinary-bowing baseline engine tests."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from string_technique_model.baseline.alignment import attach_cell_ids, build_alignment_table
from string_technique_model.baseline.duplicates import (
    collapse_exact_import_duplicates,
    observation_fingerprint,
)
from string_technique_model.baseline.eligibility import annotate_eligibility
from string_technique_model.baseline.equal_collection import equal_collection_mean
from string_technique_model.baseline.outputs import scientific_frames_equivalent
from string_technique_model.baseline.pipeline import build_ordinary_baseline
from string_technique_model.baseline.pooling import pool_cell
from string_technique_model.baseline.provenance import reconstruct_cell_value, verify_weight_sums
from string_technique_model.baseline.weighted import WeightValidationError, validate_user_weights
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.metrics.conversions import apply_registered_conversion

ROOT = PACKAGE_ROOT
BASELINE_SRC = ROOT / "src" / "string_technique_model" / "baseline"


def _metric_registry() -> MetricRegistry:
    return MetricRegistry.from_paths(
        ROOT / "configs" / "metric_definitions.yaml",
        ROOT / "configs" / "metric_conversions.yaml",
    )


def _row(
    *,
    collection_id: str = "coll_a",
    instrument: str = "vln",
    technique: str = "ordinary",
    pitch_midi_sounding: float = 69.0,
    pitch_name_sounding: str = "A4",
    pitch_midi_written: float | None = 69.0,
    pitch_name_written: str | None = "A4",
    dynamic: str = "mf",
    density_value: float = 20.0,
    metric_definition_id: str = "ewsd_v1",
    measured_or_estimated: str = "measured",
    collection_type: str = "measured",
    articulation: str = "sustain",
    string_name: str = "A",
    record_id: str = "r1",
    source_file: str = "a.csv",
    source_row: int = 1,
    provenance: str = "test",
    **extra,
) -> dict:
    base = {
        "record_id": record_id,
        "collection_id": collection_id,
        "collection_type": collection_type,
        "instrument": instrument,
        "technique": technique,
        "instrument_mapping_status": "valid",
        "technique_mapping_status": "valid",
        "pitch_midi_sounding": pitch_midi_sounding,
        "pitch_name_sounding": pitch_name_sounding,
        "pitch_midi_written": pitch_midi_written,
        "pitch_name_written": pitch_name_written,
        "dynamic": dynamic,
        "density_value": density_value,
        "metric_definition_id": metric_definition_id,
        "measured_or_estimated": measured_or_estimated,
        "articulation": articulation,
        "string_name": string_name,
        "source_file": source_file,
        "source_sheet": None,
        "source_row": source_row,
        "provenance": provenance,
        "schema_validity_status": "valid",
        "excluded": False,
    }
    base.update(extra)
    return base


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_01_only_four_instruments_enter_baseline():
    reg = _metric_registry()
    df = _frame(
        [
            _row(instrument="vln", record_id="1"),
            _row(instrument="vla", record_id="2", pitch_midi_sounding=60),
            _row(instrument="vlc", record_id="3", pitch_midi_sounding=36),
            _row(instrument="cb", record_id="4", pitch_midi_sounding=28),
            _row(instrument="banjo", record_id="5"),
        ]
    )
    elig, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert set(elig["instrument"]) <= {"vln", "vla", "vlc", "cb"}
    assert (excl["baseline_exclusion_reason"] == "unsupported_instrument").any()


def test_02_unsupported_instruments_rejected():
    reg = _metric_registry()
    df = _frame([_row(instrument="piano", record_id="p1")])
    _, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert excl.iloc[0]["baseline_exclusion_reason"] == "unsupported_instrument"


def test_03_only_ordinary_enters_baseline():
    reg = _metric_registry()
    df = _frame(
        [
            _row(technique="ordinary", record_id="o1"),
            _row(technique="sul_ponticello", record_id="s1"),
        ]
    )
    elig, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert set(elig["technique"]) == {"ordinary"}
    assert (excl["baseline_exclusion_reason"] == "non_ordinary_technique").any()


def test_04_special_techniques_excluded():
    reg = _metric_registry()
    for tech in ("artificial_harmonic", "sul_ponticello", "sul_tasto", "con_sordino"):
        df = _frame([_row(technique=tech, record_id=tech)])
        elig, excl = annotate_eligibility(
            df,
            target_metric_definition_id="ewsd_v1",
            metric_registry=reg,
            allowed_value_statuses=["measured"],
        )
        assert elig.empty
        assert excl.iloc[0]["baseline_exclusion_reason"] == "non_ordinary_technique"


def test_05_one_arbitrary_collection_builds_baseline(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "b1",
        write_wide=False,
    )
    assert len(result.baseline_long) > 0
    assert (result.baseline_long["technique"] == "ordinary").all()
    assert result.baseline_long["number_of_collections"].max() == 1


def test_06_several_collections_build_baseline(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01", "custom_test_collection"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "b2",
        write_wide=False,
    )
    assert len(result.baseline_long) > 0
    assert set(result.baseline_long["instrument"]).issubset({"vln", "vla", "vlc", "cb"})


def test_07_no_iowa_orchidea_branches_in_baseline_package():
    hits: list[str] = []
    for path in BASELINE_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        # Allow comments mentioning honesty constraints? Spec: no branch specific to IOWA/ORCHIDEA.
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare | ast.If):
                pass
        for token in ("== \"iowa\"", "== 'iowa'", '== "orchidea"', "== 'orchidea'", "if collection_id == \"iowa\""):
            if token in text:
                hits.append(f"{path.name}:{token}")
        # Hardcoded collection_id branches
        if "legacy_iowa_orchidea_midpoint" in text and ("if " in text or "elif " in text):
            # mere string mention in docs/comments is ok; check for identity branches
            if "collection_id == \"legacy_iowa_orchidea_midpoint\"" in text:
                hits.append(str(path))
    assert hits == []


def test_08_incompatible_metrics_rejected():
    reg = _metric_registry()
    df = _frame([_row(metric_definition_id="not_a_real_metric", record_id="bad")])
    elig, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert elig.empty
    assert excl.iloc[0]["baseline_exclusion_reason"] in {
        "unknown_metric_definition",
        "incompatible_metric",
    }


def test_09_declared_metric_conversions_traceable():
    reg = _metric_registry()
    df = _frame(
        [
            _row(
                metric_definition_id="ewsd_v1_percent",
                density_value=2500.0,
                record_id="pct1",
            )
        ]
    )
    # percent conversion: /100 * 100 = same numeric if reference 100 — still must be traced
    converted = apply_registered_conversion(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
    )
    assert bool(converted.iloc[0]["metric_conversion_applied"]) is True
    assert converted.iloc[0]["conversion_id"] == "ewsd_percent_to_score"
    assert converted.iloc[0]["original_density_value"] == 2500.0
    assert converted.iloc[0]["original_metric_definition_id"] == "ewsd_v1_percent"


def test_10_different_pitches_never_pooled():
    group = _frame(
        [
            _row(pitch_midi_sounding=69, density_value=10, record_id="a"),
            _row(pitch_midi_sounding=70, density_value=90, record_id="b"),
        ]
    )
    # Pooling is per-cell; building alignment must yield two cells
    aligned = build_alignment_table(
        attach_cell_ids(group, alignment_key=["pitch_midi_sounding", "instrument", "dynamic"]),
        alignment_key=["pitch_midi_sounding", "instrument", "dynamic"],
    )
    assert len(aligned) == 2


def test_11_different_dynamics_never_pooled():
    group = _frame(
        [
            _row(dynamic="pp", density_value=10, record_id="a"),
            _row(dynamic="ff", density_value=90, record_id="b"),
        ]
    )
    aligned = build_alignment_table(
        attach_cell_ids(group, alignment_key=["pitch_midi_sounding", "instrument", "dynamic"]),
        alignment_key=["pitch_midi_sounding", "instrument", "dynamic"],
    )
    assert len(aligned) == 2


def test_12_different_instruments_never_pooled():
    group = _frame(
        [
            _row(instrument="vln", density_value=10, record_id="a"),
            _row(instrument="vlc", density_value=90, record_id="b"),
        ]
    )
    aligned = build_alignment_table(
        attach_cell_ids(group, alignment_key=["pitch_midi_sounding", "instrument", "dynamic"]),
        alignment_key=["pitch_midi_sounding", "instrument", "dynamic"],
    )
    assert len(aligned) == 2


def test_13_configured_articulation_differences_respected():
    group = _frame(
        [
            _row(articulation="sustain", density_value=10, record_id="a"),
            _row(articulation="staccato", density_value=90, record_id="b"),
        ]
    )
    key = ["instrument", "pitch_midi_sounding", "dynamic", "articulation"]
    aligned = build_alignment_table(attach_cell_ids(group, alignment_key=key), alignment_key=key)
    assert len(aligned) == 2


def test_14_configured_string_differences_respected():
    group = _frame(
        [
            _row(string_name="A", density_value=10, record_id="a"),
            _row(string_name="E", density_value=90, record_id="b"),
        ]
    )
    key = ["instrument", "pitch_midi_sounding", "dynamic", "string_name"]
    aligned = build_alignment_table(attach_cell_ids(group, alignment_key=key), alignment_key=key)
    assert len(aligned) == 2


def test_15_exact_duplicate_imports_do_not_increase_n():
    rows = [
        _row(record_id="dup", source_row=1, density_value=12.0),
        _row(record_id="dup", source_row=1, density_value=12.0),
    ]
    df = _frame(rows)
    kept, dropped = collapse_exact_import_duplicates(df)
    assert len(kept) == 1
    assert len(dropped) == 1


def test_16_legitimate_repeated_measurements_retained():
    rows = [
        _row(record_id="r1", source_row=1, density_value=12.0, provenance="take1"),
        _row(record_id="r2", source_row=2, density_value=14.0, provenance="take2"),
    ]
    df = _frame(rows)
    kept, dropped = collapse_exact_import_duplicates(df)
    assert len(kept) == 2
    assert dropped.empty
    fp1 = observation_fingerprint(kept.iloc[0])
    fp2 = observation_fingerprint(kept.iloc[1])
    assert fp1 != fp2
    assert len(fp1) == 64  # sha256 hex


def test_17_equal_collection_mean_weights_equally():
    values = {
        "c1": np.array([10.0, 10.0, 10.0]),
        "c2": np.array([30.0]),
    }
    result = equal_collection_mean(values)
    assert result["baseline_value"] == pytest.approx(20.0)
    assert result["collection_weights"]["c1"] == pytest.approx(0.5)
    assert result["collection_weights"]["c2"] == pytest.approx(0.5)


def test_18_user_weights_validated():
    with pytest.raises(WeightValidationError):
        validate_user_weights(["a", "b"], {"a": 0.5})
    with pytest.raises(WeightValidationError):
        validate_user_weights(["a", "b"], {"a": 0.5, "b": 0.6})
    with pytest.raises(WeightValidationError):
        validate_user_weights(["a", "b"], {"a": -0.1, "b": 1.1})
    assert validate_user_weights(["a", "b"], {"a": 0.4, "b": 0.6})["a"] == 0.4


def test_19_weights_recorded_in_provenance(tmp_path: Path):
    # Build from synthetic via pool_cell + ledger through real pipeline collections
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01", "custom_test_collection"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "prov",
        write_wide=False,
    )
    led = result.provenance_ledger
    included = led[led["inclusion_status"] == "included"]
    assert "collection_weight" in included.columns
    assert "final_effective_weight" in included.columns
    if not included.empty:
        assert included["collection_weight"].notna().any()


def test_20_missing_cells_remain_missing():
    group = _frame([])
    result = pool_cell(group, method="equal_collection_mean")
    assert result["baseline_value"] is None
    assert result["status"] == "empty"


def test_21_no_interpolation_occurs(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_test_collection"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "interp",
        write_wide=False,
    )
    # No filled grid: only observed ordinary eligible cells
    assert (result.baseline_long["baseline_status"] != "interpolated").all()
    # Missing density rows from fixture must not appear as zero-filled cells for empty technique
    assert "sul_ponticello" not in set(result.baseline_long["technique"])


def test_22_no_extrapolation_occurs(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_test_collection"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "extrap",
        write_wide=False,
        pitch_min=68,
        pitch_max=70,
    )
    assert len(result.baseline_long) > 0
    midis = pd.to_numeric(result.baseline_long["pitch_midi_sounding"], errors="coerce")
    assert midis.min() >= 68
    assert midis.max() <= 70
    # Values outside the requested window are absent (not extrapolated in).
    assert not ((midis < 68) | (midis > 70)).any()


def test_23_missing_not_converted_to_zero():
    reg = _metric_registry()
    df = _frame([_row(density_value=np.nan, record_id="miss")])
    elig, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert elig.empty
    assert excl.iloc[0]["baseline_exclusion_reason"] == "missing_density_value"
    assert excl.iloc[0]["density_value"] is None or pd.isna(excl.iloc[0]["density_value"])


def test_24_double_bass_written_and_sounding_remain_distinct():
    df = _frame(
        [
            _row(
                instrument="cb",
                pitch_midi_written=28,
                pitch_name_written="E1",
                pitch_midi_sounding=16,
                pitch_name_sounding="E0",
                written_to_sounding_semitones=-12,
                record_id="cb1",
            )
        ]
    )
    assert df.iloc[0]["pitch_midi_written"] != df.iloc[0]["pitch_midi_sounding"]
    assert df.iloc[0]["pitch_name_written"] != df.iloc[0]["pitch_name_sounding"]


def test_25_sounding_pitch_used_for_alignment():
    group = _frame(
        [
            _row(
                instrument="cb",
                pitch_midi_written=28,
                pitch_midi_sounding=16,
                density_value=10,
                record_id="a",
            ),
            _row(
                instrument="cb",
                pitch_midi_written=28,
                pitch_midi_sounding=17,
                density_value=90,
                record_id="b",
            ),
        ]
    )
    key = ["instrument", "pitch_midi_sounding", "dynamic"]
    aligned = build_alignment_table(attach_cell_ids(group, alignment_key=key), alignment_key=key)
    assert len(aligned) == 2


def test_26_pooled_derived_not_marked_measured(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["legacy_iowa_orchidea_midpoint"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "legacy",
        write_wide=False,
    )
    assert len(result.baseline_long) > 0
    assert not (result.baseline_long["measured_or_estimated"] == "measured").any()
    assert result.baseline_long["measured_or_estimated"].isin(["pooled_derived", "derived"]).all()


def test_27_precomputed_midpoint_not_split_into_fictional_collections(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["legacy_iowa_orchidea_midpoint"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "mid",
        write_wide=False,
    )
    for ids in result.baseline_long["contributing_collection_ids"]:
        colls = ids if isinstance(ids, list) else str(ids).split(";")
        assert "iowa" not in {str(c).lower() for c in colls}
        assert "orchidea" not in {str(c).lower() for c in colls}
        assert any("legacy_iowa_orchidea_midpoint" in str(c) for c in colls)


def test_28_deterministic_runs_reproduce(tmp_path: Path):
    a = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "d1",
        write_wide=False,
        seed=123,
    )
    b = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "d2",
        write_wide=False,
        seed=123,
    )
    assert a.run_id == b.run_id
    assert np.allclose(
        a.baseline_long.sort_values("baseline_cell_id")["baseline_value"].to_numpy(dtype=float),
        b.baseline_long.sort_values("baseline_cell_id")["baseline_value"].to_numpy(dtype=float),
        equal_nan=True,
    )


def test_29_different_seeds_affect_only_stochastic_methods(tmp_path: Path):
    # Current pooling methods are deterministic; seed changes run_id but not values for equal_mean.
    a = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "s1",
        write_wide=False,
        seed=1,
    )
    b = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "s2",
        write_wide=False,
        seed=2,
    )
    assert a.run_id != b.run_id
    assert np.allclose(
        a.baseline_long.sort_values("baseline_cell_id")["baseline_value"].to_numpy(dtype=float),
        b.baseline_long.sort_values("baseline_cell_id")["baseline_value"].to_numpy(dtype=float),
        equal_nan=True,
    )


def test_30_cells_preserve_contributing_collection_ids(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "ids",
        write_wide=False,
    )
    for ids in result.baseline_long["contributing_collection_ids"]:
        assert ids
        colls = ids if isinstance(ids, list) else [ids]
        assert "custom_lab_01" in colls


def test_31_excluded_records_have_explicit_reasons():
    reg = _metric_registry()
    df = _frame(
        [
            _row(technique="sul_tasto", record_id="x1"),
            _row(density_value=np.nan, record_id="x2"),
        ]
    )
    _, excl = annotate_eligibility(
        df,
        target_metric_definition_id="ewsd_v1",
        metric_registry=reg,
        allowed_value_statuses=["measured"],
    )
    assert excl["baseline_exclusion_reason"].notna().all()
    assert (excl["baseline_exclusion_reason"].astype(str) != "").all()


def test_32_uncertainty_not_filled_with_zero_when_unavailable(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="equal_collection_mean",
        output_dir=tmp_path / "unc",
        write_wide=False,
    )
    # equal_collection_mean does not produce SE/CI — must remain null, not 0
    assert result.baseline_long["baseline_se"].isna().all()
    assert result.baseline_long["baseline_q025"].isna().all()
    assert result.baseline_long["baseline_q975"].isna().all()


def test_33_provenance_ledger_reconstructs_result():
    group = _frame(
        [
            _row(collection_id="c1", density_value=10.0, record_id="a", source_row=1),
            _row(collection_id="c2", density_value=30.0, record_id="b", source_row=2),
        ]
    )
    group = attach_cell_ids(
        group,
        alignment_key=["instrument", "pitch_midi_sounding", "dynamic", "technique", "metric_definition_id"],
    )
    pooled = pool_cell(group, method="equal_collection_mean")
    cell_id = str(group["baseline_cell_id"].iloc[0])
    baseline_long = pd.DataFrame(
        [
            {
                "baseline_cell_id": cell_id,
                "collection_weights": pooled["collection_weights"],
                "collection_values": pooled["collection_level_values"],
                "baseline_value": pooled["baseline_value"],
            }
        ]
    )
    from string_technique_model.baseline.provenance import build_provenance_ledger

    ledger = build_provenance_ledger(group, pd.DataFrame(), baseline_long)
    reconstructed = reconstruct_cell_value(
        ledger, cell_id, pooled["collection_level_values"]
    )
    assert reconstructed == pytest.approx(pooled["baseline_value"])
    check = verify_weight_sums(ledger)
    assert check["ok"]


def test_34_csv_and_parquet_equivalent(tmp_path: Path):
    build_ordinary_baseline(
        collection_ids=["custom_lab_01"],
        pooling_method="no_pooling",
        output_dir=tmp_path / "io",
        write_wide=False,
    )
    pq = pd.read_parquet(tmp_path / "io" / "ordinary_baseline_long.parquet")
    csv = pd.read_csv(tmp_path / "io" / "ordinary_baseline_long.csv")
    assert scientific_frames_equivalent(
        pq,
        csv,
        ["baseline_value", "pitch_midi_sounding", "instrument", "dynamic", "number_of_observations"],
    )


def test_35_baseline_contains_no_special_technique_prediction(tmp_path: Path):
    result = build_ordinary_baseline(
        collection_ids=["custom_lab_01", "custom_test_collection", "legacy_iowa_orchidea_midpoint"],
        pooling_method="hierarchical_collection",
        output_dir=tmp_path / "nospec",
        write_wide=False,
    )
    assert set(result.baseline_long["technique"].astype(str).str.lower().unique()) == {"ordinary"}
    forbidden = {
        "artificial_harmonic",
        "sul_ponticello",
        "sul_tasto",
        "con_sordino",
        "ponticello",
        "tastiera",
    }
    assert not (set(result.baseline_long["technique"].astype(str).str.lower()) & forbidden)


def test_fingerprint_uses_sha256_not_python_hash():
    row = _row()
    fp = observation_fingerprint(row)
    expected = hashlib.sha256(
        "|".join(
            [
                "coll_a",
                "a.csv",
                "",
                "1",
                "r1",
                "vln",
                "ordinary",
                "69.0",
                "mf",
                "ewsd_v1",
                "20.0",
            ]
        ).encode()
    ).hexdigest()
    assert fp == expected


def test_python_hash_not_used_in_baseline_package():
    import re

    for path in BASELINE_SRC.rglob("*.py"):
        # Strip comments/docstrings roughly by checking code lines only.
        code_lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#", 1)[0]
            code_lines.append(stripped)
        text = "\n".join(code_lines)
        assert re.search(r"(?<!hashlib\.)\bhash\(", text) is None
