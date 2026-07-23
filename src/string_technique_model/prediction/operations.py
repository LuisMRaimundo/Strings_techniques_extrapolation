"""Explicit operation-type dispatch with declared source/target spaces.

Ledger ``operation_type`` is authoritative. Link and operation spaces must not
share mathematically invalid shortcuts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from string_technique_model.literature.scales import assert_not_db_density

LOG_COMPATIBLE_LINKS = frozenset({"log"})
IDENTITY_COMPATIBLE_LINKS = frozenset({"identity", "log", "logit", "probit"})


class OperationError(ValueError):
    pass


@dataclass(frozen=True)
class OperationSpec:
    operation_type: str
    source_space: str  # density | link | log_density | forbidden
    target_space: str
    compatible_links: frozenset[str]
    input_unit: str
    transformation_equation: str


OPERATION_SPECS: dict[str, OperationSpec] = {
    "multiplicative_ratio": OperationSpec(
        operation_type="multiplicative_ratio",
        source_space="density",
        target_space="density",
        compatible_links=frozenset({"identity", "log", "logit", "probit"}),
        input_unit="dimensionless_ratio",
        transformation_equation="D' = D * x; eta' = link(D')",
    ),
    "additive_difference": OperationSpec(
        operation_type="additive_difference",
        source_space="density",
        target_space="density",
        compatible_links=frozenset({"identity", "log", "logit", "probit"}),
        input_unit="density_units",
        transformation_equation="D' = D + x; eta' = link(D')",
    ),
    "additive_log_difference": OperationSpec(
        operation_type="additive_log_difference",
        source_space="log_density",
        target_space="log_density",
        compatible_links=frozenset({"log"}),
        input_unit="nat_log_density_difference",
        transformation_equation="eta' = eta + x where eta = log(D); D' = exp(eta')",
    ),
    "decibel_amplitude_gain": OperationSpec(
        operation_type="decibel_amplitude_gain",
        source_space="forbidden",
        target_space="forbidden",
        compatible_links=frozenset(),
        input_unit="dB_amplitude",
        transformation_equation="not a density effect without approved mapping",
    ),
    "decibel_power_gain": OperationSpec(
        operation_type="decibel_power_gain",
        source_space="forbidden",
        target_space="forbidden",
        compatible_links=frozenset(),
        input_unit="dB_power",
        transformation_equation="not a density effect without approved mapping",
    ),
    "decibel_gain": OperationSpec(
        operation_type="decibel_gain",
        source_space="forbidden",
        target_space="forbidden",
        compatible_links=frozenset(),
        input_unit="dB_unspecified",
        transformation_equation="ambiguous dB convention; not a density effect",
    ),
}


def amplitude_ratio_from_db(db: np.ndarray | float) -> np.ndarray:
    return np.asarray(10.0 ** (np.asarray(db, dtype=float) / 20.0), dtype=float)


def power_ratio_from_db(db: np.ndarray | float) -> np.ndarray:
    return np.asarray(10.0 ** (np.asarray(db, dtype=float) / 10.0), dtype=float)


def get_operation_spec(operation_type: str) -> OperationSpec | None:
    return OPERATION_SPECS.get(str(operation_type))


def apply_operation(
    *,
    operation_type: str,
    draws: np.ndarray,
    eta: np.ndarray,
    d_ordinary: np.ndarray,
    numerical_scale: str | None,
    link: str,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Apply an operation with explicit link compatibility.

    Returns:
        (eta_out, d_out, space) where space is 'eta' when eta_out is authoritative
        for the subsequent inverse-link step, or 'density' when d_out must be
        re-linked by the caller.
    """
    from string_technique_model.prediction.links import link_forward

    op = str(operation_type)
    x = np.asarray(draws, dtype=float)
    d = np.asarray(d_ordinary, dtype=float)
    eta_arr = np.asarray(eta, dtype=float)
    link_name = str(link)

    if op == "multiplicative_ratio":
        if np.any(x <= 0):
            raise OperationError("multiplicative_ratio draws must be positive")
        d_out = d * x
        if link_name == "log":
            # Equivalent and numerically stable in log-density space.
            return eta_arr + np.log(x), d_out, "eta"
        if link_name not in IDENTITY_COMPATIBLE_LINKS:
            raise OperationError(f"multiplicative_ratio incompatible with link={link_name}")
        eta_out, _ = link_forward(d_out, link_name)
        return eta_out, d_out, "eta"

    if op == "additive_difference":
        # Must apply in density space, then transform through the selected link.
        d_out = d + x
        if link_name not in IDENTITY_COMPATIBLE_LINKS:
            raise OperationError(f"additive_difference incompatible with link={link_name}")
        eta_out, _ = link_forward(d_out, link_name)
        return eta_out, d_out, "eta"

    if op == "additive_log_difference":
        if link_name not in LOG_COMPATIBLE_LINKS:
            raise OperationError(
                "additive_log_difference requires a log-compatible link "
                f"(got {link_name!r})"
            )
        eta_out = eta_arr + x
        d_out = np.exp(eta_out)
        return eta_out, d_out, "eta"

    if op in {"decibel_amplitude_gain", "decibel_power_gain", "decibel_gain"}:
        scale = numerical_scale or (
            "amplitude_decibel" if "amplitude" in op else "decibel_power"
        )
        try:
            assert_not_db_density(scale, context=op)
        except ValueError as exc:
            raise OperationError(str(exc)) from exc
        raise OperationError(f"{op} is not a density effect without approved mapping")

    if op in {"frequency_dependent_transfer", "spectral_slope_change"}:
        raise OperationError(f"{op} requires spectrum-aware numerical_transform_available")

    if op in {
        "validity_bound",
        "temporal_constant",
        "probability_parameter",
        "categorical_constraint",
    }:
        raise OperationError(f"{op} cannot create a direct density coefficient")

    raise OperationError(f"Unsupported or inactive operation_type: {op}")


def is_density_transform_operation(operation_type: str) -> bool:
    return operation_type in {
        "multiplicative_ratio",
        "additive_difference",
        "additive_log_difference",
    }


def describe_operation(operation_type: str) -> dict[str, Any]:
    spec = get_operation_spec(operation_type)
    if spec is None:
        return {"operation_type": operation_type, "status": "unsupported"}
    return {
        "operation_type": spec.operation_type,
        "source_space": spec.source_space,
        "target_space": spec.target_space,
        "compatible_links": sorted(spec.compatible_links),
        "input_unit": spec.input_unit,
        "transformation_equation": spec.transformation_equation,
    }
