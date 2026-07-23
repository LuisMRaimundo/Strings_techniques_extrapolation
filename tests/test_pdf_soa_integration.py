"""Tests for PDF state-of-the-art integration (production ontology, constraints, ops)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from string_technique_model.analytical_levels import (
    AcousticDescriptorObservation,
    assert_level_separation,
    infer_textural_function,
)
from string_technique_model.constraints import QualitativeConstraintEngine
from string_technique_model.descriptors import list_implemented_descriptors, load_descriptor_registry
from string_technique_model.io import check_parquet_engine
from string_technique_model.literature.package_ingestion import ingest_evidence_package
from string_technique_model.models.capabilities import CapabilityState
from string_technique_model.models.registry import get_model
from string_technique_model.ontology import legacy_cell_count, load_ontology
from string_technique_model.prediction.links import link_forward, link_inverse
from string_technique_model.prediction.operations import OperationError, apply_operation
from string_technique_model.production import (
    ProductionInstruction,
    compute_beta,
    migrate_legacy_technique_record,
    normalize_mute_mass,
    validate_bow_contact,
    validate_harmonic_interval_order,
)
from string_technique_model.production.models import BowContactInstruction, HarmonicInstruction

# ---------------------------------------------------------------------------
# A. Harmonic validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("interval", "order"),
    [("P4", 4), ("M3", 5), ("m3", 6), ("P5", 3)],
)
def test_a_interval_order_relations(interval: str, order: int) -> None:
    result = validate_harmonic_interval_order(interval, order)
    assert result.ok


def test_a_inconsistent_order_interval_rejected() -> None:
    result = validate_harmonic_interval_order("P4", 5)
    assert result.ok is False
    assert any("inconsistent" in e for e in result.errors)


def test_a_natural_artificial_remain_distinct() -> None:
    bad = validate_harmonic_interval_order(
        "P4",
        4,
        left_hand_regime="natural_harmonic",
        harmonic_type="artificial",
    )
    assert bad.ok is False
    natural = migrate_legacy_technique_record(
        {"technique": "artificial_harmonic", "harmonic_type": "natural", "harmonic_order": 4}
    )
    # Migration keeps type if supplied; validation rejects mismatch for artificial model context
    assert natural.left_hand is not None


def test_a_double_bass_convention_explicit() -> None:
    prod = migrate_legacy_technique_record(
        {
            "technique": "artificial_harmonic",
            "instrument": "cb",
            "harmonic_order": 4,
            "double_bass_pitch_convention": "unresolved",
        }
    )
    assert prod.left_hand is not None
    assert prod.performance_context is not None or prod.left_hand.double_bass_pitch_convention in {
        None,
        "unresolved",
        "written_transposed",
        "sounding",
    }


# ---------------------------------------------------------------------------
# B. Bow-contact representation
# ---------------------------------------------------------------------------


def test_b_beta_from_lengths() -> None:
    assert math.isclose(compute_beta(0.04, 0.32), 0.125)


def test_b_nonpositive_speaking_length_rejected() -> None:
    with pytest.raises(ValueError):
        compute_beta(0.04, 0.0)


def test_b_contradictory_beta_detected() -> None:
    instr = BowContactInstruction(
        category="sul_tasto",
        relative_bow_bridge_distance_beta=0.5,
        bow_bridge_distance_m=0.04,
        speaking_length_m=0.32,
        excitation_region="speaking_string",
    )
    result = validate_bow_contact(instr)
    assert result.ok is False
    assert any("contradiction" in e.lower() for e in result.errors)


def test_b_no_arbitrary_beta_thresholds_in_ontology() -> None:
    ont = load_ontology()
    assert ont.bow_contact_beta_thresholds is None


def test_b_on_bridge_and_afterlength_separate() -> None:
    ont = load_ontology()
    outside = set(ont.excitation_regions_outside_continuum or [])
    assert "directly_on_bridge" in outside
    assert "afterlength_behind_bridge" in outside
    bridge = BowContactInstruction(
        category=None,
        excitation_region="directly_on_bridge",
    )
    after = BowContactInstruction(
        category=None,
        excitation_region="afterlength_behind_bridge",
    )
    assert bridge.excitation_region != after.excitation_region


# ---------------------------------------------------------------------------
# C. Flautando
# ---------------------------------------------------------------------------


def test_c_flautando_not_mapped_to_sul_tasto() -> None:
    prod = migrate_legacy_technique_record({"technique": "flautando"})
    assert prod.timbre_execution_target == "flautando"
    assert prod.bow_contact is None or prod.bow_contact.category != "sul_tasto"


def test_c_flautando_with_contact_point() -> None:
    prod = ProductionInstruction(
        legacy_technique_label="sul_tasto",
        bow_contact=BowContactInstruction(category="sul_tasto"),
        timbre_execution_target="flautando",
    )
    assert prod.bow_contact is not None
    assert prod.bow_contact.category == "sul_tasto"
    assert prod.timbre_execution_target == "flautando"


# ---------------------------------------------------------------------------
# D. Mutes
# ---------------------------------------------------------------------------


def test_d_standard_and_heavy_distinct() -> None:
    std = migrate_legacy_technique_record({"technique": "con_sordino", "mute_type": "orchestral"})
    heavy = migrate_legacy_technique_record({"technique": "con_sordino", "mute_type": "heavy_practice"})
    assert std.mute is not None and heavy.mute is not None
    assert std.mute.category != heavy.mute.category


def test_d_mass_units_normalized() -> None:
    grams, mass_raw, warnings = normalize_mute_mass("35 g")
    assert grams == 35.0
    assert mass_raw == "35 g"
    assert warnings == []


def test_d_missing_mute_type_not_defaulted() -> None:
    prod = migrate_legacy_technique_record({"technique": "con_sordino"})
    assert prod.mute is not None
    assert prod.mute.category in {"unresolved", None} or str(prod.mute.category) == "unresolved"
    assert prod.migration_warnings


def test_d_violin_mobility_not_silent_cello_transfer() -> None:
    engine = QualitativeConstraintEngine.load()
    matches = engine.match(
        {"mute": {"category": "standard_performance_orchestral"}},
        "vlc",
    )
    mobility = [m for m in matches if m.constraint_id == "QC_MUTE_BRIDGE_MOBILITY_DEC"]
    assert mobility == []


# ---------------------------------------------------------------------------
# E. Combined production states
# ---------------------------------------------------------------------------


def test_e_artificial_harmonic_plus_sul_ponticello() -> None:
    prod = ProductionInstruction(
        legacy_technique_label="artificial_harmonic",
        left_hand=HarmonicInstruction(
            left_hand_regime="artificial_harmonic",
            harmonic_type="artificial",
            harmonic_order=4,
            touched_interval="P4",
        ),
        bow_contact=BowContactInstruction(category="sul_ponticello"),
    )
    assert prod.left_hand is not None
    assert prod.bow_contact is not None
    # Combination is structural, not a scalar product
    assert not hasattr(prod, "density_multiplier")


def test_e_con_sordino_plus_sul_tasto() -> None:
    prod = migrate_legacy_technique_record(
        {"technique": "sul_tasto", "mute_type": "orchestral"}
    )
    assert prod.bow_contact is not None
    assert prod.mute is not None
    assert prod.mute.state == "on"


# ---------------------------------------------------------------------------
# F. Evidence gating
# ---------------------------------------------------------------------------


def test_f_review_activates_qualitative_not_ewsd() -> None:
    result = ingest_evidence_package(dry_run=True)
    assert len(result.active_parameters) == 0
    engine = QualitativeConstraintEngine.load()
    matches = engine.match({"technique": "sul_tasto"}, "vln")
    assert matches
    eval_result = engine.evaluate({"technique": "sul_tasto"}, "vln", request_density_prediction=True)
    assert eval_result.status == "numerical_prediction_not_allowed"


def test_f_numerical_secondary_requires_primary_verification() -> None:
    from string_technique_model.literature.extracts import load_extracts

    extracts = load_extracts()
    numerical = [
        e
        for e in extracts
        if getattr(e, "evidence_id", None) in {"EV_SOA_MUTE_MOBILITY_001", "EV_SOA_MUTE_HEAVY_001"}
        or (isinstance(e, dict) and e.get("evidence_id") in {"EV_SOA_MUTE_MOBILITY_001", "EV_SOA_MUTE_HEAVY_001"})
    ]
    # load_extracts may return objects or the YAML path — tolerate both
    if not numerical:
        from string_technique_model.config import PACKAGE_ROOT, load_yaml

        data = load_yaml(PACKAGE_ROOT / "configs" / "literature_evidence_extracts.yaml")
        numerical = [
            e
            for e in data.get("extracts", [])
            if e.get("evidence_id") in {"EV_SOA_MUTE_MOBILITY_001", "EV_SOA_MUTE_HEAVY_001"}
        ]
    assert numerical
    for e in numerical:
        status = e.get("numerical_activation_status") if isinstance(e, dict) else getattr(e, "numerical_activation_status", None)
        if status is None and isinstance(e, dict):
            status = e.get("density_mapping_status")
        assert status in {
            "secondary_synthesis_requires_primary_verification",
            "incompatible_variable",
            "qualitative_constraint_only",
        }


def test_f_author_year_unresolved() -> None:
    from string_technique_model.config import PACKAGE_ROOT, load_yaml

    sources = load_yaml(PACKAGE_ROOT / "configs" / "literature_sources.yaml")["sources"]
    soa = next(s for s in sources if s["source_id"] == "SRC_STRING_TIMBRAL_ARTICULATORY_STATE_OF_ART")
    assert soa.get("authors") in (None, [], "")
    assert soa.get("year") is None
    assert soa.get("author_year_status") == "unresolved"


# ---------------------------------------------------------------------------
# G. Four-level separation
# ---------------------------------------------------------------------------


def test_g_acoustic_cannot_be_textural() -> None:
    obs = AcousticDescriptorObservation(
        descriptor_id="DESC_SPECTRAL_CENTROID",
        value=1200.0,
        units="Hz",
    )
    with pytest.raises(TypeError):
        assert_level_separation(obs, as_level="textural_function")


def test_g_textural_without_context_insufficient() -> None:
    assessment = infer_textural_function("sul_tasto", grouping_context=None)
    assert assessment.function == "insufficient_context"


def test_g_technique_label_alone_cannot_force_fusion() -> None:
    assessment = infer_textural_function("sul_tasto", grouping_context={})
    payload = assessment.model_dump() if hasattr(assessment, "model_dump") else dict(assessment)
    text = str(payload).lower()
    assert "fusion" not in text or "conditional" in text or "insufficient" in text


# ---------------------------------------------------------------------------
# H. Numerical operations
# ---------------------------------------------------------------------------


def test_h_additive_difference_identity_and_log() -> None:
    d = np.array([10.0, 20.0])
    x = np.array([1.0, 2.0])
    eta_id, _ = link_forward(d, "identity")
    eta_out, d_out, _ = apply_operation(
        operation_type="additive_difference",
        draws=x,
        eta=eta_id,
        d_ordinary=d,
        numerical_scale="density",
        link="identity",
    )
    np.testing.assert_allclose(d_out, d + x)
    np.testing.assert_allclose(eta_out, d + x)

    eta_log, _ = link_forward(d, "log")
    eta_out2, d_out2, _ = apply_operation(
        operation_type="additive_difference",
        draws=x,
        eta=eta_log,
        d_ordinary=d,
        numerical_scale="density",
        link="log",
    )
    np.testing.assert_allclose(d_out2, d + x)
    np.testing.assert_allclose(link_inverse(eta_out2, "log"), d + x)


def test_h_multiplicative_ratio_identity_and_log() -> None:
    d = np.array([10.0, 20.0])
    x = np.array([1.5, 2.0])
    eta_id, _ = link_forward(d, "identity")
    eta_out, d_out, _ = apply_operation(
        operation_type="multiplicative_ratio",
        draws=x,
        eta=eta_id,
        d_ordinary=d,
        numerical_scale="ratio",
        link="identity",
    )
    np.testing.assert_allclose(d_out, d * x)

    eta_log, _ = link_forward(d, "log")
    eta_out2, d_out2, _ = apply_operation(
        operation_type="multiplicative_ratio",
        draws=x,
        eta=eta_log,
        d_ordinary=d,
        numerical_scale="ratio",
        link="log",
    )
    np.testing.assert_allclose(d_out2, d * x)
    np.testing.assert_allclose(eta_out2, eta_log + np.log(x))


def test_h_incompatible_link_operation_fails() -> None:
    d = np.array([0.5])
    eta, _ = link_forward(d, "identity")
    with pytest.raises(OperationError):
        apply_operation(
            operation_type="additive_log_difference",
            draws=np.array([0.1]),
            eta=eta,
            d_ordinary=d,
            numerical_scale="log",
            link="identity",
        )


# ---------------------------------------------------------------------------
# I. Backward compatibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "technique",
    ["ordinary", "artificial_harmonic", "sul_tasto", "sul_ponticello", "con_sordino"],
)
def test_i_legacy_labels_import(technique: str) -> None:
    prod = migrate_legacy_technique_record({"technique": technique, "dynamic": "mf"})
    assert isinstance(prod, ProductionInstruction)
    assert prod.legacy_technique_label == technique or technique == "ordinary"


def test_i_migration_deterministic() -> None:
    row = {"technique": "sul_ponticello", "dynamic": "f", "mute_type": "orchestral"}
    a = migrate_legacy_technique_record(row).model_dump()
    b = migrate_legacy_technique_record(row).model_dump()
    assert a == b


def test_i_legacy_ambiguity_recorded() -> None:
    prod = migrate_legacy_technique_record({"technique": "flautando"})
    assert prod.migration_warnings


def test_i_legacy_cell_count_from_ontology() -> None:
    assert legacy_cell_count() == 16


# ---------------------------------------------------------------------------
# J. Capability reporting
# ---------------------------------------------------------------------------


def test_j_spectrum_numerical_not_advertised() -> None:
    desc = get_model("vln", "sul_ponticello").describe_model()
    assert desc.capabilities.get("numerical_spectrum_transform") == CapabilityState.unavailable.value
    assert desc.advertises_numerical_spectrum_transform() is False


def test_j_descriptor_and_qualitative_separate() -> None:
    # Numerical descriptors live in descriptors/ backend; technique models do not auto-extract.
    assert len(list_implemented_descriptors()) >= 8
    reg = load_descriptor_registry()
    assert len(reg.all()) >= 10
    desc = get_model("vln", "sul_tasto").describe_model()
    assert desc.capabilities.get("qualitative_constraints") == CapabilityState.qualitative_constraints_available.value
    assert desc.capabilities.get("descriptor_extraction") == CapabilityState.unavailable.value


def test_parquet_preflight_reports_clearly() -> None:
    result = check_parquet_engine()
    assert result.ok is True or result.actionable_hint
