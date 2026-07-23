"""Advanced / Tools windows — scientific machinery kept off the main screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


def open_advanced_tools(master: tk.Misc, *, run_config_path: tk.StringVar | None = None) -> None:
    """Open legacy lookup/pipeline + metric entry in a separate Toplevel."""
    win = tk.Toplevel(master)
    win.title("Advanced tools — scientific / developer")
    win.geometry("1100x760")
    win.minsize(900, 600)

    note = ttk.Label(
        win,
        text=(
            "These tools expose prediction, literature, descriptors, and developer diagnostics. "
            "Ordinary metadata entry does not require this window."
        ),
        wraplength=1000,
    )
    note.pack(fill=tk.X, padx=10, pady=8)

    try:
        from string_technique_model.gui_legacy import LegacyScientificApp

        frame = LegacyScientificApp(win, run_config_path=run_config_path)
        frame.pack(fill=tk.BOTH, expand=True)
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("Advanced tools unavailable", str(exc), parent=win)
        ttk.Label(win, text=f"Could not load advanced tools:\n{exc}").pack(padx=12, pady=12)
