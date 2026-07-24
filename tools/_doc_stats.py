"""Print documentation file sizes and TECHNICAL_GUIDE heading inventory."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md",
    "docs/TECHNICAL_GUIDE.md",
    "docs/DOCUMENTATION_INDEX.md",
    "docs/USER_GUIDE.md",
    "docs/CLI_REFERENCE.md",
    "docs/GUI_REFERENCE.md",
    "docs/CONFIGURATION_REFERENCE.md",
    "docs/DATA_SCHEMA_REFERENCE.md",
    "docs/EXCEL_OUTPUT_REFERENCE.md",
    "docs/SCIENTIFIC_LIMITATIONS.md",
    "docs/GLOSSARY.md",
    "docs/NONLINEAR_EXTRAPOLATION.md",
    "reports/documentation_audit.md",
    "tools/validate_documentation.py",
]


def main() -> None:
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"MISSING  {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        n_lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        print(f"{path.stat().st_size / 1024:7.1f} KB  lines={n_lines:5d}  {rel}")
    guide = (ROOT / "docs/TECHNICAL_GUIDE.md").read_text(encoding="utf-8")
    heads = [ln for ln in guide.splitlines() if ln.startswith("## ")]
    print(f"\nTECHNICAL_GUIDE ## headings: {len(heads)}")
    for h in heads:
        print(h)
    print(f"\n$$ count: {guide.count('$$')}")
    print(f"bad mmd image embed: {'![General architecture](technical_guide_assets/architecture.mmd)' in guide}")


if __name__ == "__main__":
    main()
