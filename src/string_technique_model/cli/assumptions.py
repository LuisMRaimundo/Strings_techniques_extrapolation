"""CLI management commands for explicitly user-supplied assumptions."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from string_technique_model.assumptions import (
    clear_assumption_registry_cache,
    get_user_assumption_registry,
    load_user_assumption_registry,
    resolve_user_assumptions,
)
from string_technique_model.config import PACKAGE_ROOT, resolve_path

WARNING_BANNER = (
    "WARNING: USER ASSUMPTION — not literature-validated and not evidence-based."
)


def _config_path(value: Path | None) -> Path:
    return resolve_path(value or PACKAGE_ROOT / "configs" / "user_assumptions.yaml")


def _assumption_payload(assumption: Any) -> dict[str, Any]:
    payload = assumption.model_dump()
    payload["literature_validated"] = False
    return payload


def _rewrite_active_flag(path: Path, assumption_id: str, active: bool) -> dict[str, Any]:
    """Back up then update only the selected entry's active flag."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assumptions = data.get("assumptions") or []
    match = next((item for item in assumptions if item.get("assumption_id") == assumption_id), None)
    if match is None:
        raise KeyError(f"Unknown assumption ID: {assumption_id}")
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    match["active_for_density_prediction"] = active
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    clear_assumption_registry_cache()
    return {"assumption_id": assumption_id, "active_for_density_prediction": active, "backup": str(backup)}


def register_assumptions_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser("assumptions", help="Manage user numerical assumptions")
    sub = parser.add_subparsers(dest="assumptions_command", required=True)
    for name in ("list", "validate"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, default=None)
    show = sub.add_parser("show")
    show.add_argument("assumption_id")
    show.add_argument("--config", type=Path, default=None)
    for name in ("activate", "deactivate"):
        command = sub.add_parser(name)
        command.add_argument("assumption_id")
        command.add_argument("--config", type=Path, default=None)
    applicable = sub.add_parser("applicable")
    applicable.add_argument("--instrument", required=True)
    applicable.add_argument("--technique", required=True)
    applicable.add_argument("--dynamic", default="mf")
    applicable.add_argument("--config", type=Path, default=None)
    audit = sub.add_parser("audit")
    audit.add_argument("--output", type=Path, default=Path("reports/assumption_audit.md"))
    audit.add_argument("--config", type=Path, default=None)


def run_assumptions_command(args: argparse.Namespace) -> int:
    path = _config_path(getattr(args, "config", None))
    command = args.assumptions_command
    if command == "validate":
        registry = load_user_assumption_registry(path)
        print(json.dumps({"valid": True, "assumptions": len(registry.assumptions), "literature_validated": False}))
        return 0
    if command == "list":
        registry = get_user_assumption_registry(path)
        print(json.dumps([_assumption_payload(a) for a in registry.assumptions], indent=2, default=str))
        return 0
    if command == "show":
        registry = get_user_assumption_registry(path)
        assumption = registry.by_id(args.assumption_id)
        print(json.dumps(_assumption_payload(assumption), indent=2, default=str))
        return 0
    if command in {"activate", "deactivate"}:
        result = _rewrite_active_flag(path, args.assumption_id, command == "activate")
        if command == "activate":
            assumption = get_user_assumption_registry(path).by_id(args.assumption_id)
            print(WARNING_BANNER)
            print(
                json.dumps(
                    {
                        **result,
                        "value": assumption.reported_value,
                        "unit": assumption.unit,
                        "uncertainty": assumption.uncertainty_sd or assumption.uncertainty_distribution,
                        "scope": assumption.scope_note,
                        "equation": f"{assumption.operation_type}({assumption.source_space} → {assumption.target_space})",
                        "literature_validated": False,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            print(json.dumps(result, indent=2))
        return 0
    if command == "applicable":
        records = resolve_user_assumptions(
            context={
                "instrument": args.instrument,
                "technique": args.technique,
                "dynamic": args.dynamic,
                "target_metric_definition_id": "ewsd_v1",
            },
            link="log",
            activation_enabled=True,
            path=str(path),
        )
        print(json.dumps([r.to_row("applicable") for r in records], indent=2))
        return 0
    if command == "audit":
        registry = get_user_assumption_registry(path)
        output = resolve_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# User assumption audit", "", WARNING_BANNER, ""]
        for assumption in registry.assumptions:
            lines.extend(
                [
                    f"## {assumption.assumption_id}",
                    f"- active_for_density_prediction: `{assumption.active_for_density_prediction}`",
                    f"- instrument / technique: `{assumption.instrument}` / `{assumption.technique}`",
                    f"- operation: `{assumption.operation_type}`",
                    f"- value / unit: `{assumption.reported_value}` / `{assumption.unit}`",
                    f"- scope: {assumption.scope_note or 'not specified'}",
                    "- literature_validated: `false`",
                    "",
                ]
            )
        output.write_text("\n".join(lines), encoding="utf-8")
        print(str(output))
        return 0
    raise ValueError(f"Unknown assumptions command: {command}")
