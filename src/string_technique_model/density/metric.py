from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from string_technique_model.config import PACKAGE_ROOT, resolve_path


@dataclass(frozen=True)
class DensityMetric:
    name: str
    formula: str
    placeholder: bool
    config: dict[str, Any]

    def phi(self, x: Any) -> Any:
        """Apply the density metric Phi.

        For the located EWSD/CDM scalar pipeline, Phi is the identity on the
        already-computed score. The same function is used for ordinary and
        estimated technique representations.
        """
        if self.placeholder:
            raise RuntimeError(
                "Density metric is a placeholder; scientific prediction is stopped. "
                "Missing information is documented in configs/density_metric.yaml."
            )
        return _identity_phi(x)


def _identity_phi(x: Any) -> Any:
    if x is None:
        return None  # missing-by-design: never coerce to zero
    if isinstance(x, (float, int, np.floating, np.integer)):
        if isinstance(x, (float, np.floating)) and np.isnan(x):
            return np.nan
        return float(x)
    if isinstance(x, np.ndarray):
        return np.asarray(x, dtype=float)
    if isinstance(x, dict):
        # spectrum-aware path: if a precomputed density key exists, use it;
        # otherwise require an explicit scalar 'density' field.
        if "density" in x:
            return _identity_phi(x["density"])
        raise ValueError(
            "Spectrum-aware representation must provide key 'density' for Phi "
            "until a full EWSD recomputation module is linked."
        )
    raise TypeError(f"Unsupported representation for Phi: {type(x)!r}")


def load_density_metric(path: Path | str | None = None) -> DensityMetric:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "density_metric.yaml")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if cfg.get("placeholder") is True or cfg.get("status") == "missing":
        return DensityMetric(
            name=cfg.get("name", "PLACEHOLDER"),
            formula=cfg.get("formula", ""),
            placeholder=True,
            config=cfg,
        )
    return DensityMetric(
        name=str(cfg["name"]),
        formula=str(cfg.get("formula", "")),
        placeholder=False,
        config=cfg,
    )


# Module-level singleton used by tests to prove identity of Phi across techniques
_METRIC = load_density_metric()


def phi(x: Any) -> Any:
    return _METRIC.phi(x)
