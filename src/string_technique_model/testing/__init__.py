"""Acoustics stress-testing utilities (fixtures, oracles, reporting).

Synthetic signals are numerical test fixtures — not perceptually equivalent to
real bowed-string recordings. Literature oracles never invent experimental values.
"""

from string_technique_model.testing.literature_oracles import (
    LiteratureBenchmarkCase,
    load_literature_benchmark_cases,
)
from string_technique_model.testing.reference_cases import WorkedBenchmark, worked_benchmarks
from string_technique_model.testing.signal_generators import SyntheticSignal, generate_signal
from string_technique_model.testing.tolerance_profiles import ToleranceProfile, load_tolerance_profiles

__all__ = [
    "LiteratureBenchmarkCase",
    "SyntheticSignal",
    "ToleranceProfile",
    "WorkedBenchmark",
    "generate_signal",
    "load_literature_benchmark_cases",
    "load_tolerance_profiles",
    "worked_benchmarks",
]
