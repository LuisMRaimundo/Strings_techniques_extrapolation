"""Qualitative constraint matching engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml
from string_technique_model.constraints.models import (
    ConstraintEvaluationResult,
    ConstraintMatch,
    ProductionCondition,
    QualitativeConstraint,
)
from string_technique_model.production.models import ProductionInstruction

CONSTRAINTS_PATH = PACKAGE_ROOT / "configs" / "qualitative_acoustic_constraints.yaml"


def _as_dict(value: ProductionInstruction | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, ProductionInstruction):
        return value.model_dump()
    return value


def _nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _flatten_legacy_technique(production: dict[str, Any]) -> dict[str, Any]:
    """Allow flat prediction contexts (technique=sul_tasto) to match constraints."""
    if production.get("bow_contact") or production.get("mute") or production.get("left_hand"):
        return production
    technique = str(production.get("technique") or production.get("target_technique") or "")
    out = dict(production)
    if technique in {
        "sul_tasto",
        "poco_sul_tasto",
        "molto_sul_tasto",
        "sul_ponticello",
        "poco_sul_ponticello",
        "molto_sul_ponticello",
    }:
        out["bow_contact"] = {
            "category": technique,
            "motion_regime": production.get("motion_regime"),
        }
    elif technique == "artificial_harmonic":
        out["left_hand"] = {
            "left_hand_regime": "artificial_harmonic",
            "harmonic_type": production.get("harmonic_type") or "artificial",
        }
    elif technique == "con_sordino":
        mute_type = str(production.get("mute_type") or "").lower()
        category = "unresolved"
        if "light" in mute_type and "practice" in mute_type:
            category = "light_practice"
        elif "heavy" in mute_type or "hotel" in mute_type or mute_type == "practice":
            category = "heavy_practice"
        elif mute_type in {"orchestral", "standard", "performance", "performance_mute", "wood", "rubber"}:
            category = "performance_mute"
        out["mute"] = {"category": category, "state": "on"}
    if production.get("timbre_execution_target") == "flautando" or str(
        production.get("articulation") or ""
    ).lower() == "flautando":
        out["timbre_execution_target"] = "flautando"
    return out


def _production_matches(condition: ProductionCondition, production: dict[str, Any]) -> bool:
    production = _flatten_legacy_technique(production)
    bow_category = _nested_get(production, "bow_contact", "category")
    mute_category = _nested_get(production, "mute", "category")
    left_hand_regime = _nested_get(production, "left_hand", "left_hand_regime")
    motion_regime = _nested_get(production, "bow_contact", "motion_regime")

    if condition.bow_contact_category_any_of is not None:
        if bow_category is None or bow_category not in condition.bow_contact_category_any_of:
            return False

    if condition.mute_category is not None:
        if mute_category != condition.mute_category:
            return False

    if condition.left_hand_regime_any_of is not None:
        if left_hand_regime is None or left_hand_regime not in condition.left_hand_regime_any_of:
            return False

    if condition.left_hand_regime is not None:
        if left_hand_regime != condition.left_hand_regime:
            return False

    if condition.motion_regime is not None:
        if motion_regime != condition.motion_regime:
            return False

    return True


class QualitativeConstraintEngine:
    """Match production instructions against qualitative acoustic constraints."""

    def __init__(self, constraints: list[QualitativeConstraint]) -> None:
        self._constraints = constraints

    @classmethod
    def load(cls, path: Path | str | None = None) -> QualitativeConstraintEngine:
        data = load_yaml(path or CONSTRAINTS_PATH)
        items = [
            QualitativeConstraint.model_validate(item) for item in data.get("constraints", [])
        ]
        return cls(items)

    @property
    def constraints(self) -> list[QualitativeConstraint]:
        return list(self._constraints)

    def match(
        self,
        production_instruction_or_dict: ProductionInstruction | dict[str, Any],
        instrument: str,
    ) -> list[ConstraintMatch]:
        production = _as_dict(production_instruction_or_dict)
        matches: list[ConstraintMatch] = []

        for constraint in self._constraints:
            if instrument not in constraint.instrument_scope:
                continue
            if not _production_matches(constraint.production_condition, production):
                continue
            matches.append(
                ConstraintMatch(
                    constraint_id=constraint.constraint_id,
                    descriptor=constraint.descriptor,
                    tendency=constraint.tendency,
                    strength=constraint.strength,
                    required_contextual_variables=list(constraint.required_contextual_variables),
                    exceptions_or_limitations=constraint.exceptions_or_limitations,
                    source_ids=list(constraint.source_ids),
                    evidence_ids=list(constraint.evidence_ids),
                    numerical_prediction_allowed=constraint.numerical_prediction_allowed,
                )
            )
        return matches

    def evaluate(
        self,
        production_instruction_or_dict: ProductionInstruction | dict[str, Any],
        instrument: str,
        *,
        request_density_prediction: bool = False,
    ) -> ConstraintEvaluationResult:
        """Return structured qualitative tendencies; never EWSD numbers."""
        if request_density_prediction:
            return ConstraintEvaluationResult(
                status="numerical_prediction_not_allowed",
                instrument=instrument,
                message=(
                    "Qualitative constraints may express tendencies only; "
                    "numerical density prediction is not allowed from this layer."
                ),
            )

        matches = self.match(production_instruction_or_dict, instrument)
        tendencies = [
            {
                "descriptor": m.descriptor,
                "tendency": m.tendency,
                "strength": m.strength,
                "constraint_id": m.constraint_id,
                "required_contextual_variables": m.required_contextual_variables,
                "exceptions_or_limitations": m.exceptions_or_limitations,
            }
            for m in matches
        ]
        return ConstraintEvaluationResult(
            status="qualitative_tendencies_only",
            instrument=instrument,
            matches=matches,
            tendencies=tendencies,
        )


def load_constraints(path: Path | str | None = None) -> list[QualitativeConstraint]:
    return QualitativeConstraintEngine.load(path).constraints
