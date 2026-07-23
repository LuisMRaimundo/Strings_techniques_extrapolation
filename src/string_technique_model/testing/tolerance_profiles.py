"""Load explicit stress-test tolerance profiles."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path


class ToleranceProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    value: float | None = None
    unit: str
    rationale: str
    applicable_descriptors: list[str] = Field(default_factory=list)
    applicable_checks: list[str] = Field(default_factory=list)
    source_or_justification: str | None = None


def load_tolerance_profiles(path: Path | str | None = None) -> dict[str, ToleranceProfile]:
    data = load_yaml(resolve_path(path or PACKAGE_ROOT / "configs" / "stress_tolerances.yaml"))
    profiles = [ToleranceProfile.model_validate(item) for item in (data.get("profiles") or [])]
    return {p.id: p for p in profiles}


def get_tolerance(profile_id: str, path: Path | str | None = None) -> ToleranceProfile:
    profiles = load_tolerance_profiles(path)
    if profile_id not in profiles:
        raise KeyError(f"Unknown tolerance profile: {profile_id}")
    return profiles[profile_id]


def abs_close(a: float, b: float, *, tol_id: str = "TOL_FLOAT64_ABS") -> bool:
    tol = get_tolerance(tol_id)
    if tol.value is None:
        raise ValueError(f"Tolerance {tol_id} has null value; numerical comparison not allowed")
    return abs(float(a) - float(b)) <= float(tol.value)


def rel_close(a: float, b: float, *, tol_id: str = "TOL_FLOAT64_REL") -> bool:
    tol = get_tolerance(tol_id)
    if tol.value is None:
        raise ValueError(f"Tolerance {tol_id} has null value")
    denom = max(abs(float(b)), 1e-15)
    return abs(float(a) - float(b)) / denom <= float(tol.value)
