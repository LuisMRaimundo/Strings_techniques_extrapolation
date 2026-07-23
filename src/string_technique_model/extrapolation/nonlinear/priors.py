"""Load weakly informative priors for nonlinear extrapolation.

Expected YAML layout (also written to ``configs/extrapolation_priors.yaml``)::

    version: "1.0.0"
    priors:
      - prior_id: alpha_t_sul_tasto
        parameter: alpha_t
        family: normal
        mean: -0.15
        sd: 0.45
        activation_status: active
        source: literature_direction_sul_tasto
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.nonlinear.domain import PriorSpec

DEFAULT_PRIORS_PATH = PACKAGE_ROOT / "configs" / "extrapolation_priors.yaml"


def load_priors(path: Path | str | None = None) -> list[PriorSpec]:
    """Load prior specifications from YAML."""
    data = load_yaml(resolve_path(path or DEFAULT_PRIORS_PATH))
    priors: list[PriorSpec] = []
    for raw in data.get("priors") or []:
        if not isinstance(raw, dict):
            continue
        priors.append(PriorSpec.model_validate(raw))
    return priors


def priors_by_id(path: Path | str | None = None) -> dict[str, PriorSpec]:
    return {p.prior_id: p for p in load_priors(path)}


def active_priors(path: Path | str | None = None) -> list[PriorSpec]:
    return [p for p in load_priors(path) if p.activation_status == "active"]


def get_prior(prior_id: str, *, path: Path | str | None = None) -> PriorSpec | None:
    return priors_by_id(path).get(prior_id)


def prior_parameters(cfg: dict[str, Any] | None = None) -> dict[str, PriorSpec]:
    if cfg is None:
        return priors_by_id()
    out: dict[str, PriorSpec] = {}
    for raw in cfg.get("priors") or []:
        spec = PriorSpec.model_validate(raw)
        out[spec.prior_id] = spec
    return out
