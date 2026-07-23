"""Empirical ordinary baseline via log-linear penalized B-splines on MIDI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.extrapolation.baselines import normalize_instrument
from string_technique_model.extrapolation.nonlinear.domain import BaselineModelSpec
from string_technique_model.extrapolation.nonlinear.splines import (
    fit_penalized_bspline,
    predict_bspline,
    second_difference_penalty_matrix,
)

DYNAMIC_ORDER: tuple[str, ...] = ("ppp", "pp", "mp", "mf", "f", "ff", "fff")

_ORDINARY_TECHNIQUES = frozenset({"ordinary", "ordinario", "arco", "arco_normal"})


def dynamic_sort_key(dynamic: str) -> tuple[int, str]:
    """Ordinal categorical ordering; dynamics are NOT spaced numerically."""
    d = str(dynamic).strip().lower()
    try:
        return (DYNAMIC_ORDER.index(d), d)
    except ValueError:
        return (len(DYNAMIC_ORDER), d)


@dataclass
class BaselineFit:
    instrument: str
    dynamic: str
    quantity: str
    intercept: float
    spline_coeffs: np.ndarray
    knots: np.ndarray
    degree: int
    penalty: float
    midi_min: float
    midi_max: float
    residual_sd: float
    record_ids: list[str] = field(default_factory=list)
    n_observations: int = 0

    def predict(self, midi: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(mean_on_original_scale, outside_baseline_range)``."""
        midi_arr = np.asarray(midi, dtype=float).ravel()
        log_spline, outside = predict_bspline(
            midi_arr,
            self.knots,
            self.degree,
            self.spline_coeffs,
            x_min=self.midi_min,
            x_max=self.midi_max,
        )
        log_mean = self.intercept + log_spline
        return np.exp(log_mean), outside


@dataclass
class BaselineFitCollection:
    fits: dict[tuple[str, str], BaselineFit]
    quantity: str
    spec: BaselineModelSpec

    def get(self, instrument: str, dynamic: str) -> BaselineFit | None:
        inst = normalize_instrument(instrument)
        dyn = str(dynamic).strip().lower()
        return self.fits.get((inst, dyn))


def _record_id(row: pd.Series, idx: int) -> str:
    src = row.get("source_path")
    note = row.get("note")
    if src and note:
        return f"{src}::{note}::{idx}"
    return f"row_{idx}"


def fit_ordinary_baseline(
    df: pd.DataFrame,
    *,
    spec: BaselineModelSpec | None = None,
) -> BaselineFitCollection:
    """Fit log B = intercept + penalized spline(midi) per instrument × dynamic."""
    spec = spec or BaselineModelSpec()
    required = {"instrument", "dynamic", "midi", "value", "quantity"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"baseline dataframe missing columns: {sorted(missing)}")

    work = df.copy()
    if "technique" in work.columns:
        work = work[work["technique"].astype(str).str.lower().isin(_ORDINARY_TECHNIQUES)]
    work = work.dropna(subset=["midi", "value"])
    work["instrument"] = work["instrument"].map(normalize_instrument)
    work["dynamic"] = work["dynamic"].astype(str).str.lower()
    work = work[work["quantity"].astype(str) == spec.quantity]

    fits: dict[tuple[str, str], BaselineFit] = {}
    for (inst, dyn), group in work.groupby(["instrument", "dynamic"], sort=False):
        group = group.sort_values("midi")
        if len(group) < 2:
            continue
        x = group["midi"].to_numpy(dtype=float)
        y_raw = group["value"].to_numpy(dtype=float)
        if np.any(y_raw <= 0):
            raise ValueError(f"non-positive baseline values for {inst}/{dyn}")
        y = np.log(y_raw)
        fit = fit_penalized_bspline(
            x,
            y,
            degree=spec.spline_degree,
            n_basis=spec.n_basis,
            lam=spec.penalty_lambda,
        )
        # Intercept + penalized spline with zero penalty on intercept
        design = fit.design
        n_spline = design.shape[1]
        penalty = second_difference_penalty_matrix(n_spline)
        aug_design = np.column_stack([np.ones(len(x)), design])
        aug_penalty = np.zeros((n_spline + 1, n_spline + 1))
        aug_penalty[1:, 1:] = penalty
        lhs = aug_design.T @ aug_design + spec.penalty_lambda * aug_penalty
        rhs = aug_design.T @ y
        beta = np.linalg.solve(lhs, rhs)
        intercept = float(beta[0])
        spline_coeffs = beta[1:]
        fitted_log = aug_design @ beta
        resid = y - fitted_log
        dof = max(1, len(y) - n_spline - 1)
        residual_sd = float(np.sqrt(np.sum(resid**2) / dof))
        record_ids = [_record_id(row, idx) for idx, (_, row) in enumerate(group.iterrows())]
        fits[(str(inst), str(dyn))] = BaselineFit(
            instrument=str(inst),
            dynamic=str(dyn),
            quantity=spec.quantity,
            intercept=intercept,
            spline_coeffs=spline_coeffs,
            knots=fit.knots,
            degree=fit.degree,
            penalty=spec.penalty_lambda,
            midi_min=fit.x_min,
            midi_max=fit.x_max,
            residual_sd=residual_sd,
            record_ids=record_ids,
            n_observations=len(group),
        )

    return BaselineFitCollection(fits=fits, quantity=spec.quantity, spec=spec)


def fit_baseline(df: pd.DataFrame, **kwargs: Any) -> BaselineFitCollection:
    """Public alias for :func:`fit_ordinary_baseline`."""
    return fit_ordinary_baseline(df, **kwargs)
