"""Con-sordino models (one instance per instrument)."""

from __future__ import annotations

from typing import Any

from string_technique_model.models.base import ModelDescription, TechniqueModel
from string_technique_model.models.capabilities import default_capabilities


class ConSordinoModel(TechniqueModel):
    technique = "con_sordino"

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
                "Standard performance and heavy practice mutes remain distinct. "
                "Mute acts as added bridge mass / mobility / transmission filter, "
                "not merely absorbing overtones. No constant density multiplier. "
                "Spectrum numerical transform unavailable."
            ),
        )


def build_con_sordino_models(cfg: dict[str, Any]) -> dict[str, ConSordinoModel]:
    tech = cfg.get("con_sordino") or {}
    out: dict[str, ConSordinoModel] = {}
    for instrument in ("vln", "vla", "vlc", "cb"):
        out[f"{instrument}/con_sordino"] = ConSordinoModel(instrument, tech)
    return out
