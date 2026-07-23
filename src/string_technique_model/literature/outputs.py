"""Write literature-layer CSV/Markdown/BibTeX artefacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd


def write_csv(path: Path, rows: list[dict[str, Any]], *, columns: list[str] | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        frame = pd.DataFrame(rows)
    elif columns:
        frame = pd.DataFrame(columns=columns)
    else:
        frame = pd.DataFrame()
    # Quote non-numerics so evidence_grade "NA" is not read as missing by pandas.
    frame.to_csv(path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return str(path)


def write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)
