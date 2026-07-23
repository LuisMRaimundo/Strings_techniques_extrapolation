"""Real-audio validation status — no silent downloads."""

from __future__ import annotations

from pathlib import Path

import pytest

from string_technique_model.config import PACKAGE_ROOT

pytestmark = pytest.mark.acoustics_stress

_AUDIO_GLOBS = ("*.wav", "*.flac", "*.aiff", "*.aif", "*.mp3")


def _local_verified_audio() -> list[Path]:
    roots = [
        PACKAGE_ROOT / "literature",
        PACKAGE_ROOT / "data",
        PACKAGE_ROOT / "datasets",
        PACKAGE_ROOT / "audio",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in _AUDIO_GLOBS:
            found.extend(root.rglob(pattern))
    return found


@pytest.mark.literature_bounded
def test_real_audio_validation_absent_locally() -> None:
    """If no verified local audio accompanies articles/datasets, state absence honestly."""
    audio = _local_verified_audio()
    assert audio == [], (
        "Unexpected local audio found; wire optional adapters only after explicit curation: "
        + ", ".join(str(p) for p in audio[:5])
    )
    # Real-audio validation is absent — do not claim ecological validity.
    status = "absent"
    ecological_validity_claimed = False
    assert status == "absent"
    assert ecological_validity_claimed is False
