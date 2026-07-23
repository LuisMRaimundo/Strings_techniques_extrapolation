"""Explicit activation modes for numerical prediction inputs."""

from __future__ import annotations

from typing import Literal

PredictionMode = Literal["evidence_only", "evidence_plus_user_assumptions"]


def resolve_activate_user_assumptions(mode: PredictionMode | str | None) -> bool:
    """Return whether user assumptions are enabled for an explicit mode.

    Unknown and omitted modes deliberately fail closed.
    """
    return mode == "evidence_plus_user_assumptions"
