"""Sul-ponticello models (one instance per instrument)."""

from __future__ import annotations

from typing import Any

from string_technique_model.models.base import ModelDescription, TechniqueModel
from string_technique_model.models.capabilities import default_capabilities


class SulPonticelloModel(TechniqueModel):
    technique = "sul_ponticello"

    def __init__(self, instrument: str, technique_cfg: dict[str, Any] | None = None) -> None:
        super().__init__(technique_cfg)
        self.instrument = instrument

    def describe_model(self) -> ModelDescription:
        return ModelDescription(
            instrument=self.instrument,
            technique=self.technique,
            backend_support=["metric-only", "spectrum-aware"],
            required_metadata=sorted(self.required_metadata()),
            mechanism_supported=True,
            numerical_parameter_required=True,
            capabilities=default_capabilities(metric_numerical=False),
            notes=(
                "Distinguish poco/sul/molto sul ponticello from on-bridge and afterlength. "
                "No universal density increase. Multiple-slip regimes are distinct from "
                "stable bridge-oriented Helmholtz motion. Spectrum numerical transform unavailable."
            ),
        )


def build_sul_ponticello_models(cfg: dict[str, Any]) -> dict[str, SulPonticelloModel]:
    tech = cfg.get("sul_ponticello") or {}
    out: dict[str, SulPonticelloModel] = {}
    for instrument in ("vln", "vla", "vlc", "cb"):
        out[f"{instrument}/sul_ponticello"] = SulPonticelloModel(instrument, tech)
    return out
