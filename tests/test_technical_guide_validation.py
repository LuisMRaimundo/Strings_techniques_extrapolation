"""Documentation validation for docs/TECHNICAL_GUIDE.md."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "validate_technical_guide.py"
_spec = importlib.util.spec_from_file_location("validate_technical_guide", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_technical_guide"] = _mod
_spec.loader.exec_module(_mod)
GUIDE = _mod.GUIDE
validate = _mod.validate


def test_technical_guide_exists() -> None:
    assert GUIDE.exists()
    text = GUIDE.read_text(encoding="utf-8")
    assert len(text) > 10_000


def test_technical_guide_uses_latex_delimiters() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert "$$" in text
    assert r"\beta" in text or r"$\beta$" in text
    assert r"\Phi" in text or r"$\Phi$" in text


def test_technical_guide_validation_script_passes() -> None:
    errors = validate()
    assert errors == [], errors


def test_guide_sections_present() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    for heading in (
        "## 2. Purpose and research scope",
        "## 8. Pitch registry and formulas",
        "## 11. EWSD score and the identity metric",
        "## 14. Automatic model selection",
        "## 18. Bow-contact model",
        "## 20. Harmonic register generator",
        "## Appendix A: Formula inventory",
        "## Appendix B: Code-to-documentation traceability matrix",
        "## Appendix D: Production instructions, Phase-4 prediction, and literature sources",
    ):
        assert heading in text


def test_assets_exist() -> None:
    assets = Path("docs/technical_guide_assets")
    for name in (
        "architecture.mmd",
        "applicability_flowchart.mmd",
        "prediction_sequence.mmd",
        "evidence_provenance.mmd",
        "config_dependency.mmd",
        "README.md",
    ):
        assert (assets / name).exists()
