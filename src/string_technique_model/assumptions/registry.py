"""Load and validate the user numerical-assumption registry."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from string_technique_model.assumptions.models import UserAssumption, UserAssumptionRegistry
from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

DEFAULT_PATH = PACKAGE_ROOT / "configs" / "user_assumptions.yaml"


def load_user_assumption_registry(path: Path | str | None = None) -> UserAssumptionRegistry:
    data = load_yaml(resolve_path(path or DEFAULT_PATH))
    if data.get("literature_validated") is True:
        raise ValueError("user_assumptions.yaml must not set literature_validated: true")
    return UserAssumptionRegistry.model_validate(data)


@lru_cache(maxsize=4)
def _cached_registry(path_str: str) -> UserAssumptionRegistry:
    return load_user_assumption_registry(path_str)


def get_user_assumption_registry(path: Path | str | None = None) -> UserAssumptionRegistry:
    p = str(resolve_path(path or DEFAULT_PATH).resolve())
    return _cached_registry(p)


def clear_assumption_registry_cache() -> None:
    _cached_registry.cache_clear()


def list_assumptions(
    *,
    instrument: str | None = None,
    technique: str | None = None,
    path: Path | str | None = None,
) -> list[UserAssumption]:
    reg = get_user_assumption_registry(path)
    out: list[UserAssumption] = []
    for a in reg.assumptions:
        if instrument and a.instrument != instrument:
            continue
        if technique and a.technique != technique:
            continue
        out.append(a)
    return out
