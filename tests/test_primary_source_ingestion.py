"""Tests for verified primary-source qualitative ingestion (no EWSD activation)."""

from __future__ import annotations

from string_technique_model.literature.extracts import load_extracts
from string_technique_model.literature.pipeline import build_literature_layer
from string_technique_model.measurement_domains import load_measurement_domain_registry
from string_technique_model.production.migration import migrate_legacy_technique_record


def _extracts_for(source_id: str) -> list:
    return [e for e in load_extracts() if e.source_id == source_id]


def test_schoonderwaldt_measurement_domain_separation_extracts() -> None:
    registry = load_measurement_domain_registry()
    extracts = _extracts_for("SRC_SCHOONDERWALDT_2009")
    assert len(extracts) >= 3

    domain_extract = next(e for e in extracts if e.evidence_id == "EV_SCHOONDERWALDT_DOMAIN_SEP_001")
    assert domain_extract.measurement_domain_id == "string_velocity_at_bow"
    assert registry.get("string_velocity_at_bow") is not None
    assert domain_extract.density_mapping_status == "incompatible_variable"
    assert "radiated" in domain_extract.paraphrased_claim.lower()

    beta_extract = next(e for e in extracts if e.evidence_id == "EV_SCHOONDERWALDT_BETA_DEF_001")
    assert beta_extract.canonical_variable_name == "relative_bow_bridge_distance_beta"

    reg_warning = next(e for e in extracts if e.evidence_id == "EV_SCHOONDERWALDT_STDREG_WARNING_001")
    assert reg_warning.density_mapping_status == "insufficient_information"
    assert "standardized" in reg_warning.paraphrased_claim.lower()


def test_evangelista_nonlinear_mute_no_mass_attenuation_law() -> None:
    extracts = _extracts_for("SRC_EVANGELISTA_FREIRE_2025")
    assert len(extracts) >= 3

    nonlinear = next(e for e in extracts if e.evidence_id == "EV_EVANGELISTA_NO_MASS_ATTENUATION_LAW_001")
    claim = nonlinear.paraphrased_claim.lower()
    assert "mass" in claim
    assert "attenuation" in claim or "intensity" in claim
    assert nonlinear.density_mapping_status == "incompatible_variable"
    assert all(e.density_mapping_status != "direct_density_mapping" for e in extracts)

    ewsd_block = next(e for e in extracts if e.evidence_id == "EV_EVANGELISTA_NO_EWSD_001")
    assert ewsd_block.measurement_domain_id == "radiated_audio"
    assert "ewsd" in ewsd_block.paraphrased_claim.lower()


def test_primary_source_ingestion_does_not_activate_density() -> None:
    result = build_literature_layer(dry_run=True)
    assert result.n_active_density_parameters == 0
    new_ids = {
        "EV_SCHOONDERWALDT_BETA_DEF_001",
        "EV_EVANGELISTA_NO_MASS_ATTENUATION_LAW_001",
        "EV_FLETCHER_ROSSING_CH10_BOWED_001",
        "EV_ROSSING2010_CH12_BOWED_001",
    }
    loaded_ids = {e.evidence_id for e in load_extracts()}
    assert new_ids <= loaded_ids


def test_mute_category_additive_aliases() -> None:
    perf = migrate_legacy_technique_record({"technique": "con_sordino", "mute_type": "performance"})
    light = migrate_legacy_technique_record({"technique": "con_sordino", "mute_type": "light_practice"})
    heavy = migrate_legacy_technique_record({"technique": "con_sordino", "mute_type": "heavy_practice"})
    assert perf.mute is not None and perf.mute.category == "performance_mute"
    assert light.mute is not None and light.mute.category == "light_practice"
    assert heavy.mute is not None and heavy.mute.category == "heavy_practice"
    assert len({perf.mute.category, light.mute.category, heavy.mute.category}) == 3
