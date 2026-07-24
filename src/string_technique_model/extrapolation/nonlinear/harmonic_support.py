"""Support classification and provenance contracts for harmonic calibration."""

from __future__ import annotations

from enum import Enum


class HarmonicSupportClass(str, Enum):
    SAME_INSTRUMENT_SAME_COLLECTION_MEASURED = "same_instrument_same_collection_measured"
    SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED = "same_instrument_cross_collection_measured"
    SAME_INSTRUMENT_DYNAMIC_TRANSFER = "same_instrument_dynamic_transfer"
    SAME_INSTRUMENT_INTERPOLATED = "same_instrument_interpolated"
    CROSS_INSTRUMENT_TRANSFER = "cross_instrument_transfer"
    UNSUPPORTED = "unsupported"


TRANSFER_FORMULA_ORDINARY_RATIO = (
    "H_d2(p) = H_d1(p) * O_d2(p) / O_d1(p)  "
    "[same instrument, collection, note, quantity, SSA/EWSD domain]"
)

DEFAULT_PROCESSING_VERSION = "ssa_ewsd_acoustic_balanced_v1"

# Feature flags — experimental paths stay off unless explicitly enabled.
DEFAULT_ALLOW_INTERPOLATION = False
DEFAULT_ALLOW_CROSS_INSTRUMENT = False
DEFAULT_ALLOW_POOLED_ORDINARY_FALLBACK = False
