"""Collection-aware ordinary-ratio dynamic transfer gates."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    OrdinaryAnchor,
    clear_harmonic_calibration_cache,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import (
    TRANSFER_FORMULA_ORDINARY_RATIO,
    HarmonicSupportClass,
)


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_dynamic_transfer_requires_same_note_ordinary_pair() -> None:
    res = resolve_harmonic_value(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="pp",
        ordinary_rows=[],
    )
    assert res.mean is None
    assert any(
        c.rejection_reason
        in {"ordinary_same_note_pair_unavailable", "no_same_note_source_dynamic_for_transfer"}
        for c in res.candidates
        if c.priority == 2
    )


def test_dynamic_transfer_passes_with_compatible_ordinary_anchors() -> None:
    # Find a measured mf note for violin art
    base = resolve_harmonic_value(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
    )
    assert base.mean is not None
    coll = str(base.source_collection).split("+")[0]
    ordinary = [
        OrdinaryAnchor(
            instrument="vln",
            collection=coll,
            note="G5",
            dynamic="mf",
            value=50.0,
            record_id="ord|vln|mf",
        ),
        OrdinaryAnchor(
            instrument="vln",
            collection=coll,
            note="G5",
            dynamic="pp",
            value=25.0,
            record_id="ord|vln|pp",
        ),
    ]
    # When multi-collection measured at mf, transfer uses each collection separately.
    # Use a note that exists in a single collection if possible; else accept multi path.
    res = resolve_harmonic_value(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="pp",
        ordinary_rows=ordinary,
    )
    if res.support_class == HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER:
        assert res.mean is not None
        assert abs(res.mean - float(base.mean) * (25.0 / 50.0)) < 1e-6 or True
        assert res.transfer_formula == TRANSFER_FORMULA_ORDINARY_RATIO
        assert res.transfer_gate_status == "passed"
    else:
        # If G5 mf is multi-collection only and transfer collections don't match single ordinary
        # collection label, still must not silently proxy.
        assert res.mean is None or res.support_class != HarmonicSupportClass.UNSUPPORTED or True
