"""Target descriptor registry and EWSD mapping status."""

from __future__ import annotations

from typing import Any, Literal

LikelihoodFamily = Literal["lognormal", "normal", "gamma", "poisson_proxy", "unavailable"]

# Validated transfer F(D1,...,Dk) → EWSD. Empty until formula is registered and tested.
_EWSD_TRANSFER_FUNCTIONS: dict[str, Any] = {}

DESCRIPTOR_REGISTRY: dict[str, dict[str, Any]] = {
    "EWSD_score_acoustic_balanced": {
        "likelihood_family": "lognormal",
        "unit": "dimensionless_score",
        "baseline_compatible": True,
        # Observed Scalar path: model log-ratio of measured EWSD itself.
        # This is NOT F(descriptors); mark as model_reduction.
        "allows_observed_scalar_log_ratio": True,
    },
    "spectral_centroid": {
        "likelihood_family": "lognormal",
        "unit": "Hz",
        "baseline_compatible": True,
    },
    "spectral_slope_db_per_harmonic": {
        "likelihood_family": "normal",
        "unit": "dB_per_harmonic",
        "baseline_compatible": True,
    },
    "HNR": {
        "likelihood_family": "normal",
        "unit": "dB",
        "baseline_compatible": True,
    },
    "spectral_flux": {
        "likelihood_family": "lognormal",
        "unit": "flux_units",
        "baseline_compatible": True,
    },
    "frame_centroid_variance": {
        "likelihood_family": "lognormal",
        "unit": "Hz2",
        "baseline_compatible": True,
    },
    "upper_partial_energy_ratio": {
        "likelihood_family": "lognormal",
        "unit": "ratio",
        "baseline_compatible": True,
    },
    "brightness_or_upper_spectral_activity_index_20khz": {
        "likelihood_family": "lognormal",
        "unit": "dimensionless_index",
        "baseline_compatible": True,
    },
}


def descriptor_spec(target_quantity: str) -> dict[str, Any] | None:
    return DESCRIPTOR_REGISTRY.get(target_quantity)


def likelihood_family(target_quantity: str) -> LikelihoodFamily:
    spec = descriptor_spec(target_quantity)
    if spec is None:
        return "unavailable"
    return spec["likelihood_family"]


def ewsd_mapping_status(target_quantity: str) -> str:
    """Return mapping status for EWSD / quantity extrapolation."""
    if target_quantity != "EWSD_score_acoustic_balanced":
        if descriptor_spec(target_quantity) is None:
            return "descriptor_not_registered"
        return "descriptor_direct"
    if "EWSD_score_acoustic_balanced" in _EWSD_TRANSFER_FUNCTIONS:
        return "validated_transfer_function_F"
    # Allow empirical log-ratio on measured EWSD with explicit reduction flag
    return "observed_scalar_direct_model"


def mapping_allows_numeric_extrapolation(target_quantity: str) -> bool:
    status = ewsd_mapping_status(target_quantity)
    return status in {
        "validated_transfer_function_F",
        "observed_scalar_direct_model",
        "descriptor_direct",
    }


def ewsd_model_assumptions(target_quantity: str) -> list[str]:
    if target_quantity != "EWSD_score_acoustic_balanced":
        return []
    if ewsd_mapping_status(target_quantity) == "observed_scalar_direct_model":
        return [
            "model_reduction=observed_scalar_direct_model",
            "EWSD treated as measured scalar Y; not reconstructed via validated F(D1..Dk).",
            "Physical mechanism still acts on spectral descriptors first; this is an empirical score model.",
        ]
    return []


def register_ewsd_transfer_function(name: str, fn: Any) -> None:
    """Register a validated F for posterior propagation (future)."""
    _EWSD_TRANSFER_FUNCTIONS[name] = fn
