"""Registry of instrument–technique model instances (legacy specialised set)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml
from string_technique_model.models.artificial_harmonic import build_artificial_harmonic_models
from string_technique_model.models.base import TechniqueModel
from string_technique_model.models.con_sordino import build_con_sordino_models
from string_technique_model.models.sul_ponticello import build_sul_ponticello_models
from string_technique_model.models.sul_tasto import build_sul_tasto_models
from string_technique_model.ontology import legacy_cell_count


def load_technique_model_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or PACKAGE_ROOT / "configs" / "technique_models.yaml")


@lru_cache(maxsize=1)
def _registry() -> dict[str, TechniqueModel]:
    cfg = load_technique_model_config()
    models: dict[str, TechniqueModel] = {}
    models.update(build_artificial_harmonic_models(cfg))
    models.update(build_sul_ponticello_models(cfg))
    models.update(build_sul_tasto_models(cfg))
    models.update(build_con_sordino_models(cfg))
    expected = legacy_cell_count()
    if len(models) != expected:
        raise RuntimeError(
            f"Expected {expected} legacy model configurations from ontology, got {len(models)}"
        )
    return models


def get_model(instrument: str, technique: str) -> TechniqueModel:
    key = f"{instrument}/{technique}"
    reg = _registry()
    if key not in reg:
        raise KeyError(f"No model for {key}")
    return reg[key]


def list_model_keys() -> list[str]:
    return sorted(_registry().keys())


def clear_registry_cache() -> None:
    _registry.cache_clear()
