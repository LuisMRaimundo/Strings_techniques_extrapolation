"""Abstract technique model interface with honest capability reporting."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from string_technique_model.models.capabilities import CapabilityState, default_capabilities

# Re-export for callers that imported from base historically.
__all__ = [
    "CapabilityState",
    "ModelDescription",
    "ParameterDraws",
    "ParameterResolutionResult",
    "SpectrumAwareResult",
    "TechniqueModel",
    "default_capabilities",
]


@dataclass
class ModelDescription:
    instrument: str
    technique: str
    backend_support: list[str]
    required_metadata: list[str]
    mechanism_supported: bool
    numerical_parameter_required: bool
    notes: str = ""
    capabilities: dict[str, str] = field(default_factory=dict)

    def advertises_numerical_spectrum_transform(self) -> bool:
        return (
            self.capabilities.get("spectrum_aware")
            == CapabilityState.numerical_transform_available.value
            or self.capabilities.get("numerical_spectrum_transform")
            == CapabilityState.numerical_transform_available.value
        )


@dataclass
class ParameterResolutionResult:
    active: list[dict[str, Any]] = field(default_factory=list)
    inactive: list[dict[str, Any]] = field(default_factory=list)
    conditionally_active: list[dict[str, Any]] = field(default_factory=list)
    not_applicable: list[dict[str, Any]] = field(default_factory=list)
    records: list[Any] = field(default_factory=list)


@dataclass
class ParameterDraws:
    summaries: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class SpectrumAwareResult:
    """Descriptor/constraint result — never fabricates EWSD or transformed audio."""

    status: str
    capabilities: dict[str, str]
    standardized_input_keys: list[str] = field(default_factory=list)
    descriptor_records: list[dict[str, Any]] = field(default_factory=list)
    qualitative_constraint_ids: list[str] = field(default_factory=list)
    ewsd_value: float | None = None
    notes: list[str] = field(default_factory=list)


class TechniqueModel(ABC):
    instrument: str
    technique: str

    def __init__(self, technique_cfg: dict[str, Any] | None = None) -> None:
        self.technique_cfg = technique_cfg or {}

    def required_metadata(self) -> set[str]:
        return set(self.technique_cfg.get("required_metadata") or [])

    def validate_context(
        self,
        baseline_record: dict[str, Any] | None,
        prediction_request: dict[str, Any],
    ) -> Any:
        from string_technique_model.prediction.context import validate_prediction_context

        return validate_prediction_context(
            baseline_record,
            prediction_request,
            required_metadata=self.required_metadata(),
            technique_cfg=self.technique_cfg,
        )

    def resolve_parameters(
        self,
        parameter_registry: list[Any],
        prediction_context: dict[str, Any],
    ) -> ParameterResolutionResult:
        _ = parameter_registry, prediction_context
        return ParameterResolutionResult()

    def sample_parameters(
        self,
        active_parameters: list[dict[str, Any]],
        n_draws: int,
        random_seed: int,
    ) -> ParameterDraws:
        _ = active_parameters, n_draws, random_seed
        return ParameterDraws()

    def predict_metric(
        self,
        baseline_value: dict[str, Any],
        parameter_draws_unused: ParameterDraws,
        prediction_context: dict[str, Any],
        *,
        active_parameters: list[dict[str, Any]],
        link: str,
        n_draws: int,
        random_seed: int,
        transfer_uncertainty_sd: float | None = None,
    ) -> Any:
        from string_technique_model.prediction.uncertainty import propagate_metric_only

        _ = parameter_draws_unused, prediction_context
        return propagate_metric_only(
            baseline=baseline_value,
            active_params=active_parameters,
            link=link,
            n_draws=n_draws,
            random_seed=random_seed,
            transfer_uncertainty_sd=transfer_uncertainty_sd,
        )

    def spectrum_capabilities(self) -> dict[str, str]:
        return default_capabilities(metric_numerical=False)

    def transform_spectrum(
        self,
        ordinary_representation: dict[str, Any] | None,
        parameter_draws: ParameterDraws,
        prediction_context: dict[str, Any],
    ) -> SpectrumAwareResult:
        """Validate spectral input and apply qualitative constraints only.

        Does not fabricate transformed audio or an EWSD value.
        """
        _ = parameter_draws
        caps = self.spectrum_capabilities()
        if ordinary_representation is None:
            raise ValueError("spectrum-aware backend requires ordinary spectral representation")
        keys = {"audio", "fft", "psd", "stft", "partial_amplitudes", "band_energy"}
        present = sorted(keys.intersection(ordinary_representation.keys()))
        if not present:
            raise ValueError(
                "spectrum-aware mode cannot run without spectral input "
                "(audio/fft/psd/stft/partial_amplitudes/band_energy)"
            )

        from string_technique_model.constraints import QualitativeConstraintEngine

        engine = QualitativeConstraintEngine.load()
        instrument = str(prediction_context.get("instrument") or self.instrument)
        matches = engine.match(prediction_context, instrument)
        notes = [
            "numerical_spectrum_transform unavailable",
            "ewsd_formula_unresolved_or_inactive",
            "returning_descriptor_compatible_qualitative_results_only",
        ]
        if caps.get("numerical_spectrum_transform") == CapabilityState.numerical_transform_available.value:
            raise RuntimeError("capability map claims numerical transform but none is implemented")

        return SpectrumAwareResult(
            status="qualitative_constraints_only",
            capabilities=caps,
            standardized_input_keys=present,
            descriptor_records=[],
            qualitative_constraint_ids=[m.constraint_id for m in matches],
            ewsd_value=None,
            notes=notes,
        )

    @abstractmethod
    def describe_model(self) -> ModelDescription:
        ...
