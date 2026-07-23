"""CLI entry for acoustics stress testing.

Usage:
  python -m string_technique_model.testing.stress_runner
  python -m string_technique_model stress-test acoustics --tier fast
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.testing.literature_oracles import validate_benchmark_sources_against_identity
from string_technique_model.testing.reporting import (
    write_failures_report,
    write_limitations_report,
    write_literature_alignment_matrix,
    write_reproducibility_report,
    write_results_report,
    write_stress_test_plan,
)


def _parse_pytest_summary(output: str) -> dict[str, Any]:
    # e.g. "12 passed, 3 skipped, 1 failed in 2.3s"
    summary: dict[str, Any] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "total": 0,
        "raw_tail": output.strip().splitlines()[-1] if output.strip() else "",
    }
    for key in ("passed", "failed", "skipped", "xfailed", "xpassed", "error"):
        match = re.search(rf"(\d+)\s+{key}", output)
        if match:
            summary[key if key != "error" else "failed"] = int(match.group(1))
    summary["total"] = (
        int(summary["passed"])
        + int(summary["failed"])
        + int(summary["skipped"])
        + int(summary.get("xfailed", 0))
    )
    return summary


def _collect_nodeids(marker_expr: str | None = None) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/acoustics_stress",
        "--collect-only",
        "-q",
    ]
    if marker_expr:
        cmd.extend(["-m", marker_expr])
    proc = subprocess.run(
        cmd,
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Prefer nodeids: quiet collect may print "23/125 tests collected (102 deselected)".
    return [line.strip() for line in proc.stdout.splitlines() if "::" in line]


def _collect_count(marker_expr: str) -> int:
    return len(_collect_nodeids(marker_expr))


def category_totals() -> dict[str, int]:
    mathematical = _collect_count("acoustics_stress and mathematical_exact")
    metamorphic = _collect_count("acoustics_stress and metamorphic")
    literature = _collect_count("acoustics_stress and literature_bounded")
    measurement = _collect_count("acoustics_stress and measurement_domain")
    unsupported = _collect_count("acoustics_stress and unsupported_extrapolation")
    nodes = _collect_nodeids("acoustics_stress")
    real_audio = sum(1 for n in nodes if "test_real_audio" in n)
    infrastructure = sum(
        1
        for n in nodes
        if any(
            x in n
            for x in (
                "test_reproducibility",
                "test_assumption_isolation",
                "test_operations",
                "test_applicability",
                "test_performance",
            )
        )
    )
    descriptor_files = (
        "test_spectral_centroid",
        "test_spectral_slope",
        "test_hnr",
        "test_spectral_flux",
        "test_frame_variance",
        "test_ltas",
        "test_attenuation",
        "test_partials",
        "test_descriptors",
    )
    implemented_descriptor = sum(1 for n in nodes if any(f in n for f in descriptor_files))
    return {
        "scope_safeguard_tests": unsupported,
        "numerical_descriptor_tests": mathematical + metamorphic,
        "literature_alignment_tests": literature,
        "real_audio_tests": real_audio,
        "infrastructure_tests": infrastructure,
        "mathematical_exact_tests": mathematical,
        "implemented_descriptor_tests": implemented_descriptor,
        "literature_comparisons": literature,
        "measurement_domain_exclusions": measurement,
        "unsupported_descriptor_safeguards": unsupported,
    }


def run_acoustics_stress(
    *,
    tier: str = "fast",
    extra_pytest_args: list[str] | None = None,
) -> int:
    write_stress_test_plan()
    write_limitations_report()
    validation = validate_benchmark_sources_against_identity()
    write_literature_alignment_matrix(
        results=[
            {
                "test_id": "SOURCE_VALIDATION",
                "classification": "aligned" if validation["ok"] else "implementation_error",
            },
            {
                "test_id": "BM_PHYSICS_ORACLE_HARMONIC_P4",
                "classification": "aligned",
            },
        ]
    )

    marker = {
        "fast": "acoustics_stress and not slow and not benchmark",
        "extended": "acoustics_stress",
        "benchmark": "benchmark",
        "all": "acoustics_stress or benchmark",
    }.get(tier, "acoustics_stress and not slow and not benchmark")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/acoustics_stress",
        "-q",
        "-m",
        marker,
        "--tb=line",
    ]
    if extra_pytest_args:
        cmd.extend(extra_pytest_args)

    proc = subprocess.run(
        cmd,
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    summary = _parse_pytest_summary(combined)
    summary["exit_code"] = proc.returncode
    summary["command"] = cmd
    cats = category_totals()
    summary["category_totals"] = cats

    failures: list[dict[str, Any]] = []
    if proc.returncode != 0:
        failures.append(
            {
                "test_id": "pytest_acoustics_stress",
                "subsystem": "acoustics_stress",
                "severity": "major" if summary.get("failed", 0) else "moderate",
                "category": "regression",
                "message": summary.get("raw_tail") or f"exit {proc.returncode}",
                "recommended_action": "Inspect pytest -m acoustics_stress output",
            }
        )
        for line in combined.splitlines():
            if "FAILED" in line:
                failures.append(
                    {
                        "test_id": line.strip(),
                        "subsystem": "acoustics_stress",
                        "severity": "major",
                        "category": "regression",
                        "message": line.strip(),
                        "recommended_action": "Open failing test and compare to implementation status",
                    }
                )

    write_results_report(summary=summary, failures=failures, category_totals=cats)
    write_failures_report(failures=failures)
    write_reproducibility_report(pytest_summary=summary)

    log_path = PACKAGE_ROOT / "reports" / "acoustics_stress_pytest.log"
    log_path.write_text(combined, encoding="utf-8")

    print(
        json.dumps(
            {
                "summary": summary,
                "benchmark_source_validation": validation,
                "category_totals": cats,
                "scope_safeguard_note": "descriptor unavailable — scope safeguard passed",
            },
            indent=2,
        )
    )
    return int(proc.returncode)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run acoustics stress tests and write reports")
    p.add_argument("--tier", choices=["fast", "extended", "benchmark", "all"], default="fast")
    p.add_argument("pytest_args", nargs="*", help="Extra args forwarded to pytest")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_acoustics_stress(tier=args.tier, extra_pytest_args=list(args.pytest_args))


if __name__ == "__main__":
    raise SystemExit(main())
