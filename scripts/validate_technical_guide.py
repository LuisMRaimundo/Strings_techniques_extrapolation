#!/usr/bin/env python3
"""Validate docs/TECHNICAL_GUIDE.md against the live codebase (reliable checks only)."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "TECHNICAL_GUIDE.md"
CONFIGS = ROOT / "configs"

# Modules/symbols the guide must reference accurately
REQUIRED_SYMBOLS: list[tuple[str, str]] = [
    ("string_technique_model.production.bow_contact", "compute_beta"),
    ("string_technique_model.production.harmonics", "validate_harmonic_interval_order"),
    ("string_technique_model.production.mute", "normalize_mute_mass"),
    ("string_technique_model.production.migration", "migrate_legacy_technique_record"),
    ("string_technique_model.prediction.operations", "apply_operation"),
    ("string_technique_model.prediction.links", "link_forward"),
    ("string_technique_model.prediction.modes", "resolve_activate_user_assumptions"),
    ("string_technique_model.prediction.from_ordinary", "predict_from_ordinary"),
    ("string_technique_model.density.metric", "DensityMetric"),
    ("string_technique_model.applicability.resolver", "resolve_applicability"),
    ("string_technique_model.constraints.engine", "QualitativeConstraintEngine"),
    ("string_technique_model.literature.source_identity", "load_source_identity_registry"),
    ("string_technique_model.assumptions.activation", "resolve_user_assumptions"),
    ("string_technique_model.descriptors.engine", "compute_descriptor"),
    ("string_technique_model.descriptors.centroid", "compute_spectral_centroid"),
    ("string_technique_model.descriptors.attenuation", "amplitude_ratio_to_db"),
]

REQUIRED_CONFIGS = [
    "technique_ontology.yaml",
    "acoustic_descriptors.yaml",
    "qualitative_acoustic_constraints.yaml",
    "literature_sources.yaml",
    "literature_evidence_extracts.yaml",
    "density_metric.yaml",
    "model_links.yaml",
    "prediction.yaml",
    "user_assumptions.yaml",
    "source_identity_validation.yaml",
    "measurement_domains.yaml",
]

REQUIRED_GUIDE_PHRASES = [
    r"\\Phi\(D\)\s*=\s*D",
    r"\\beta\s*=",
    r"Not currently implemented",
    r"evidence_only",
    r"assumption_based",
    r"MEYER_ACOUSTICS",
    r"SRC_SCHOONDERWALDT_2009",
    r"SRC_EVANGELISTA_FREIRE_2025",
    r"harmonic_modal_acoustic_model_unavailable",
    r"missing_model_components",
    r"assumption_distribution_interval",
]

FORBIDDEN_GUIDE_CLAIMS = [
    r"list_implemented_descriptors\(\)\s+returns\s+`\[\]`",
    r"all\s+entries\s+`implemented:\s*false`",
    r"harmonic_insufficient_metadata",
]


def _has_symbol(module_name: str, symbol: str) -> bool:
    mod = importlib.import_module(module_name)
    return hasattr(mod, symbol)


def _cli_commands() -> set[str]:
    from string_technique_model.cli import build_parser

    parser = build_parser()
    for action in parser._subparsers._group_actions:  # type: ignore[attr-defined]
        if hasattr(action, "choices"):
            return set(action.choices.keys())
    return set()


def validate() -> list[str]:
    errors: list[str] = []
    if not GUIDE.exists():
        return [f"Missing guide: {GUIDE}"]

    text = GUIDE.read_text(encoding="utf-8")

    if "$$" not in text:
        errors.append("Guide lacks display LaTeX delimiters ($$...$$)")
    if text.count("$") < 20:
        errors.append("Guide has too few `$` math delimiters for StackEdit rendering")

    for pattern in REQUIRED_GUIDE_PHRASES:
        if not re.search(pattern, text):
            errors.append(f"Missing required guide content pattern: {pattern}")

    for pattern in FORBIDDEN_GUIDE_CLAIMS:
        if re.search(pattern, text):
            errors.append(f"Forbidden claim present: {pattern}")

    sys.path.insert(0, str(ROOT / "src"))
    for mod_name, symbol in REQUIRED_SYMBOLS:
        try:
            if not _has_symbol(mod_name, symbol):
                errors.append(f"Missing symbol {mod_name}.{symbol}")
            short = mod_name.split(".")[-1]
            if short not in text and symbol not in text:
                errors.append(f"Guide does not mention {symbol} or package {short}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Import failure {mod_name}: {exc}")

    for name in REQUIRED_CONFIGS:
        path = CONFIGS / name
        if not path.exists():
            errors.append(f"Missing config: {name}")
        elif name not in text:
            errors.append(f"Guide does not mention config: {name}")

    try:
        from string_technique_model.literature.package_ingestion import ingest_evidence_package

        result = ingest_evidence_package(dry_run=True)
        active = [d for d in result.decisions if getattr(d, "active", False)]
        if active:
            errors.append(f"Expected 0 active density params, found {len(active)}")
        if "inactive" not in text.lower() and "n_active_density_parameters == 0" not in text:
            errors.append("Guide does not state density parameters are inactive")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not verify active parameters: {exc}")

    try:
        cmds = _cli_commands()
        for cmd in ("predict", "assumptions", "literature", "baseline", "nonlinear", "extrapolate"):
            if cmd not in cmds:
                errors.append(f"CLI missing command {cmd}")
            if cmd not in text:
                errors.append(f"Guide missing CLI command `{cmd}`")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CLI inspection failed: {exc}")

    if re.search(r"user assumption[^\n]{0,80}literature-validated", text, re.I):
        if not re.search(
            r"never.*literature_validated|must remain `false`|not literature-validated",
            text,
            re.I,
        ):
            errors.append("Guide may conflate user assumptions with literature validation")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("TECHNICAL GUIDE VALIDATION FAILED")
        for e in errors:
            print(f" - {e}")
        return 1
    print("TECHNICAL GUIDE VALIDATION OK")
    print(f"Guide: {GUIDE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
