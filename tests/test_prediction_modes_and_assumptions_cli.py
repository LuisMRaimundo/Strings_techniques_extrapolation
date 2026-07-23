"""Explicit prediction modes and user-assumption CLI coverage."""

from __future__ import annotations

from pathlib import Path

import yaml

from string_technique_model.assumptions import (
    AssumptionConflictError,
    clear_assumption_registry_cache,
    resolve_user_assumptions,
)
from string_technique_model.cli import build_parser
from string_technique_model.cli.assumptions import run_assumptions_command
from string_technique_model.prediction.modes import resolve_activate_user_assumptions


def _assumption(assumption_id: str = "UA_MODE_TEST") -> dict:
    return {
        "assumption_id": assumption_id,
        "instrument": "vln",
        "technique": "sul_ponticello",
        "operation_type": "multiplicative_ratio",
        "reported_value": 1.1,
        "unit": "dimensionless_ratio",
        "numerical_scale": "density_ratio",
        "compatible_links": ["log"],
        "source_space": "density",
        "target_space": "density",
        "uncertainty_sd": 0.05,
        "applicable_dynamic": "mf",
        "operationalisation": "Test-only explicit ratio.",
        "provenance": "test fixture; not literature",
        "active_for_density_prediction": True,
    }


def _registry(path: Path, assumptions: list[dict]) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "literature_validated": False,
                "default_active_for_density_prediction": False,
                "assumptions": assumptions,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    clear_assumption_registry_cache()


def _context() -> dict:
    return {
        "instrument": "vln",
        "technique": "sul_ponticello",
        "dynamic": "mf",
        "target_metric_definition_id": "ewsd_v1",
    }


def test_evidence_only_mode_never_activates_assumptions(tmp_path: Path):
    path = tmp_path / "assumptions.yaml"
    _registry(path, [_assumption()])
    records = resolve_user_assumptions(
        context=_context(),
        link="log",
        activation_enabled=resolve_activate_user_assumptions("evidence_only"),
        path=str(path),
    )
    assert records[0].status == "inactive"
    assert resolve_activate_user_assumptions(None) is False


def test_evidence_plus_user_assumptions_activates_applicable_entry(tmp_path: Path):
    path = tmp_path / "assumptions.yaml"
    _registry(path, [_assumption()])
    records = resolve_user_assumptions(
        context=_context(),
        link="log",
        activation_enabled=resolve_activate_user_assumptions("evidence_plus_user_assumptions"),
        path=str(path),
    )
    assert records[0].status == "active"
    assert records[0].assumption["literature_validated"] is False


def test_conflicting_active_assumptions_raise(tmp_path: Path):
    path = tmp_path / "assumptions.yaml"
    _registry(path, [_assumption(), _assumption("UA_MODE_TEST_2")])
    try:
        resolve_user_assumptions(
            context=_context(),
            link="log",
            activation_enabled=True,
            path=str(path),
        )
    except AssumptionConflictError:
        pass
    else:
        raise AssertionError("expected AssumptionConflictError")


def test_assumptions_cli_list_and_validate(tmp_path: Path, capsys):
    path = tmp_path / "assumptions.yaml"
    _registry(path, [_assumption()])
    parser = build_parser()
    validate = parser.parse_args(["assumptions", "validate", "--config", str(path)])
    assert run_assumptions_command(validate) == 0
    assert '"valid": true' in capsys.readouterr().out
    listed = parser.parse_args(["assumptions", "list", "--config", str(path)])
    assert run_assumptions_command(listed) == 0
    assert "UA_MODE_TEST" in capsys.readouterr().out
