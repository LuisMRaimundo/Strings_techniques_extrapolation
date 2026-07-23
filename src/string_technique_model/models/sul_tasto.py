"""Sul-tasto models (one instance per instrument)."""

from __future__ import annotations

from typing import Any

from string_technique_model.models.base import ModelDescription, TechniqueModel
from string_technique_model.models.capabilities import default_capabilities


class SulTastoModel(TechniqueModel):
    technique = "sul_tasto"

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
                "Sul tasto and flautando remain distinct unless a source equates them. "
                "No universal density decrease is imposed. "
                "Operative geometric variable is relative_bow_bridge_distance_beta. "
                "Spectrum numerical transform unavailable."
            ),
        )


def build_sul_tasto_models(cfg: dict[str, Any]) -> dict[str, SulTastoModel]:
    tech = cfg.get("sul_tasto") or {}
    out: dict[str, SulTastoModel] = {}
    for instrument in ("vln", "vla", "vlc", "cb"):
        out[f"{instrument}/sul_tasto"] = SulTastoModel(instrument, tech)
    return out
