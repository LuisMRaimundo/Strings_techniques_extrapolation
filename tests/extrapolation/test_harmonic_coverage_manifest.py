"""Coverage manifests must reflect live measured tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
    coverage_counts,
    write_coverage_manifests,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = ROOT / "data" / "harmonic_calibration" / "manifests"


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_manifests_match_table_counts() -> None:
    paths = write_coverage_manifests()
    assert paths["vln"].exists()
    assert paths["vla"].exists()
    assert paths["vlc"].exists()

    vln = pd.read_csv(paths["vln"])
    vla = pd.read_csv(paths["vla"])
    vlc = pd.read_csv(paths["vlc"])

    art_mf = vln[(vln.technique == "artificial_harmonic") & (vln.dynamic == "mf")]
    assert int(art_mf["n_measured_notes"].sum()) >= coverage_counts("vln", "artificial_harmonic", "mf")
    # Unique notes across collections for vln art mf
    assert coverage_counts("vln", "artificial_harmonic", "mf") == 31
    assert coverage_counts("vln", "natural_harmonic", "mf") == 15
    assert coverage_counts("vln", "natural_harmonic", "p") == 9

    vla_art = vla[(vla.technique == "artificial_harmonic") & (vla.dynamic == "mf")]
    assert not vla_art.empty
    assert coverage_counts("vla", "artificial_harmonic", "mf") == 35

    vla_nat = vla[vla.technique == "natural_harmonic"]
    assert (vla_nat["n_measured_notes"] == 0).all()
    assert (vlc["n_measured_notes"] == 0).all()


def test_manifests_include_hashes_and_version() -> None:
    paths = write_coverage_manifests()
    vla = pd.read_csv(paths["vla"])
    art = vla[(vla.technique == "artificial_harmonic") & (vla.n_measured_notes > 0)]
    assert art["source_hashes"].notna().all()
    assert (art["ssa_ewsd_version"].astype(str).str.len() > 0).all()
