"""Artificial-harmonic models (one instance per instrument)."""

from __future__ import annotations

from typing import Any

from string_technique_model.models.base import ModelDescription, TechniqueModel
from string_technique_model.models.capabilities import default_capabilities


class ArtificialHarmonicModel(TechniqueModel):
    technique = "artificial_harmonic"

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
                "Natural vs artificial harmonics remain distinct. "
                "No universal density direction is imposed. "
                "Harmonic order must be explicit when configured. "
                "Spectrum-aware numerical transform is unavailable; "
                "qualitative constraints may apply."
            ),
        )


def build_artificial_harmonic_models(cfg: dict[str, Any]) -> dict[str, ArtificialHarmonicModel]:
    tech = cfg.get("artificial_harmonic") or {}
    out: dict[str, ArtificialHarmonicModel] = {}
    for instrument in ("vln", "vla", "vlc", "cb"):
        out[f"{instrument}/artificial_harmonic"] = ArtificialHarmonicModel(instrument, tech)
    return out
