#!/usr/bin/env python3
"""Validate the documentation set.

The following checks are applied. Any failure causes the script to exit
with a non-zero code and a summary of failures.

1. Broken relative Markdown links in every file under ``docs/`` plus
   ``README.md``.
2. Unbalanced ``$$`` display math delimiters and rough ``$`` parity in
   text outside fenced code blocks and inline code spans.
3. Forbidden placeholders: ``TODO_DOC``, ``TBD_FORMULA``,
   ``lorem ipsum`` (case-insensitive).
4. Obsolete identifiers: ``harmonic_insufficient_metadata``.
5. Presence of the anchor documents ``docs/TECHNICAL_GUIDE.md`` and
   ``docs/DOCUMENTATION_INDEX.md``.

Usage::

    python tools/validate_documentation.py

The script prints a per-check summary and returns exit code 0 when all
checks pass, 1 otherwise.
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
README = ROOT / "README.md"

REQUIRED_DOCS = [
    DOCS_DIR / "TECHNICAL_GUIDE.md",
    DOCS_DIR / "DOCUMENTATION_INDEX.md",
]

FORBIDDEN_PLACEHOLDERS = [
    "TODO_DOC",
    "TBD_FORMULA",
    "lorem ipsum",
]

OBSOLETE_IDENTIFIERS = [
    "harmonic_insufficient_metadata",
]

# Markdown inline link pattern: [text](target)
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Fenced code block delimiter
_FENCE_RE = re.compile(r"^\s*```")


def _iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    if README.exists():
        files.append(README)
    if DOCS_DIR.exists():
        for path in sorted(DOCS_DIR.rglob("*.md")):
            files.append(path)
    return files


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans from ``text``."""
    lines = text.splitlines()
    kept: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept)


def _check_required_docs() -> list[str]:
    errors: list[str] = []
    for path in REQUIRED_DOCS:
        if not path.exists():
            errors.append(f"required document missing: {path.relative_to(ROOT)}")
    return errors


def _check_broken_links(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        for match in _LINK_RE.finditer(text):
            target = match.group(1).strip()
            # Strip Markdown link titles: e.g. `foo.md "title"`
            target = target.split(" ", 1)[0]
            if not target:
                continue
            # Skip absolute URLs and mail links
            scheme = urllib.parse.urlparse(target).scheme
            if scheme in {"http", "https", "mailto", "ftp"}:
                continue
            # Skip pure anchors
            if target.startswith("#"):
                continue
            # Strip fragment (anchor) portion
            local, _, _fragment = target.partition("#")
            if not local:
                continue
            resolved = (source.parent / local).resolve()
            if not resolved.exists():
                errors.append(
                    f"broken relative link in {source.relative_to(ROOT)}: '{target}' -> {resolved}"
                )
    return errors


def _check_math_delimiters(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in files:
        stripped = _strip_code(source.read_text(encoding="utf-8"))
        # Count $$ (display) occurrences; must be even
        display_count = stripped.count("$$")
        if display_count % 2 != 0:
            errors.append(
                f"unbalanced $$ display delimiters in {source.relative_to(ROOT)}: "
                f"count={display_count}"
            )
        # After removing $$ pairs, count remaining lone $ for rough parity
        without_display = stripped.replace("$$", "")
        # Escaped \$ do not count as math delimiters
        without_display = without_display.replace("\\$", "")
        inline_count = without_display.count("$")
        if inline_count % 2 != 0:
            errors.append(
                f"odd number of inline $ delimiters in {source.relative_to(ROOT)}: "
                f"count={inline_count}"
            )
    return errors


def _check_forbidden(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        lower = text.lower()
        for placeholder in FORBIDDEN_PLACEHOLDERS:
            if placeholder.lower() in lower:
                errors.append(
                    f"forbidden placeholder '{placeholder}' in {source.relative_to(ROOT)}"
                )
    return errors


def _check_obsolete_ids(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        for ident in OBSOLETE_IDENTIFIERS:
            if ident in text:
                errors.append(
                    f"obsolete identifier '{ident}' in {source.relative_to(ROOT)}"
                )
    return errors


def main() -> int:
    files = _iter_markdown_files()
    if not files:
        print("No documentation files found.")
        return 1

    checks: list[tuple[str, list[str]]] = [
        ("required documents", _check_required_docs()),
        ("relative link resolution", _check_broken_links(files)),
        ("math delimiter parity", _check_math_delimiters(files)),
        ("forbidden placeholders", _check_forbidden(files)),
        ("obsolete identifiers", _check_obsolete_ids(files)),
    ]

    total_errors = 0
    print("Documentation validation")
    print(f"  files inspected: {len(files)}")
    print()
    for name, errors in checks:
        status = "OK" if not errors else f"FAIL ({len(errors)})"
        print(f"  [{status}] {name}")
        for error in errors:
            print(f"      - {error}")
        total_errors += len(errors)
    print()

    if total_errors:
        print(f"FAILED: {total_errors} error(s) across {len(files)} file(s).")
        return 1

    print(f"PASSED: {len(files)} file(s) inspected, no errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
