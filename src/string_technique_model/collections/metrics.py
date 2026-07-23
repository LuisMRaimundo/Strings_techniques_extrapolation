from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.config import load_yaml, resolve_path

COMPATIBILITY_STATUSES = {
    "identical",
    "compatible_after_unit_conversion",
    "compatible_after_declared_transformation",
    "conditionally_comparable",
    "incompatible",
    "unknown",
}

COMPARABILITY_FIELDS = [
    "exact_formula",
    "mathematical_domain",
    "unit",
    "normalisation",
    "frequency_range",
    "temporal_window",
    "amplitude_or_power_convention",
    "thresholding",
    "aggregation_method",
    # Aliases retained for older definition blocks
    "formula_reference",
    "normalisation_id",
    "analysis_window_id",
    "frequency_range_id",
    "amplitude_convention",
    "fft_configuration_id",
    "scale",
]


@dataclass(frozen=True)
class MetricDefinition:
    metric_definition_id: str
    name: str
    version: str
    config: dict[str, Any]

    @property
    def compatible_with(self) -> list[str]:
        return list(self.config.get("compatible_with") or [self.metric_definition_id])


@dataclass
class CompatibilityResult:
    status: str
    reason: str
    source_metric_definition_id: str
    target_metric_definition_id: str
    conversion_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class MetricRegistry:
    def __init__(
        self,
        definitions: dict[str, MetricDefinition],
        conversions: list[dict[str, Any]],
    ) -> None:
        self.definitions = definitions
        self.conversions = conversions

    @classmethod
    def from_paths(
        cls,
        definitions_path: Path | str,
        conversions_path: Path | str,
    ) -> MetricRegistry:
        defs_raw = load_yaml(resolve_path(definitions_path)).get("metric_definitions") or {}
        conversions = load_yaml(resolve_path(conversions_path)).get("conversions") or []
        definitions = {
            mid: MetricDefinition(
                metric_definition_id=mid,
                name=str(cfg.get("name", mid)),
                version=str(cfg.get("version", "")),
                config=cfg,
            )
            for mid, cfg in defs_raw.items()
        }
        return cls(definitions, list(conversions))

    def get(self, metric_definition_id: str) -> MetricDefinition:
        if metric_definition_id not in self.definitions:
            raise KeyError(f"Unknown metric_definition_id: {metric_definition_id}")
        return self.definitions[metric_definition_id]

    def compare(
        self,
        source_metric_definition_id: str,
        target_metric_definition_id: str,
    ) -> CompatibilityResult:
        if source_metric_definition_id == target_metric_definition_id:
            return CompatibilityResult(
                status="identical",
                reason="Same metric_definition_id.",
                source_metric_definition_id=source_metric_definition_id,
                target_metric_definition_id=target_metric_definition_id,
            )

        if (
            source_metric_definition_id not in self.definitions
            or target_metric_definition_id not in self.definitions
        ):
            return CompatibilityResult(
                status="unknown",
                reason="One or both metric definitions are missing from the registry.",
                source_metric_definition_id=source_metric_definition_id,
                target_metric_definition_id=target_metric_definition_id,
            )

        source = self.get(source_metric_definition_id)
        target = self.get(target_metric_definition_id)

        conversion = self._find_conversion(source_metric_definition_id, target_metric_definition_id)
        if conversion is not None:
            status = (
                "compatible_after_unit_conversion"
                if source.config.get("unit") != target.config.get("unit")
                else "compatible_after_declared_transformation"
            )
            return CompatibilityResult(
                status=status,
                reason="Explicit registered conversion available.",
                source_metric_definition_id=source_metric_definition_id,
                target_metric_definition_id=target_metric_definition_id,
                conversion_id=conversion.get("conversion_id"),
                details={"equation": conversion.get("equation")},
            )

        mismatches = []
        for key in COMPARABILITY_FIELDS:
            if source.config.get(key) != target.config.get(key):
                mismatches.append(key)

        if not mismatches and target_metric_definition_id in source.compatible_with:
            return CompatibilityResult(
                status="identical",
                reason="Metric configuration fields match and compatibility list includes target.",
                source_metric_definition_id=source_metric_definition_id,
                target_metric_definition_id=target_metric_definition_id,
            )

        if mismatches and target_metric_definition_id in source.compatible_with:
            return CompatibilityResult(
                status="conditionally_comparable",
                reason="Listed as compatible_with but configuration fields differ: "
                + ", ".join(mismatches),
                source_metric_definition_id=source_metric_definition_id,
                target_metric_definition_id=target_metric_definition_id,
                details={"mismatched_fields": mismatches},
            )

        return CompatibilityResult(
            status="incompatible",
            reason="No identical definition, no registered conversion, and mismatched fields: "
            + (", ".join(mismatches) if mismatches else "compatibility list exclusion"),
            source_metric_definition_id=source_metric_definition_id,
            target_metric_definition_id=target_metric_definition_id,
            details={"mismatched_fields": mismatches},
        )

    def _find_conversion(self, source_id: str, target_id: str) -> dict[str, Any] | None:
        for item in self.conversions:
            if (
                item.get("source_metric_definition_id") == source_id
                and item.get("target_metric_definition_id") == target_id
            ):
                return item
        return None

    def apply_conversion(
        self,
        values: pd.Series,
        source_metric_definition_id: str,
        target_metric_definition_id: str,
    ) -> tuple[pd.Series, CompatibilityResult]:
        result = self.compare(source_metric_definition_id, target_metric_definition_id)
        if result.status == "identical":
            return values.astype(float), result
        if result.status not in {
            "compatible_after_unit_conversion",
            "compatible_after_declared_transformation",
        }:
            raise ValueError(
                f"Cannot convert metrics: status={result.status}; reason={result.reason}"
            )
        conversion = self._find_conversion(source_metric_definition_id, target_metric_definition_id)
        assert conversion is not None
        # Only the declared percent→score transform is implemented generically for now.
        equation = str(conversion.get("equation", ""))
        params = conversion.get("parameters") or {}
        if "source / 100.0" in equation or "/ 100" in equation:
            reference = float((params.get("reference_score") or {}).get("value", 100.0))
            converted = values.astype(float) / 100.0 * reference
            return converted, result
        raise ValueError(
            f"Conversion {conversion.get('conversion_id')} equation is declared but "
            "no executable implementation is registered for it."
        )
