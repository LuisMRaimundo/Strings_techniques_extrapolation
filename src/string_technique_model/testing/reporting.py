"""Markdown report writers for acoustics stress testing."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, resolve_path
from string_technique_model.descriptors.registry import list_implemented_descriptors, load_descriptor_registry
from string_technique_model.literature.source_identity import load_source_identity_registry
from string_technique_model.testing.literature_oracles import (
    load_literature_benchmark_cases,
    validate_benchmark_sources_against_identity,
)
from string_technique_model.testing.reference_cases import worked_benchmarks


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def environment_block() -> dict[str, Any]:
    return {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "executable": sys.executable,
        "package_root": str(PACKAGE_ROOT),
        "generated_at_utc": _utc_now(),
    }


def write_stress_test_plan(path: Path | str | None = None) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "acoustics_stress_test_plan.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    benches = worked_benchmarks()
    implemented = [d.descriptor_id for d in list_implemented_descriptors()]
    unsupported = [d.descriptor_id for d in load_descriptor_registry().all() if not d.implemented]
    lines = [
        "# Acoustics stress test plan",
        "",
        f"Generated: {_utc_now()}",
        "",
        "## Principles",
        "",
        "1. Exact mathematical tests for implemented equations.",
        "2. Literature-bounded tests only from identity-verified sources.",
        "3. Qualitative/metamorphic tests for directional/non-equivalence claims.",
        "4. Negative/scope tests for unsupported extrapolation.",
        "5. Scope-safeguard passes for unimplemented descriptors are **not** numerical validation.",
        "",
        "## Tiers",
        "",
        "- Fast: `pytest -m \"acoustics_stress and not slow and not benchmark\"`",
        "- Full: `pytest tests/acoustics_stress -q` or `pytest -m acoustics_stress`",
        "- Benchmarks: `pytest -m benchmark`",
        "",
        "## Worked benchmarks A–J",
        "",
        "| ID | Name | Status |",
        "|----|------|--------|",
    ]
    for b in benches:
        lines.append(f"| {b.id} | {b.name} | `{b.status}` |")
    lines.extend(
        [
            "",
            "## Implemented descriptors",
            "",
            ", ".join(f"`{d}`" for d in implemented) or "_none_",
            "",
            "## Unsupported descriptors (scope safeguard only)",
            "",
            ", ".join(f"`{d}`" for d in unsupported) or "_none_",
            "",
            "## Synthetic signals",
            "",
            "Deterministic fixtures in `testing/signal_generators.py`.",
            "Not perceptually equivalent to real bowed-string sounds.",
            "",
            "## Real-audio validation",
            "",
            "**Absent** — no verified local audio corpus accompanies articles/datasets;",
            "no silent downloads; optional dataset adapters only.",
            "",
            "## Report categories",
            "",
            "- infrastructure tests",
            "- mathematical exact tests",
            "- implemented descriptor tests",
            "- literature comparisons",
            "- measurement-domain exclusions",
            "- real-audio tests",
            "- unsupported descriptors (scope safeguard)",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_literature_alignment_matrix(
    path: Path | str | None = None,
    *,
    results: list[dict[str, Any]] | None = None,
) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "literature_alignment_matrix.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    cases = load_literature_benchmark_cases()
    validation = validate_benchmark_sources_against_identity(cases)
    result_by_id = {r["test_id"]: r for r in (results or [])}
    lines = [
        "# Literature alignment matrix",
        "",
        f"Generated: {_utc_now()}",
        "",
        f"Benchmark source validation ok: **{validation['ok']}**",
        "",
        "| test ID | source | DOI | domain | claim type | expected | result | scope |",
        "|---------|--------|-----|--------|------------|----------|--------|-------|",
    ]
    for case in cases:
        r = result_by_id.get(case.benchmark_case_id, {})
        src = case.source_id or (
            "first_principles_analytical_identity"
            if case.is_first_principles()
            else "physics_oracle"
        )
        lines.append(
            "| {tid} | {src} | {doi} | {dom} | {typ} | {exp} | {res} | {scope} |".format(
                tid=case.benchmark_case_id,
                src=src,
                doi=case.DOI or "—",
                dom=case.measurement_domain or "—",
                typ=case.expected_output_type,
                exp=str(case.expected)[:60].replace("|", "/"),
                res=r.get("classification", "not_run_in_matrix_writer"),
                scope="within" if case.direct_numerical_comparison_allowed else "scope/qualitative",
            )
        )
    if validation["errors"]:
        lines.extend(["", "## Validation errors", ""])
        lines.extend(f"- {e}" for e in validation["errors"])
    if validation["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in validation["warnings"])
    else:
        lines.extend(["", "## Warnings", "", "_None._", ""])
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_limitations_report(path: Path | str | None = None) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "acoustic_model_limitations.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    implemented = [d.descriptor_id for d in list_implemented_descriptors()]
    unsupported = [d.descriptor_id for d in load_descriptor_registry().all() if not d.implemented]
    out.write_text(
        "\n".join(
            [
                "# Acoustic model limitations (stress-test view)",
                "",
                f"Generated: {_utc_now()}",
                "",
                "- EWSD is precomputed $\\Phi(D)=D$; not recomputed from audio.",
                "- Active literature density parameters: **0**.",
                f"- Implemented acoustic descriptors: {', '.join(f'`{d}`' for d in implemented)}.",
                f"- Unsupported descriptors (scope safeguard only): {', '.join(f'`{d}`' for d in unsupported)}.",
                "- Harmonic sounding frequency $f_n=n f_0$: first-principles oracle; not a ProductionInstruction auto-fill.",
                "- Schelleng boundary: **not implemented**.",
                "- Mute attenuation $= f(\\mathrm{mass})$: **refused**.",
                "- Cross-domain centroid equivalence: **refused** (`not_comparable`).",
                "- Secondary synthesis must not activate EWSD.",
                "- Real-audio validation: **absent** (no local verified audio; no ecological-validity claim).",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out


def write_reproducibility_report(
    path: Path | str | None = None,
    *,
    pytest_summary: dict[str, Any] | None = None,
) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "reproducibility_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    env = environment_block()
    identity = load_source_identity_registry()
    lines = [
        "# Reproducibility report",
        "",
        f"Generated: {env['generated_at_utc']}",
        "",
        "## Environment",
        "",
        f"- Python: {env['python']}",
        f"- Platform: {env['platform']}",
        f"- Machine: {env['machine']}",
        "",
        "## Source identity hashes (verified / partial)",
        "",
    ]
    for e in identity.list_entries():
        if e.validation_status in {"verified_identity", "partial_identity_match"}:
            lines.append(
                f"- `{e.entry_id}`: `{e.file_hash_sha256}` ({e.validation_status})"
            )
    lines.extend(
        [
            "",
            "## Pytest summary",
            "",
            f"```json\n{pytest_summary}\n```" if pytest_summary else "_Run stress_runner to populate._",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_results_report(
    path: Path | str | None = None,
    *,
    summary: dict[str, Any],
    failures: list[dict[str, Any]],
    category_totals: dict[str, Any] | None = None,
) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "acoustics_stress_results.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    env = environment_block()
    cats = category_totals or {}
    lines = [
        "# Acoustics stress results",
        "",
        f"Generated: {env['generated_at_utc']}",
        "",
        "## Executive summary",
        "",
        f"- total: {summary.get('total')}",
        f"- passed: {summary.get('passed')}",
        f"- failed: {summary.get('failed')}",
        f"- skipped: {summary.get('skipped')}",
        f"- xfailed: {summary.get('xfailed')}",
        f"- exit_code: {summary.get('exit_code')}",
        "",
        "## Separate totals",
        "",
        f"- scope-safeguard tests: {cats.get('scope_safeguard_tests', 'n/a')}",
        f"- numerical descriptor tests: {cats.get('numerical_descriptor_tests', 'n/a')}",
        f"- literature-alignment tests: {cats.get('literature_alignment_tests', 'n/a')}",
        f"- real-audio tests: {cats.get('real_audio_tests', 'n/a')}",
        "",
        "## Category breakdown",
        "",
        f"- infrastructure tests: {cats.get('infrastructure_tests', 'n/a')}",
        f"- mathematical exact tests: {cats.get('mathematical_exact_tests', 'n/a')}",
        f"- implemented descriptor tests: {cats.get('implemented_descriptor_tests', 'n/a')}",
        f"- literature comparisons: {cats.get('literature_comparisons', 'n/a')}",
        f"- measurement-domain exclusions: {cats.get('measurement_domain_exclusions', 'n/a')}",
        f"- real-audio tests: {cats.get('real_audio_tests', 'n/a')}",
        f"- unsupported descriptors (scope safeguard): {cats.get('unsupported_descriptor_safeguards', 'n/a')}",
        "",
        "Scope-safeguard wording: **descriptor unavailable — scope safeguard passed**.",
        "These are **not** counted as numerical acoustic validation.",
        "",
        "## Environment",
        "",
        f"- {env['platform']}",
        f"- Python {env['python']}",
        "",
        "## Failures",
        "",
    ]
    if not failures:
        lines.append("_None recorded by runner._")
    else:
        for f in failures:
            lines.append(
                f"- **{f.get('severity', 'unknown')}**: {f.get('test_id')} — {f.get('message')}"
            )
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_failures_report(
    path: Path | str | None = None,
    *,
    failures: list[dict[str, Any]],
) -> Path:
    out = resolve_path(path or PACKAGE_ROOT / "reports" / "stress_test_failures.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Stress test failures", "", f"Generated: {_utc_now()}", ""]
    if not failures:
        lines.append("No failures recorded.")
    else:
        for f in failures:
            lines.extend(
                [
                    f"## {f.get('test_id')}",
                    "",
                    f"- subsystem: {f.get('subsystem')}",
                    f"- severity: {f.get('severity')}",
                    f"- category: {f.get('category')}",
                    f"- message: {f.get('message')}",
                    f"- recommended_action: {f.get('recommended_action')}",
                    "",
                ]
            )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
