"""Shared fixtures for acoustics stress tests."""

from __future__ import annotations

import pytest

from string_technique_model.testing.literature_oracles import load_literature_benchmark_cases
from string_technique_model.testing.reference_cases import worked_benchmarks
from string_technique_model.testing.tolerance_profiles import load_tolerance_profiles


@pytest.fixture(scope="session")
def tolerance_profiles():
    return load_tolerance_profiles()


@pytest.fixture(scope="session")
def literature_cases():
    return load_literature_benchmark_cases()


@pytest.fixture(scope="session")
def benchmarks():
    return {b.id: b for b in worked_benchmarks()}
