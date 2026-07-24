"""Compatibility facade over the harmonic source-priority resolver.

New code should import ``harmonic_source_resolver`` directly. This module keeps
the previous function names used by ``harmonic_model`` / tests while enforcing
instrument isolation and disabling silent cross-instrument use.
"""

from __future__ import annotations

from typing import Any

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    OrdinaryAnchor,
    clear_harmonic_calibration_cache,
    has_calibrated_harmonic_coverage,
    load_raw_harmonic_calibration_table,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import (
    DEFAULT_ALLOW_CROSS_INSTRUMENT,
    DEFAULT_ALLOW_INTERPOLATION,
)


def clear_calibrated_harmonic_table_cache() -> None:
    clear_harmonic_calibration_cache()


def load_calibrated_harmonic_table(measured_dir: str | None = None):
    """Legacy helper: unique instrument×technique×dynamic×note means (multi-collection averaged)."""
    import pandas as pd

    raw = load_raw_harmonic_calibration_table(measured_dir)
    if raw.empty:
        return raw
    return (
        raw.groupby(["instrument", "technique", "dynamic", "note"], as_index=False)
        .agg(value=("value", "mean"), collection=("collection", lambda s: "+".join(sorted(set(s)))))
    )


def lookup_calibrated_harmonic(
    *,
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
    ordinary_by_dynamic: dict[str, float] | None = None,
    ordinary_rows: list[OrdinaryAnchor] | dict[str, Any] | None = None,
    measured_dir: str | None = None,
    allow_interpolation: bool = DEFAULT_ALLOW_INTERPOLATION,
    allow_cross_instrument: bool = DEFAULT_ALLOW_CROSS_INSTRUMENT,
) -> dict[str, Any] | None:
    """Resolve via priority ladder.

    ``ordinary_by_dynamic`` (GUI register mean) is **ignored** for transfer — it
    fails collection/same-note gates by design. Pass ``ordinary_rows`` with
    instrument+collection+note+dynamic anchors instead.
    """
    del ordinary_by_dynamic  # intentionally unused (pooled GUI mean forbidden)
    anchors: list[OrdinaryAnchor] | None
    if ordinary_rows is None:
        anchors = None
    elif ordinary_rows and isinstance(ordinary_rows[0], OrdinaryAnchor):
        anchors = list(ordinary_rows)  # type: ignore[arg-type]
    else:
        anchors = [
            OrdinaryAnchor(**o) if isinstance(o, dict) else o  # type: ignore[arg-type]
            for o in ordinary_rows  # type: ignore[union-attr]
        ]

    resolution = resolve_harmonic_value(
        instrument=instrument,
        technique=technique,
        note=note,
        dynamic=dynamic,
        ordinary_rows=anchors,
        measured_dir=measured_dir,
        allow_interpolation=allow_interpolation,
        allow_cross_instrument=allow_cross_instrument,
    )
    if resolution.mean is None:
        return None
    return {
        "mean": resolution.mean,
        "sd": resolution.sd,
        "source_dynamic": resolution.source_dynamic,
        "source_note": resolution.source_note,
        "requested_note": resolution.target_note,
        "transfer": resolution.transfer_method,
        "collection": resolution.source_collection,
        "measured_or_extrapolated": resolution.measured_or_extrapolated,
        "support_class": resolution.support_class.value,
        "resolution": resolution.to_dict(),
    }
