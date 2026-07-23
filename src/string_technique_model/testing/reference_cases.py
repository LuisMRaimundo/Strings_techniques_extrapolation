"""Worked Benchmarks A–J with honest implementation status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

BenchmarkStatus = Literal[
    "implemented",
    "implemented_scope",
    "physics_oracle_only_production_api_absent",
    "descriptor_unimplemented",
    "implemented_with_empty_default_registry",
]


@dataclass(frozen=True)
class WorkedBenchmark:
    id: str
    name: str
    status: BenchmarkStatus
    inputs: dict[str, Any]
    expected: dict[str, Any]
    notes: str


def worked_benchmarks() -> list[WorkedBenchmark]:
    return [
        WorkedBenchmark(
            id="A",
            name="beta_exact",
            status="implemented",
            inputs={"bow_bridge_distance_m": 0.03, "speaking_length_m": 0.60},
            expected={"beta": 0.05},
            notes="production.bow_contact.compute_beta",
        ),
        WorkedBenchmark(
            id="B",
            name="artificial_harmonic_sounding_frequency",
            status="physics_oracle_only_production_api_absent",
            inputs={
                "stopped_frequency_hz": 220.0,
                "touch_interval": "perfect_fourth",
                "harmonic_order": 4,
            },
            expected={"physics_sounding_frequency_hz": 880.0, "production_auto_compute": False},
            notes="f_n = n * f_0 analytical identity; ProductionInstruction does not auto-fill sounding Hz",
        ),
        WorkedBenchmark(
            id="C",
            name="interval_order_contradiction",
            status="implemented",
            inputs={"touch_interval": "perfect_fifth", "harmonic_order": 4},
            expected={"validation_ok": False},
            notes="P5 maps to order 3; order 4 contradicts",
        ),
        WorkedBenchmark(
            id="D",
            name="spectral_centroid_sine",
            status="implemented",
            inputs={"kind": "pure_sine", "frequency_hz": 1000.0},
            expected={"centroid_hz_approx": 1000.0, "implemented": True},
            notes="DESC_SPECTRAL_CENTROID; tolerance from FFT-bin resolution",
        ),
        WorkedBenchmark(
            id="E",
            name="spectral_centroid_two_tone",
            status="implemented",
            inputs={"frequencies_hz": [500.0, 1500.0], "equal_weight": True},
            expected={"centroid_hz_approx": 1000.0, "implemented": True},
            notes="Equal-amplitude two-tone under explicit power weighting",
        ),
        WorkedBenchmark(
            id="F",
            name="hnr_monotonicity",
            status="implemented",
            inputs={"noise_levels": [0.0, 0.05, 0.2, 0.5]},
            expected={"implemented": True, "monotonic_decrease": True},
            notes="DESC_HNR spectral-mask definition; monotonic with noise",
        ),
        WorkedBenchmark(
            id="G",
            name="mute_categories_distinct",
            status="implemented_scope",
            inputs={"categories": ["performance_mute", "light_practice", "heavy_practice"]},
            expected={"distinct": True, "no_mass_attenuation_law": True},
            notes="MuteCategory literals + Evangelista scope extracts",
        ),
        WorkedBenchmark(
            id="H",
            name="measurement_domain_mismatch",
            status="implemented_scope",
            inputs={"domains": ["radiated_audio", "bridge_force"]},
            expected={"comparable": False},
            notes="measurement_domains registry non-equivalence",
        ),
        WorkedBenchmark(
            id="I",
            name="evidence_only_ewsd_na",
            status="implemented",
            inputs={"mode": "evidence_only"},
            expected={"active_density_parameters": 0},
            notes="No validated EWSD technique mapping activated",
        ),
        WorkedBenchmark(
            id="J",
            name="user_assumption_mode",
            status="implemented_with_empty_default_registry",
            inputs={"mode": "evidence_plus_user_assumptions"},
            expected={"default_registry_active_count": 0, "label_if_used": "assumption_based"},
            notes="Dual gate; empty default assumptions list",
        ),
    ]
