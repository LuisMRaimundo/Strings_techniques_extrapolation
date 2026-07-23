"""Link-function registry for metric-only technique transformation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from string_technique_model.config import PACKAGE_ROOT, load_yaml


@dataclass(frozen=True)
class LinkApplication:
    name: str
    numerical_safeguard_applied: bool
    safeguard_note: str | None = None


def load_link_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or PACKAGE_ROOT / "configs" / "model_links.yaml")


def select_link(
    metric_definition_id: str | None,
    *,
    mathematical_domain: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    cfg = config or load_link_config()
    rules = cfg.get("selection_rules") or {}
    if metric_definition_id and metric_definition_id in rules:
        return str(rules[metric_definition_id])
    domain = (mathematical_domain or "").lower()
    if "unit" in domain or domain in {"(0,1)", "unit_interval"}:
        return "logit"
    if "positive" in domain:
        return "log"
    # EWSD default from config
    return str(rules.get("ewsd_v1") or "log")


def link_forward(
    values: np.ndarray | float,
    link: str,
    *,
    config: dict[str, Any] | None = None,
) -> tuple[np.ndarray, LinkApplication]:
    cfg = config or load_link_config()
    link_cfg = (cfg.get("links") or {}).get(link) or {}
    x = np.asarray(values, dtype=float)
    safeguard = False
    note = None

    if link == "identity":
        return x, LinkApplication(link, False)
    if link == "log":
        floor = float(link_cfg.get("numerical_floor") or 1e-12)
        if np.any(~np.isfinite(x)) or np.any(x <= 0):
            raise ValueError("log link requires finite positive density values")
        if np.any(x < floor):
            x = np.maximum(x, floor)
            safeguard = True
            note = f"applied numerical_floor={floor} before log"
        return np.log(x), LinkApplication(link, safeguard, note)
    if link == "logit":
        eps = float(link_cfg.get("numerical_eps") or 1e-9)
        if np.any(x <= 0) or np.any(x >= 1):
            x = np.clip(x, eps, 1.0 - eps)
            safeguard = True
            note = f"logit clip to ({eps}, {1-eps})"
        return np.log(x / (1.0 - x)), LinkApplication(link, safeguard, note)
    if link == "probit":
        if not link_cfg.get("enabled", False):
            raise ValueError("probit link is disabled in model_links.yaml")
        from scipy.stats import norm  # optional

        eps = float(link_cfg.get("numerical_eps") or 1e-9)
        x = np.clip(x, eps, 1.0 - eps)
        return norm.ppf(x), LinkApplication(link, True, "probit clip")
    raise ValueError(f"Unsupported link function: {link}")


def link_inverse(
    eta: np.ndarray | float,
    link: str,
    *,
    config: dict[str, Any] | None = None,
) -> np.ndarray:
    cfg = config or load_link_config()
    _ = cfg
    z = np.asarray(eta, dtype=float)
    if link == "identity":
        return z
    if link == "log":
        return np.exp(z)
    if link == "logit":
        return 1.0 / (1.0 + np.exp(-z))
    if link == "probit":
        from scipy.stats import norm

        return norm.cdf(z)
    raise ValueError(f"Unsupported link function: {link}")
