"""Shared STFT / spectrum utilities for descriptor implementations."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.descriptors.models import AnalysisProfile, Weighting


class SpectrumError(ValueError):
    """Invalid spectral input."""


def validate_audio(x: np.ndarray, sample_rate: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim != 1:
        raise SpectrumError("audio must be a 1-D array (mono)")
    if x.size == 0:
        raise SpectrumError("audio array is empty")
    if not np.isfinite(sample_rate) or sample_rate <= 0:
        raise SpectrumError("sample_rate must be positive and finite")
    if np.any(~np.isfinite(x)):
        raise SpectrumError("audio contains NaN or Inf")
    return x


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def is_silent(x: np.ndarray, threshold: float) -> bool:
    return rms(x) < float(threshold)


def window_array(name: str, n: int) -> np.ndarray:
    name = name.lower()
    if name == "hann":
        return np.hanning(n).astype(float)
    if name == "hamming":
        return np.hamming(n).astype(float)
    if name == "rect" or name == "rectangular":
        return np.ones(n, dtype=float)
    raise SpectrumError(f"unsupported window_type: {name}")


def stft_magnitude_power(
    x: np.ndarray,
    *,
    sample_rate: float,
    fft_size: int,
    hop_size: int,
    window_type: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (freqs, magnitude_frames[T,F], power_frames[T,F])."""
    x = validate_audio(x, sample_rate)
    if fft_size < 8:
        raise SpectrumError("fft_size too small")
    if hop_size < 1:
        raise SpectrumError("hop_size must be >= 1")
    win = window_array(window_type, fft_size)
    if x.size < fft_size:
        x = np.pad(x, (0, fft_size - x.size))
    n_frames = 1 + (x.size - fft_size) // hop_size
    mags = np.zeros((n_frames, fft_size // 2 + 1), dtype=float)
    for i in range(n_frames):
        start = i * hop_size
        frame = x[start : start + fft_size] * win
        spec = np.fft.rfft(frame)
        mags[i] = np.abs(spec)
    power = np.square(mags)
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    return freqs, mags, power


def band_mask(
    freqs: np.ndarray,
    *,
    fmin: float,
    fmax: float | None,
) -> np.ndarray:
    hi = float(np.max(freqs)) if fmax is None else float(fmax)
    return (freqs >= float(fmin)) & (freqs <= hi)


def weights_from_spectrum(
    magnitude: np.ndarray,
    power: np.ndarray,
    weighting: Weighting,
) -> np.ndarray:
    if weighting == "magnitude":
        return magnitude
    if weighting == "power":
        return power
    raise SpectrumError(f"unsupported weighting: {weighting}")


def profile_nyquist(profile: AnalysisProfile, sample_rate: float) -> float:
    fmax = profile.frequency_max_hz
    return float(sample_rate / 2.0) if fmax is None else float(fmax)


def mean_spectrum(
    frames: np.ndarray,
    *,
    normalize: bool,
) -> np.ndarray:
    mean = np.mean(frames, axis=0)
    if normalize:
        s = float(np.sum(mean))
        if s > 0:
            mean = mean / s
    return mean


def compare_domains(a: str, b: str) -> dict[str, Any]:
    if a == b:
        return {"status": "comparable", "classification": "aligned_domain"}
    return {
        "status": "not_comparable",
        "classification": "not_comparable",
        "reason": f"measurement_domain_mismatch:{a}!={b}",
    }
