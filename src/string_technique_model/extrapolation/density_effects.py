"""Provisional ordinary→technique density (EWSD) numeric effects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

DEFAULT_EFFECTS = PACKAGE_ROOT / "configs" / "extrapolation" / "provisional_density_effects_v1.yaml"


def load_density_effects(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(resolve_path(path or DEFAULT_EFFECTS))


def _power_ratio_from_db(db: float) -> float:
    return 10.0 ** (-float(db) / 10.0)


def estimate_technique_density(
    *,
    baseline: float,
    technique: str,
    instrument: str,
    literature_atten_db: float | None = None,
    effects_cfg: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return numeric provisional estimate or None if not configured / insufficient.

    Keys: value, lower_bound, upper_bound, method, assumptions, warnings,
          qualitative_effect, attenuation_db, value_kind, evidence_status, source
    """
    cfg = effects_cfg if effects_cfg is not None else load_density_effects()
    if not cfg.get("enabled", True):
        return None
    effects = cfg.get("effects") or {}
    spec = effects.get(technique)
    if not spec:
        return None

    assumptions = list(spec.get("assumptions") or [])
    warnings: list[str] = [
        "PROVISIONAL numeric estimate — edit configs/extrapolation/provisional_density_effects_v1.yaml to change factors."
    ]
    qualitative = spec.get("qualitative_effect")
    mode = spec.get("mode")

    if mode == "power_db_proxy":
        db = literature_atten_db
        if db is None:
            fb = (spec.get("fallback_db_by_instrument") or {}).get(instrument)
            if fb is None:
                return {
                    "value": None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "method": "mute_db_unavailable_for_instrument",
                    "assumptions": assumptions,
                    "warnings": warnings
                    + [f"No mute dB for {instrument}; add fallback_db_by_instrument or literature row."],
                    "qualitative_effect": qualitative,
                    "attenuation_db": None,
                    "value_kind": "unavailable",
                    "evidence_status": "literature_insufficient",
                    "source": "provisional_density_effects_v1",
                    "na_reason": "mute_db_missing_for_instrument",
                }
            db = float(fb)
            warnings.append(f"Using config fallback mute dB={db} for {instrument}.")
        ratio = _power_ratio_from_db(db)
        center = float(baseline) * ratio
        band = float(spec.get("relative_band") or 0.15)
        lo = center * (1.0 - band)
        hi = center * (1.0 + band)
        return {
            "value": center,
            "lower_bound": lo,
            "upper_bound": hi,
            "method": f"provisional_power_db_proxy:dB={db}",
            "assumptions": assumptions,
            "warnings": warnings
            + [f"Mute ≈ {db} dB power → scale ×{ratio:.4f} on ordinary EWSD."],
            "qualitative_effect": qualitative,
            "attenuation_db": float(db),
            "value_kind": "extrapolated",
            "evidence_status": "literature_supported",
            "source": "provisional_density_effects_v1+mute_dB",
            "na_reason": None,
        }

    if mode == "relative_factor":
        factor = float(spec["factor"])
        flo = float(spec.get("factor_lo", factor))
        fhi = float(spec.get("factor_hi", factor))
        if flo > fhi:
            flo, fhi = fhi, flo
        center = float(baseline) * factor
        lo = float(baseline) * flo
        hi = float(baseline) * fhi
        return {
            "value": center,
            "lower_bound": min(lo, hi),
            "upper_bound": max(lo, hi),
            "method": f"provisional_relative_factor:{factor}",
            "assumptions": assumptions,
            "warnings": warnings + [f"Applied relative factor {factor} (bounds {flo}…{fhi})."],
            "qualitative_effect": qualitative,
            "attenuation_db": None,
            "value_kind": "extrapolated",
            "evidence_status": "secondary_synthesis_qualitative",
            "source": "provisional_density_effects_v1",
            "na_reason": None,
        }

    return None
