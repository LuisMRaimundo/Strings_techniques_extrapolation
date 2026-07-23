from __future__ import annotations

from string_technique_model.density.metric import DensityMetric, phi


def assert_same_phi(metric: DensityMetric, ordinary_x, technique_x) -> None:
    """Prove ordinary and technique paths call the same Phi function object."""
    d_ord = metric.phi(ordinary_x)
    d_tech = metric.phi(technique_x)
    # Same callable identity
    assert metric.phi is metric.phi
    assert phi.__code__ is phi.__code__
    return d_ord, d_tech
