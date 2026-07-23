"""Deterministic synthetic signals for descriptor-level stress fixtures.

These are numerical test fixtures. They are NOT claimed to be perceptually
equivalent to real bowed-string sounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

SignalKind = Literal[
    "pure_sine",
    "two_tone",
    "harmonic_sum",
    "missing_fundamental",
    "inharmonic",
    "amplitude_modulated",
    "frequency_modulated",
    "harmonic_plus_noise",
    "band_limited_noise",
    "impulsive_decay",
    "pulse_train",
    "beating_pair",
    "two_component_multiphonic_proxy",
    "time_varying_envelope",
    "spectral_transition",
    "alternating_tones",
    "silence",
    "near_silence",
    "clipped",
    "nan_contaminated",
    "inf_contaminated",
]


@dataclass(frozen=True)
class SyntheticSignal:
    samples: np.ndarray
    sample_rate_hz: float
    amplitude_convention: str
    duration_s: float
    kind: str
    seed: int | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def assert_finite(self) -> None:
        if not np.isfinite(self.samples).all():
            raise ValueError(f"Signal kind={self.kind} contains non-finite samples")


def _time_vector(duration_s: float, sample_rate_hz: float) -> np.ndarray:
    n = max(int(round(duration_s * sample_rate_hz)), 1)
    return np.arange(n, dtype=float) / float(sample_rate_hz)


def _fade(x: np.ndarray, sample_rate_hz: float, fade_s: float) -> np.ndarray:
    if fade_s <= 0:
        return x
    n = len(x)
    fade_n = min(int(round(fade_s * sample_rate_hz)), n // 2)
    if fade_n <= 0:
        return x
    out = x.copy()
    ramp = np.linspace(0.0, 1.0, fade_n)
    out[:fade_n] *= ramp
    out[-fade_n:] *= ramp[::-1]
    return out


def generate_signal(
    kind: SignalKind | str,
    *,
    sample_rate_hz: float = 44100.0,
    duration_s: float = 0.25,
    seed: int = 0,
    amplitude: float = 0.5,
    fade_s: float = 0.005,
    **params: Any,
) -> SyntheticSignal:
    """Generate a deterministic synthetic signal fixture."""
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if duration_s < 0:
        raise ValueError("duration_s must be non-negative")

    rng = np.random.default_rng(seed)
    t = _time_vector(duration_s, sample_rate_hz)
    meta: dict[str, Any] = {"params": dict(params), "fixture_role": "numerical_test_only"}

    if kind == "silence":
        x = np.zeros_like(t)
    elif kind == "near_silence":
        x = np.full_like(t, 1e-12)
    elif kind == "pure_sine":
        f0 = float(params.get("frequency_hz", 1000.0))
        x = amplitude * np.sin(2 * np.pi * f0 * t)
        meta["frequency_hz"] = f0
    elif kind == "two_tone":
        f1 = float(params.get("f1_hz", 500.0))
        f2 = float(params.get("f2_hz", 1500.0))
        a1 = float(params.get("a1", amplitude))
        a2 = float(params.get("a2", amplitude))
        x = a1 * np.sin(2 * np.pi * f1 * t) + a2 * np.sin(2 * np.pi * f2 * t)
        meta.update({"f1_hz": f1, "f2_hz": f2, "a1": a1, "a2": a2})
    elif kind == "harmonic_sum":
        f0 = float(params.get("frequency_hz", 220.0))
        n_harm = int(params.get("n_harmonics", 5))
        x = np.zeros_like(t)
        for k in range(1, n_harm + 1):
            x += (amplitude / k) * np.sin(2 * np.pi * f0 * k * t)
        meta.update({"frequency_hz": f0, "n_harmonics": n_harm})
    elif kind == "missing_fundamental":
        f0 = float(params.get("frequency_hz", 220.0))
        x = np.zeros_like(t)
        for k in range(2, int(params.get("n_harmonics", 6)) + 1):
            x += (amplitude / k) * np.sin(2 * np.pi * f0 * k * t)
        meta["frequency_hz"] = f0
    elif kind == "inharmonic":
        freqs = params.get("frequencies_hz", [220.0, 330.5, 510.2])
        x = np.zeros_like(t)
        for i, f in enumerate(freqs):
            x += (amplitude / (i + 1)) * np.sin(2 * np.pi * float(f) * t)
        meta["frequencies_hz"] = list(freqs)
    elif kind == "amplitude_modulated":
        f0 = float(params.get("frequency_hz", 440.0))
        fm = float(params.get("mod_hz", 5.0))
        depth = float(params.get("depth", 0.5))
        env = 1.0 + depth * np.sin(2 * np.pi * fm * t)
        x = amplitude * env * np.sin(2 * np.pi * f0 * t)
    elif kind == "frequency_modulated":
        f0 = float(params.get("frequency_hz", 440.0))
        fm = float(params.get("mod_hz", 5.0))
        beta = float(params.get("beta", 2.0))
        phase = 2 * np.pi * f0 * t + beta * np.sin(2 * np.pi * fm * t)
        x = amplitude * np.sin(phase)
    elif kind == "harmonic_plus_noise":
        base = generate_signal(
            "harmonic_sum",
            sample_rate_hz=sample_rate_hz,
            duration_s=duration_s,
            seed=seed,
            amplitude=amplitude,
            fade_s=0.0,
            **{k: v for k, v in params.items() if k != "noise_level"},
        ).samples
        noise_level = float(params.get("noise_level", 0.1))
        x = base + noise_level * rng.normal(0.0, 1.0, size=base.shape)
        meta["noise_level"] = noise_level
    elif kind == "band_limited_noise":
        x = amplitude * rng.normal(0.0, 1.0, size=t.shape)
    elif kind == "impulsive_decay":
        tau = float(params.get("tau_s", 0.05))
        x = amplitude * np.exp(-t / max(tau, 1e-9))
        x[0] = amplitude
    elif kind == "pulse_train":
        f0 = float(params.get("frequency_hz", 100.0))
        x = np.zeros_like(t)
        period = int(max(round(sample_rate_hz / f0), 1))
        x[::period] = amplitude
    elif kind == "beating_pair":
        f1 = float(params.get("f1_hz", 440.0))
        f2 = float(params.get("f2_hz", 444.0))
        x = 0.5 * amplitude * (np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t))
        meta.update({"f1_hz": f1, "f2_hz": f2})
    elif kind == "two_component_multiphonic_proxy":
        # Numerical proxy only — not a cello multiphonic simulation.
        f1 = float(params.get("f1_hz", 196.0))
        f2 = float(params.get("f2_hz", 294.0))
        x = 0.5 * amplitude * (np.sin(2 * np.pi * f1 * t) + np.sin(2 * np.pi * f2 * t))
        meta.update(
            {
                "f1_hz": f1,
                "f2_hz": f2,
                "proxy_warning": "numerical_multiphonic_proxy_not_cello_simulation",
            }
        )
    elif kind == "time_varying_envelope":
        f0 = float(params.get("frequency_hz", 440.0))
        env = 0.2 + 0.8 * (0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t))
        x = amplitude * env * np.sin(2 * np.pi * f0 * t)
    elif kind == "spectral_transition":
        # First half f1, second half f2 — numerical flux fixture only.
        f1 = float(params.get("f1_hz", 400.0))
        f2 = float(params.get("f2_hz", 1600.0))
        mid = len(t) // 2
        x = np.zeros_like(t)
        x[:mid] = amplitude * np.sin(2 * np.pi * f1 * t[:mid])
        x[mid:] = amplitude * np.sin(2 * np.pi * f2 * t[mid:])
        meta.update({"f1_hz": f1, "f2_hz": f2, "transition": "abrupt_midpoint"})
    elif kind == "alternating_tones":
        f1 = float(params.get("f1_hz", 500.0))
        f2 = float(params.get("f2_hz", 2000.0))
        block = int(max(params.get("block_samples", sample_rate_hz * 0.05), 1))
        x = np.zeros_like(t)
        for i in range(0, len(t), block):
            f = f1 if ((i // block) % 2 == 0) else f2
            sl = slice(i, min(i + block, len(t)))
            x[sl] = amplitude * np.sin(2 * np.pi * f * t[sl])
        meta.update({"f1_hz": f1, "f2_hz": f2, "block_samples": block})
    elif kind == "clipped":
        x = np.clip(amplitude * np.sin(2 * np.pi * 440.0 * t) * 3.0, -amplitude, amplitude)
    elif kind == "nan_contaminated":
        x = amplitude * np.sin(2 * np.pi * 440.0 * t)
        x[len(x) // 2] = np.nan
    elif kind == "inf_contaminated":
        x = amplitude * np.sin(2 * np.pi * 440.0 * t)
        x[len(x) // 2] = np.inf
    else:
        raise ValueError(f"Unknown synthetic signal kind: {kind}")

    if kind not in {"nan_contaminated", "inf_contaminated", "silence", "near_silence"}:
        x = _fade(x, sample_rate_hz, fade_s)

    return SyntheticSignal(
        samples=np.asarray(x, dtype=float),
        sample_rate_hz=float(sample_rate_hz),
        amplitude_convention="linear_peak_normalized_fixture",
        duration_s=float(duration_s),
        kind=str(kind),
        seed=seed,
        metadata=meta,
    )


SUPPORTED_SIGNAL_KINDS: tuple[str, ...] = (
    "pure_sine",
    "two_tone",
    "harmonic_sum",
    "missing_fundamental",
    "inharmonic",
    "amplitude_modulated",
    "frequency_modulated",
    "harmonic_plus_noise",
    "band_limited_noise",
    "impulsive_decay",
    "pulse_train",
    "beating_pair",
    "two_component_multiphonic_proxy",
    "time_varying_envelope",
    "spectral_transition",
    "alternating_tones",
    "silence",
    "near_silence",
    "clipped",
    "nan_contaminated",
    "inf_contaminated",
)
