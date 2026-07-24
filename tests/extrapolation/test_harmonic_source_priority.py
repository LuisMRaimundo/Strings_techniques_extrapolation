"""Priority ladder ordering for harmonic source selection."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import HarmonicSupportClass


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_exact_measured_outranks_transfer_and_interpolation() -> None:
    res = resolve_harmonic_value(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
        allow_interpolation=True,
    )
    assert res.mean is not None
    assert res.support_class in {
        HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED,
        HarmonicSupportClass.SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED,
    }
    # Accepted priority must be measured (1 or 3), never interpolation/transfer.
    accepted = [c for c in res.candidates if c.accepted]
    assert accepted
    assert accepted[0].priority in {1, 3}
    assert accepted[0].support_class != HarmonicSupportClass.SAME_INSTRUMENT_INTERPOLATED.value


def test_interpolation_disabled_by_default() -> None:
    res = resolve_harmonic_value(
        instrument="vln",
        technique="artificial_harmonic",
        note="C8",
        dynamic="mf",
    )
    assert any(
        c.priority == 4 and c.rejection_reason == "interpolation_disabled" for c in res.candidates
    )


def test_candidates_include_full_ladder_on_miss() -> None:
    res = resolve_harmonic_value(
        instrument="vlc",
        technique="natural_harmonic",
        note="C3",
        dynamic="ff",
    )
    priorities = {c.priority for c in res.candidates}
    assert {5, 6}.issubset(priorities)
