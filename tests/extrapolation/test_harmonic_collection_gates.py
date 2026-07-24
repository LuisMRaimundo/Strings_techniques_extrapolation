"""Ordinary transfer gates: instrument/collection/domain compatibility."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    OrdinaryAnchor,
    clear_harmonic_calibration_cache,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import HarmonicSupportClass


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_wrong_collection_ordinary_rejected() -> None:
    base = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="A5",
        dynamic="mf",
    )
    assert base.mean is not None
    ordinary = [
        OrdinaryAnchor(
            instrument="vla",
            collection="not_a_real_collection",
            note="A5",
            dynamic="mf",
            value=40.0,
        ),
        OrdinaryAnchor(
            instrument="vla",
            collection="not_a_real_collection",
            note="A5",
            dynamic="pp",
            value=20.0,
        ),
    ]
    res = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="A5",
        dynamic="pp",
        ordinary_rows=ordinary,
    )
    assert res.support_class == HarmonicSupportClass.UNSUPPORTED
    assert res.mean is None


def test_wrong_instrument_ordinary_rejected() -> None:
    ordinary = [
        OrdinaryAnchor(instrument="vln", collection="orchidea", note="A5", dynamic="mf", value=40.0),
        OrdinaryAnchor(instrument="vln", collection="orchidea", note="A5", dynamic="pp", value=20.0),
    ]
    res = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="A5",
        dynamic="pp",
        ordinary_rows=ordinary,
    )
    assert res.mean is None
    assert res.support_class == HarmonicSupportClass.UNSUPPORTED
