"""Compositional technique selection from the configured ontology."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from string_technique_model.ontology.loader import load_ontology

LEFT_HAND_CHOICES = [
    "ordinary_stopped",
    "natural_harmonic",
    "artificial_harmonic",
    "half_harmonic",
    "multiphonic",
    "natural_harmonic_glissando",
    "artificial_harmonic_glissando",
    "unknown",
]

BOW_CONTACT_CHOICES = [
    "molto_sul_tasto",
    "sul_tasto",
    "poco_sul_tasto",
    "ordinario",
    "flautando",
    "poco_sul_ponticello",
    "sul_ponticello",
    "molto_sul_ponticello",
    "directly_on_bridge",
    "afterlength_behind_bridge",
    "unknown",
]

MUTE_STATE_CHOICES = [
    "off",
    "on",
    "con_sordino",
    "unresolved",
    "unknown",
]

ARTICULATION_CHOICES = [
    "arco",
    "pizzicato",
    "col_legno",
    "tremolo",
    "legato",
    "staccato",
    "unknown",
]


class TechniqueCombination(BaseModel):
    model_config = ConfigDict(extra="allow")

    left_hand_regime: str | None = None
    bow_contact_regime: str | None = None
    mute_state: str | None = None
    articulation: str | None = None
    additional_technique: str | None = None


def ontology_technique_choices() -> dict[str, list[str]]:
    """Load complete configured ontology lists (with safe fallbacks)."""
    try:
        ont = load_ontology()
        left = list(getattr(ont, "left_hand_regimes", None) or LEFT_HAND_CHOICES)
        bow = list(getattr(ont, "bow_contact_categories", None) or BOW_CONTACT_CHOICES)
        # Add excitation regions that are not on the continuum
        for extra in ("directly_on_bridge", "afterlength_behind_bridge", "flautando"):
            if extra not in bow:
                bow.append(extra)
        return {
            "left_hand_regime": left + ["unknown"],
            "bow_contact_regime": bow + ["unknown"],
            "mute_state": MUTE_STATE_CHOICES,
            "articulation": ARTICULATION_CHOICES,
            "legacy_technique": list(getattr(ont, "legacy_technique_labels", None) or [])
            + [
                "ordinary",
                "flautando",
                "on_bridge",
                "afterlength",
                "natural_harmonic",
                "half_harmonic",
                "harmonic_glissando",
                "multiphonic",
            ],
        }
    except Exception:  # noqa: BLE001
        return {
            "left_hand_regime": LEFT_HAND_CHOICES,
            "bow_contact_regime": BOW_CONTACT_CHOICES,
            "mute_state": MUTE_STATE_CHOICES,
            "articulation": ARTICULATION_CHOICES,
            "legacy_technique": [
                "ordinary",
                "sul_tasto",
                "flautando",
                "sul_ponticello",
                "on_bridge",
                "afterlength",
                "natural_harmonic",
                "artificial_harmonic",
                "half_harmonic",
                "harmonic_glissando",
                "multiphonic",
                "con_sordino",
            ],
        }


def summarize_technique_combination(
    *,
    left_hand_regime: str | None = None,
    bow_contact_regime: str | None = None,
    mute_state: str | None = None,
    articulation: str | None = None,
    additional_technique: str | None = None,
    legacy_technique: str | None = None,
) -> str:
    """Human-readable combination label, e.g. 'artificial harmonic + sul ponticello + con sordino'."""
    parts: list[str] = []

    def _pretty(value: str | None) -> str | None:
        if value is None:
            return None
        v = str(value).strip()
        if not v or v.lower() in {"unknown", "unresolved", "none", "off", "ordinario", "ordinary_stopped", "arco"}:
            return None
        return v.replace("_", " ")

    for candidate in (
        _pretty(left_hand_regime),
        _pretty(bow_contact_regime),
        _pretty(mute_state if mute_state not in {"on"} else "con sordino"),
        _pretty(articulation),
        _pretty(additional_technique),
    ):
        if candidate and candidate not in parts:
            parts.append(candidate)

    if not parts and legacy_technique:
        pretty = _pretty(legacy_technique)
        if pretty:
            parts.append(pretty)

    return " + ".join(parts) if parts else (legacy_technique or "")


def apply_combination_to_row(row: dict[str, Any], combo: TechniqueCombination) -> dict[str, Any]:
    out = dict(row)
    out["left_hand_regime"] = combo.left_hand_regime
    out["bow_contact_regime"] = combo.bow_contact_regime
    out["mute_state"] = combo.mute_state
    out["articulation"] = combo.articulation
    out["additional_technique"] = combo.additional_technique
    out["technique_display"] = summarize_technique_combination(
        left_hand_regime=combo.left_hand_regime,
        bow_contact_regime=combo.bow_contact_regime,
        mute_state=combo.mute_state,
        articulation=combo.articulation,
        additional_technique=combo.additional_technique,
        legacy_technique=out.get("technique"),
    )
    return out


def harmonic_panel_visible(row: dict[str, Any]) -> bool:
    left = str(row.get("left_hand_regime") or row.get("technique") or "").lower()
    harm = str(row.get("harmonic_type") or "").lower()
    tokens = (
        "harmonic",
        "multiphonic",
    )
    return any(t in left for t in tokens) or harm in {"natural", "artificial", "half", "multiphonic"}
