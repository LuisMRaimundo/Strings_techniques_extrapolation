"""Shared assertions for descriptor stress tests."""

from __future__ import annotations

from string_technique_model.descriptors.models import DescriptorResult

REQUIRED_RESULT_FIELDS = (
    "descriptor_id",
    "value",
    "unit",
    "measurement_domain",
    "sample_rate",
    "fft_size",
    "window_type",
    "hop_size",
    "frequency_limits",
    "amplitude_power_convention",
    "normalization",
    "temporal_aggregation",
    "silence_policy",
    "implementation_version",
)


def assert_provenance(result: DescriptorResult) -> None:
    for field in REQUIRED_RESULT_FIELDS:
        assert getattr(result, field) is not None, f"missing {field}"
    assert result.method_id
    assert result.profile_id
    assert isinstance(result.frequency_limits, tuple)
    assert len(result.frequency_limits) == 2
