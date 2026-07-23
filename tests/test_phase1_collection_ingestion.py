"""Phase 1 — generic collection ingestion and metric compatibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from string_technique_model.collections.canonical import PHASE1_REQUIRED_COLUMNS
from string_technique_model.collections.leakage import assert_role_separation
from string_technique_model.collections.loaders import load_table
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.collections.pooling import pool_collections
from string_technique_model.collections.registry import CollectionRegistry
from string_technique_model.collections.service import (
    import_collection,
    list_collections,
    register_collection,
    validate_collection,
)
from string_technique_model.config import PACKAGE_ROOT, load_run_config
from string_technique_model.stable_seed import stable_record_id, stable_uint32

SRC = PACKAGE_ROOT / "src" / "string_technique_model"
FIXTURE = PACKAGE_ROOT / "tests" / "fixtures" / "synthetic" / "custom_test_collection.csv"

PIPELINE_FILES = [
    SRC / "pipeline.py",
    SRC / "estimate.py",
    SRC / "baselines.py",
    SRC / "collections" / "adapter.py",
    SRC / "collections" / "pooling.py",
    SRC / "collections" / "service.py",
    SRC / "collections" / "registry.py",
    SRC / "collections" / "loaders.py",
    SRC / "collections" / "schema_map.py",
    SRC / "collections" / "metrics.py",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mini_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sample_code": "X1",
                "source_instrument": "Violin",
                "execution_mode": "normale",
                "note_label": "A4",
                "midi_number": 69,
                "dyn_label": "mezzo-forte",
                "acoustic_density_result": 21.5,
                "metric_code": "ewsd_v1",
            }
        ]
    )


def _register_temp_collection(
    tmp_path: Path,
    cid: str,
    frame: pd.DataFrame,
    fmt: str,
    write_fn,
) -> Path:
    data_path = tmp_path / f"{cid}.data"
    write_fn(frame, data_path)
    schema_src = (PACKAGE_ROOT / "configs" / "schemas" / "custom_test_collection.yaml").read_text(
        encoding="utf-8"
    )
    schema_path = tmp_path / f"{cid}.yaml"
    schema_path.write_text(schema_src.replace("custom_test_collection", cid), encoding="utf-8")
    reg_path = tmp_path / "collections.yaml"
    if reg_path.exists():
        data = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
        collections = list(data.get("collections") or [])
    else:
        collections = []
    collections.append(
        {
            "collection_id": cid,
            "display_name": cid,
            "enabled": True,
            "collection_type": "measured",
            "data_paths": [str(data_path)],
            "format": fmt,
            "schema_mapping": str(schema_path),
            "metric_definition_id": "ewsd_v1",
            "default_roles": ["baseline"],
            "measured_or_estimated": "measured",
        }
    )
    reg_path.write_text(yaml.safe_dump({"collections": collections}), encoding="utf-8")
    return reg_path


def _run_yaml_for_registry(tmp_path: Path, registry_path: Path) -> Path:
    cfg = load_run_config()
    run_yaml = tmp_path / "run.yaml"
    run_yaml.write_text(
        yaml.safe_dump(
            {
                **{k: v for k, v in cfg.items() if k != "paths_resolved"},
                "run": {
                    "baseline_collection_ids": [],
                    "calibration_collection_ids": [],
                    "validation_collection_ids": [],
                    "pooling": {"enabled": False, "method": "no_pooling"},
                    "target_metric_definition_id": "ewsd_v1",
                },
                "paths": {
                    **cfg["paths"],
                    "collections_registry": str(registry_path),
                    "imported_dir": str(tmp_path / "imported"),
                    "outputs_dir": str(tmp_path / "outputs"),
                    "reports_dir": str(tmp_path / "reports"),
                },
            }
        ),
        encoding="utf-8",
    )
    return run_yaml


def test_01_unknown_collection_registered_via_config(tmp_path: Path) -> None:
    frame = _mini_frame()
    reg = _register_temp_collection(
        tmp_path, "brand_new_lab", frame, "csv", lambda df, p: df.to_csv(p, index=False)
    )
    run_yaml = _run_yaml_for_registry(tmp_path, reg)
    result = import_collection("brand_new_lab", run_yaml)
    assert result["n_records"] == 1
    assert result["collection_ids_present"] == ["brand_new_lab"]


def test_02_arbitrary_source_columns_map() -> None:
    registry = CollectionRegistry.from_yaml(PACKAGE_ROOT / "configs" / "collections.yaml")
    adapter = registry.get_adapter("custom_test_collection")
    raw = adapter.load_raw()
    assert "sample_code" in raw.columns
    canonical = adapter.map_to_canonical_schema(raw)
    row = canonical.loc[canonical["record_id"] == "CTC-001"].iloc[0]
    assert row["instrument"] == "vln"
    assert row["technique"] == "ordinary"
    assert float(row["density_value"]) == pytest.approx(23.809207)


def test_instrument_aliases_case_insensitive_no_fuzzy() -> None:
    from string_technique_model.collections.instruments_domain import normalize_instrument_label

    assert normalize_instrument_label("  Violin ") == "vln"
    assert normalize_instrument_label("VIOLONCELLO") == "vlc"
    assert normalize_instrument_label("double-bass") == "cb"
    assert normalize_instrument_label("Banjo") is None
    assert normalize_instrument_label("viol") is None  # no fuzzy / partial match
    assert normalize_instrument_label("guitare") is None


@pytest.mark.parametrize(
    "fmt,writer",
    [
        ("csv", lambda df, p: df.to_csv(p, index=False)),
        ("tsv", lambda df, p: df.to_csv(p, sep="\t", index=False)),
        ("xlsx", lambda df, p: df.to_excel(p, index=False)),
        ("json", lambda df, p: p.write_text(df.to_json(orient="records"), encoding="utf-8")),
        (
            "jsonl",
            lambda df, p: p.write_text(
                "\n".join(json.dumps(r) for r in df.to_dict(orient="records")),
                encoding="utf-8",
            ),
        ),
        ("parquet", lambda df, p: df.to_parquet(p, index=False)),
    ],
)
def test_03_to_08_format_imports(tmp_path: Path, fmt: str, writer) -> None:
    cid = f"fmt_{fmt}"
    reg = _register_temp_collection(tmp_path, cid, _mini_frame(), fmt, writer)
    run_yaml = _run_yaml_for_registry(tmp_path, reg)
    # Also unit-test loader
    data_path = tmp_path / f"{cid}.data"
    loaded = load_table(data_path, fmt)
    assert len(loaded) == 1
    result = import_collection(cid, run_yaml)
    assert result["schema_ok"] is True
    assert result["n_records"] == 1


def test_09_source_files_unchanged() -> None:
    before = _sha256(FIXTURE)
    import_collection("custom_test_collection")
    assert _sha256(FIXTURE) == before


def test_10_missing_optional_metadata_null() -> None:
    frame = pd.read_parquet(import_collection("custom_test_collection")["parquet"])
    assert frame["string_name"].isna().all()
    assert frame["pitch_name_written"].isna().all()
    ctc4 = frame.loc[frame["record_id"] == "CTC-004"].iloc[0]
    assert pd.isna(ctc4["pitch_midi_sounding"])


def test_11_missing_by_design_preserved() -> None:
    frame = pd.read_parquet(import_collection("custom_test_collection")["parquet"])
    ctc8 = frame.loc[frame["record_id"] == "CTC-008"].iloc[0]
    assert pd.isna(ctc8["density_value"])
    assert ctc8["missingness_status"] == "missing_by_design"


def test_12_unsupported_instrument_rejected_from_canonical() -> None:
    from string_technique_model.collections.instruments_domain import (
        ALLOWED_INSTRUMENTS,
        EXCLUSION_REASON_UNSUPPORTED,
    )

    report = validate_collection("custom_test_collection")
    details = report["schema"]["details"]
    assert "Banjo" in details.get("unsupported_instruments", [])
    assert any("Unsupported instruments" in w for w in report["schema"]["warnings"])

    result = import_collection("custom_test_collection")
    frame = pd.read_parquet(result["parquet"])
    assert set(frame["instrument"].dropna().unique()).issubset(ALLOWED_INSTRUMENTS)
    assert "Banjo" not in set(frame.get("original_instrument_label", pd.Series(dtype=str)).astype(str))

    rejected = pd.read_csv(result["rejected_records_csv"])
    assert len(rejected) == 1
    assert rejected.iloc[0]["original_instrument_label"] == "Banjo"
    assert rejected.iloc[0]["rejection_reason"] == EXCLUSION_REASON_UNSUPPORTED
    assert {"collection_id", "source_file", "source_row", "import_timestamp_utc", "schema_mapping_version"}.issubset(
        set(rejected.columns)
    )


def test_13_invalid_technique_reported(tmp_path: Path) -> None:
    frame = _mini_frame()
    frame.loc[0, "execution_mode"] = "col legno"
    reg = _register_temp_collection(
        tmp_path, "bad_tech", frame, "csv", lambda df, p: df.to_csv(p, index=False)
    )
    run_yaml = _run_yaml_for_registry(tmp_path, reg)
    report = validate_collection("bad_tech", run_yaml)
    assert "col legno" in report["schema"]["details"].get("invalid_techniques", [])


def test_14_duplicate_records_reported() -> None:
    report = validate_collection("custom_test_collection")
    assert report["schema"]["details"].get("duplicate_record_ids", 0) >= 1
    assert any("duplicate" in w.lower() for w in report["schema"]["warnings"])


def test_15_collection_identity_preserved() -> None:
    result = import_collection("custom_test_collection")
    frame = pd.read_parquet(result["parquet"])
    assert set(frame["collection_id"]) == {"custom_test_collection"}


def test_16_canonical_record_ids_deterministic() -> None:
    a = stable_record_id("c", "f", 1, "vln")
    b = stable_record_id("c", "f", 1, "vln")
    assert a == b
    assert a.startswith("rec_")
    assert stable_uint32("a", "b") == stable_uint32("a", "b")


def test_17_repeated_imports_same_scientific_table() -> None:
    first = import_collection("custom_test_collection")
    second = import_collection("custom_test_collection")
    assert first["content_fingerprint"] == second["content_fingerprint"]
    a = pd.read_parquet(first["parquet"])[PHASE1_REQUIRED_COLUMNS]
    b = pd.read_parquet(second["parquet"])[PHASE1_REQUIRED_COLUMNS]
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=False)


def test_18_incompatible_metrics_cannot_be_pooled() -> None:
    registry = MetricRegistry.from_paths(
        PACKAGE_ROOT / "configs" / "metric_definitions.yaml",
        PACKAGE_ROOT / "configs" / "metric_conversions.yaml",
    )
    frame = pd.DataFrame(
        [
            {
                "collection_id": "a",
                "metric_definition_id": "ewsd_v1",
                "instrument": "vln",
                "technique": "ordinary",
                "pitch_name_sounding": "A4",
                "dynamic": "mf",
                "density_value": 20.0,
                "usable_for_pooling": True,
            },
            {
                "collection_id": "b",
                "metric_definition_id": "spectral_centroid_proxy_v1",
                "instrument": "vln",
                "technique": "ordinary",
                "pitch_name_sounding": "A4",
                "dynamic": "mf",
                "density_value": 1200.0,
                "usable_for_pooling": True,
            },
        ]
    )
    cell = pool_collections(
        frame,
        method="equal_mean",
        target_metric_definition_id="ewsd_v1",
        metric_registry=registry,
    ).cells[0]
    assert "b" in cell.excluded_collections
    assert import_collection("custom_test_collection")["pooling_performed"] is False


def test_19_compatible_metrics_classified() -> None:
    registry = MetricRegistry.from_paths(
        PACKAGE_ROOT / "configs" / "metric_definitions.yaml",
        PACKAGE_ROOT / "configs" / "metric_conversions.yaml",
    )
    assert registry.compare("ewsd_v1", "ewsd_v1").status == "identical"
    legacy = validate_collection("legacy_iowa_orchidea_midpoint")
    assert legacy["compatibility"]["status"] == "identical"


def test_20_conversions_only_via_explicit_rules() -> None:
    registry = MetricRegistry.from_paths(
        PACKAGE_ROOT / "configs" / "metric_definitions.yaml",
        PACKAGE_ROOT / "configs" / "metric_conversions.yaml",
    )
    values = pd.Series([50.0])
    converted, result = registry.apply_conversion(values, "ewsd_v1_percent", "ewsd_v1")
    assert result.status == "compatible_after_unit_conversion"
    assert float(converted.iloc[0]) == pytest.approx(50.0)
    with pytest.raises(ValueError):
        registry.apply_conversion(values, "spectral_centroid_proxy_v1", "ewsd_v1")


def test_21_arbitrary_number_registered(tmp_path: Path) -> None:
    collections = []
    for i in range(6):
        cid = f"bulk_{i}"
        path = tmp_path / f"{cid}.csv"
        _mini_frame().to_csv(path, index=False)
        schema = tmp_path / f"{cid}.yaml"
        schema.write_text(
            (PACKAGE_ROOT / "configs" / "schemas" / "custom_test_collection.yaml")
            .read_text(encoding="utf-8")
            .replace("custom_test_collection", cid),
            encoding="utf-8",
        )
        collections.append(
            {
                "collection_id": cid,
                "display_name": cid,
                "enabled": True,
                "data_paths": [str(path)],
                "format": "csv",
                "schema_mapping": str(schema),
                "metric_definition_id": "ewsd_v1",
                "default_roles": ["baseline"],
                "collection_type": "measured",
            }
        )
    reg = tmp_path / "collections.yaml"
    reg.write_text(yaml.safe_dump({"collections": collections}), encoding="utf-8")
    assert len(CollectionRegistry.from_yaml(reg, root=tmp_path).list()) == 6


def test_22_single_baseline_selection() -> None:
    cfg = load_run_config()
    ids = list(cfg["run"]["baseline_collection_ids"] or [])
    assert ids, "run.baseline_collection_ids must list at least one collection"
    assert "legacy_iowa_orchidea_midpoint" in ids
    # Single-collection selection remains valid even when the run config lists several.
    result = import_collection("legacy_iowa_orchidea_midpoint")
    assert result["collection_ids_present"] == ["legacy_iowa_orchidea_midpoint"]


def test_23_multiple_collections_selectable() -> None:
    ids = ["legacy_iowa_orchidea_midpoint", "custom_lab_01", "custom_test_collection"]
    listed = {c["collection_id"] for c in list_collections()}
    assert set(ids).issubset(listed)
    fps = {cid: import_collection(cid)["content_fingerprint"] for cid in ids}
    assert len(set(fps.values())) == 3


def test_24_validation_calibration_no_leakage() -> None:
    report = assert_role_separation(["legacy_iowa_orchidea_midpoint"], ["x"], ["x"])
    assert report.ok is False


def test_25_no_iowa_orchidea_pipeline_branches() -> None:
    offenders = []
    for path in PIPELINE_FILES:
        text = path.read_text(encoding="utf-8").lower()
        if "iowa" in text or "orchidea" in text:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert offenders == []


def test_26_legacy_pooled_not_falsely_split() -> None:
    registry = CollectionRegistry.from_yaml(PACKAGE_ROOT / "configs" / "collections.yaml")
    ids = {e["collection_id"] for e in registry.list()}
    assert "legacy_iowa_orchidea_midpoint" in ids
    # Fabricated separate measured iowa/orchidea must not be enabled registry entries
    enabled = {e["collection_id"] for e in registry.list(enabled_only=True)}
    assert "iowa" not in enabled
    assert "orchidea" not in enabled
    entry = registry.get_entry("legacy_iowa_orchidea_midpoint")
    assert entry["collection_type"] == "pooled_derived"
    assert entry["measured_or_estimated"] == "derived"


def test_27_canonical_export_conforms() -> None:
    for cid in ("legacy_iowa_orchidea_midpoint", "custom_test_collection"):
        result = import_collection(cid)
        frame = pd.read_parquet(result["parquet"])
        for col in PHASE1_REQUIRED_COLUMNS:
            assert col in frame.columns


def test_28_missing_not_converted_to_zero() -> None:
    frame = pd.read_parquet(import_collection("custom_test_collection")["parquet"])
    ctc8 = frame.loc[frame["record_id"] == "CTC-008"].iloc[0]
    assert pd.isna(ctc8["density_value"])
    assert ctc8["density_value"] != 0


def test_29_no_automatic_scaling_on_import() -> None:
    # Import must preserve observed density values exactly (no z-score / min-max).
    frame = pd.read_parquet(import_collection("custom_test_collection")["parquet"])
    ctc1 = frame.loc[frame["record_id"] == "CTC-001"].iloc[0]
    assert float(ctc1["density_value"]) == pytest.approx(23.809207)


def test_30_reproducible_and_no_technique_estimates() -> None:
    result = import_collection("custom_test_collection")
    assert result["modelling_performed"] is False
    assert result["pooling_performed"] is False
    assert "estimated_density" not in result


def test_register_dry_run_does_not_write(tmp_path: Path) -> None:
    cfg = tmp_path / "collections.yaml"
    cfg.write_text("collections: []\n", encoding="utf-8")
    out = register_collection(
        "tmp_reg",
        config_path=cfg,
        data_paths=["x.csv"],
        dry_run=True,
    )
    assert out["dry_run"] is True
    assert yaml.safe_load(cfg.read_text(encoding="utf-8"))["collections"] == []
