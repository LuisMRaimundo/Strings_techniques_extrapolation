"""Build the missing technique × instrument × dynamic × quantity target table."""

from __future__ import annotations

from pathlib import Path

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.extrapolation.models import TargetSpec

DEFAULT_TARGETS = PACKAGE_ROOT / "configs" / "extrapolation" / "target_grid_v1.yaml"


def load_target_grid(path: Path | str | None = None) -> tuple[list[TargetSpec], dict]:
    data = load_yaml(resolve_path(path or DEFAULT_TARGETS))
    instruments = list(data.get("instruments") or [])
    dynamics = list(data.get("dynamics") or [])
    quantities = list(data.get("target_quantities") or [])
    techniques = list(data.get("techniques") or [])
    specs: list[TargetSpec] = []
    for tech in techniques:
        tid = tech["technique_id"]
        mute = tech.get("mute_state")
        transform = tech.get("transformation")
        for inst in instruments:
            for dyn in dynamics:
                for qty in quantities:
                    # Attenuation only meaningful for muted technique in first model
                    if qty == "attenuation_db_power" and tid != "con_sordino":
                        continue
                    specs.append(
                        TargetSpec(
                            instrument=inst,
                            technique=tid,
                            dynamic=dyn,
                            mute_state=mute,
                            transformation=transform,
                            target_quantity=qty,
                        )
                    )
    return specs, data
