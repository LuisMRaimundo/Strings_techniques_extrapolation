"""Nonlinear hierarchical acoustic extrapolation (Phase 1)."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.baseline import fit_baseline, fit_ordinary_baseline
from string_technique_model.extrapolation.nonlinear.bayesian_backend import BayesianBackendStatus, check_backend
from string_technique_model.extrapolation.nonlinear.comparison import compare_models
from string_technique_model.extrapolation.nonlinear.export_nonlinear import export_nonlinear_workbook
from string_technique_model.extrapolation.nonlinear.model_selection import (
    assess_data_availability,
    select_model,
    select_register_model,
)
from string_technique_model.extrapolation.nonlinear.harmonic_register import generate_harmonic_targets
from string_technique_model.extrapolation.nonlinear.prediction import fit_technique_effect, predict_register

__all__ = [
    "BayesianBackendStatus",
    "assess_data_availability",
    "check_backend",
    "compare_models",
    "export_nonlinear_workbook",
    "fit_baseline",
    "fit_ordinary_baseline",
    "fit_technique_effect",
    "generate_harmonic_targets",
    "predict_register",
    "select_model",
    "select_register_model",
]
