"""Main GUI: manually enter whole-register values, then request techniques by note."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.gui_metadata.register_grid import RegisterGrid, RequestGrid

_DEFAULT_OUT = PACKAGE_ROOT / "outputs" / "extrapolation" / "note_level_requests.xlsx"

# UI checkbox order matches result blocks: sordino first, then tasto, ponticello, harmonics
_TECHNIQUES = ("con_sordino", "sul_tasto", "sul_ponticello", "artificial_harmonic", "natural_harmonic")

_RESULT_COLUMNS = [
    "request_technique",
    "request_note",
    "instrument",
    "dynamic",
    "baseline_value",
    "value",
    "lower_bound",
    "upper_bound",
    "value_kind",
    "qualitative_effect_vs_ordinary",
    "attenuation_db_power",
    "extrapolation_method",
    "warnings",
]


def _adapt_nonlinear_result_for_grid(r: Any) -> dict[str, Any]:
    """Map ExtrapolationResult → GUI/note-level row without dropping audit fields."""
    row = r.to_row() if hasattr(r, "to_row") else dict(r)
    # Aliases expected by the results grid / older note-level sheets
    row["request_technique"] = r.technique
    row["request_note"] = r.pitch
    # Prefer frequentist estimate_* / interval_* (production path). Bayesian
    # posterior_* / credible_interval_* stay None unless a Bayesian backend ran.
    value = (
        r.estimate_median
        if getattr(r, "estimate_median", None) is not None
        else getattr(r, "estimate_mean", None)
    )
    if value is None:
        value = r.posterior_median if r.posterior_median is not None else r.posterior_mean
    low = getattr(r, "interval_low", None)
    if low is None:
        low = r.credible_interval_low
    high = getattr(r, "interval_high", None)
    if high is None:
        high = r.credible_interval_high
    row["value"] = value
    row["lower_bound"] = low
    row["upper_bound"] = high
    row["extrapolation_method"] = r.selected_model_id or r.model_id
    # Keep list fields as lists for export_note_level_workbook join; to_row already joined strings
    if hasattr(r, "assumptions_used"):
        row["assumptions_used"] = list(r.assumptions_used or [])
    if hasattr(r, "baseline_record_ids"):
        row["baseline_record_ids"] = list(r.baseline_record_ids or [])
    if hasattr(r, "warnings"):
        row["warnings"] = list(r.warnings or [])
    return row


class NarrowExtrapolatorApp(ttk.Frame):
    """Manual full-register entry → requests (note + technique) → results."""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.root = master
        self.pack(fill=tk.BOTH, expand=True)
        self.default_instrument = tk.StringVar(value="vla")
        self.default_dynamic = tk.StringVar(value="pp")
        self.start_note = tk.StringVar(value="G3")
        self.end_note = tk.StringVar(value="G7")
        self.output_path = tk.StringVar(value=str(_DEFAULT_OUT))
        self.status_text = tk.StringVar(
            value="Build note column (e.g. C3–C6), paste value column (70,623528 …), then request techniques."
        )
        self.tech_vars = {
            t: tk.BooleanVar(value=True)  # include harmonics by default so export is complete
            for t in _TECHNIQUES
        }
        self.extrapolation_method = tk.StringVar(value="hierarchical_spline")
        self.harmonic_sounding_min = tk.StringVar(value="")  # empty = instrument-derived physical min
        self.harmonic_sounding_max = tk.StringVar(value="C8")
        self.include_low_harmonics = tk.BooleanVar(value=True)
        self.use_physical_harmonic_range = tk.BooleanVar(value=True)
        self.harmonic_selection_mode = tk.StringVar(value="configured_physically_plausible_harmonics")
        self._last_result: dict[str, Any] | None = None
        self._last_nonlinear_results: list[Any] | None = None
        self._loaded_workbook_path: str | None = None
        self._import_run_id: str | None = None
        self._build()
        self.build_register()

    def _build(self) -> None:
        self.root.title(f"Manual register → technique requests  |  {PACKAGE_ROOT}")
        self.root.minsize(1100, 720)
        self.root.geometry("1280x840")
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        menubar = tk.Menu(self.root)
        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label="Save Measured register…", command=self.save_measured_excel)
        file_m.add_command(label="Load Measured register…", command=self.load_measured_excel)
        file_m.add_command(label="Export results to Excel…", command=self.export_results)
        file_m.add_command(label="Open last Excel export", command=self.open_last_export)
        file_m.add_separator()
        file_m.add_command(label="Reload calibration data", command=self.reload_calibration_data)
        file_m.add_command(label="Show calibration status…", command=self.show_calibration_status)
        file_m.add_separator()
        file_m.add_command(label="Return to start (edit & re-run)…", command=self.return_to_start)
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_m)
        self.root.configure(menu=menubar)

        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text=(
                "Column 1 = note names (C3…C6). Column 2 = your densities (European comma OK: 70,623528). "
                "Paste either values alone (in order) or note+value together. No audio."
            ),
            wraplength=1180,
        ).pack(anchor=tk.W)

        meta = ttk.Frame(self, padding=(10, 2))
        meta.pack(fill=tk.X)
        ttk.Label(meta, text="Instrument").pack(side=tk.LEFT)
        ttk.Combobox(
            meta,
            textvariable=self.default_instrument,
            values=["vln", "vla", "vlc", "cb"],
            width=8,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(meta, text="Dynamic").pack(side=tk.LEFT)
        ttk.Combobox(
            meta,
            textvariable=self.default_dynamic,
            values=["pp", "mf", "ff"],
            width=6,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(meta, text="From note").pack(side=tk.LEFT)
        start_e = ttk.Entry(meta, textvariable=self.start_note, width=6)
        start_e.pack(side=tk.LEFT, padx=(4, 8))
        start_e.bind("<Return>", lambda _e: self.build_register())
        ttk.Label(meta, text="To note").pack(side=tk.LEFT)
        end_e = ttk.Entry(meta, textvariable=self.end_note, width=6)
        end_e.pack(side=tk.LEFT, padx=(4, 12))
        end_e.bind("<Return>", lambda _e: self.build_register())
        ttk.Button(meta, text="Build note column", command=self.build_register).pack(side=tk.LEFT, padx=4)
        ttk.Button(meta, text="Paste notes and/or values", command=self.paste_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(meta, text="Clear values", command=self.clear_values).pack(side=tk.LEFT, padx=4)
        ttk.Label(meta, text="Extrapolation method").pack(side=tk.LEFT, padx=(16, 4))
        ttk.Combobox(
            meta,
            textvariable=self.extrapolation_method,
            values=[
                "hierarchical_spline",
                "constant",
                "physical_informed_bayesian",
                "evidence_only",
            ],
            width=26,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        next_bar = ttk.LabelFrame(self, text="Next steps", padding=8)
        next_bar.pack(fill=tk.X, padx=10, pady=(6, 0))
        self.next_steps_text = tk.StringVar()
        ttk.Label(next_bar, textvariable=self.next_steps_text, wraplength=820, justify=tk.LEFT).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            next_bar,
            text="← Return to start",
            command=self.return_to_start,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Button(next_bar, text="▶ Do next step", command=self.do_next_step).pack(side=tk.RIGHT, padx=4)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        # --- Tab: Measured register ---
        tab_m = ttk.Frame(self.nb)
        self.nb.add(tab_m, text="1. Measured register (type values)")
        m_hint = ttk.Frame(tab_m)
        m_hint.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            m_hint,
            text=(
                "Notes ARE editable: double-click a note cell, or paste a note column / note+value. "
                "After changing From/To, click Build note column (or press Enter)."
            ),
            wraplength=900,
        ).pack(side=tk.LEFT)
        ttk.Button(
            m_hint,
            text="Next → 2. Choose techniques & generate requests",
            command=self.go_step2,
        ).pack(side=tk.RIGHT)
        self.register_grid = RegisterGrid(
            tab_m,
            on_change=self._on_register_change,
            get_instrument=self.default_instrument.get,
            get_dynamic=self.default_dynamic.get,
        )
        self.register_grid.pack(fill=tk.BOTH, expand=True)

        # --- Tab: Requests ---
        tab_r = ttk.Frame(self.nb)
        self.nb.add(tab_r, text="2. Requests (notes + techniques)")
        ttk.Label(
            tab_r,
            text=(
                "Step 2: tick the techniques you want (sul tasto / sul ponticello / con sordino / …), "
                "then click Generate. That creates one request per filled note × technique."
            ),
            wraplength=1100,
        ).pack(anchor=tk.W, pady=(0, 4))
        tech_bar = ttk.LabelFrame(tab_r, text="Techniques to request for ALL filled notes", padding=6)
        tech_bar.pack(fill=tk.X, pady=4)
        for t in _TECHNIQUES:
            ttk.Checkbutton(tech_bar, text=t, variable=self.tech_vars[t]).pack(side=tk.LEFT, padx=6)
        ttk.Button(tech_bar, text="Generate from filled register", command=self.generate_requests).pack(
            side=tk.RIGHT, padx=4
        )
        harm_bar = ttk.LabelFrame(
            tab_r,
            text="Harmonic output range (sounding pitches from strings×orders — not ordinary copy)",
            padding=6,
        )
        harm_bar.pack(fill=tk.X, pady=4)
        ttk.Checkbutton(
            harm_bar,
            text="Use physically available harmonic range",
            variable=self.use_physical_harmonic_range,
            command=self._sync_harmonic_mode,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Label(harm_bar, text="From").pack(side=tk.LEFT)
        ttk.Entry(harm_bar, textvariable=self.harmonic_sounding_min, width=8).pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(harm_bar, text="To").pack(side=tk.LEFT)
        ttk.Entry(harm_bar, textvariable=self.harmonic_sounding_max, width=6).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(harm_bar, text="Mode").pack(side=tk.LEFT)
        ttk.Combobox(
            harm_bar,
            textvariable=self.harmonic_selection_mode,
            values=[
                "configured_physically_plausible_harmonics",
                "upper_register_only",
                "custom_sounding_range",
                "selected_harmonic_orders",
            ],
            width=32,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)
        req_btns = ttk.Frame(tab_r)
        req_btns.pack(fill=tk.X)
        ttk.Button(req_btns, text="Add empty request row", command=self.add_request_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            req_btns,
            text="Next → 3. Run & see results",
            command=self.go_step3,
        ).pack(side=tk.RIGHT, padx=2)
        self.request_grid = RequestGrid(tab_r, on_change=self._update_counts)
        self.request_grid.pack(fill=tk.BOTH, expand=True, pady=4)

        # --- Tab: Results ---
        tab_o = ttk.Frame(self.nb)
        self.nb.add(tab_o, text="3. Results")
        ttk.Label(
            tab_o,
            text=(
                "Step 3: Run requests. value = provisional density estimate from your ordinary baseline "
                "(sul tasto ↓, sul ponticello ↑, sordino scaled by mute dB). "
                "Edit factors in configs/extrapolation/provisional_density_effects_v1.yaml."
            ),
            wraplength=1100,
        ).pack(anchor=tk.W, pady=(0, 4))
        run_bar = ttk.Frame(tab_o)
        run_bar.pack(fill=tk.X, pady=4)
        ttk.Button(run_bar, text="Run requests", command=self.run_requests).pack(side=tk.LEFT, padx=2)
        ttk.Button(run_bar, text="Export to Excel…", command=self.export_results).pack(side=tk.LEFT, padx=2)
        ttk.Button(run_bar, text="Open Excel", command=self.open_last_export).pack(side=tk.LEFT, padx=2)
        ttk.Button(run_bar, text="← Return to start", command=self.return_to_start).pack(side=tk.LEFT, padx=8)
        ttk.Entry(run_bar, textvariable=self.output_path, width=56).pack(side=tk.LEFT, padx=8)
        ttk.Label(
            tab_o,
            text="Rows are grouped: all con_sordino, then all sul_tasto, then sul_ponticello, then harmonics.",
            foreground="#444",
        ).pack(anchor=tk.W)
        self.result_tree = ttk.Treeview(tab_o, columns=_RESULT_COLUMNS, show="headings", height=20)
        for col in _RESULT_COLUMNS:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=100 if col != "warnings" else 200, stretch=True)
        yscroll = ttk.Scrollbar(tab_o, orient=tk.VERTICAL, command=self.result_tree.yview)
        xscroll = ttk.Scrollbar(tab_o, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        status = ttk.Frame(self, padding=(10, 6))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        self.counts_text = tk.StringVar(value="Register notes: 0 | Filled values: 0 | Requests: 0")
        ttk.Label(status, textvariable=self.counts_text).pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.status_text).pack(side=tk.RIGHT)

    def build_register(self) -> None:
        from string_technique_model.extrapolation.register_builder import build_empty_register

        try:
            rows = build_empty_register(
                self.default_instrument.get(),
                self.default_dynamic.get(),
                start_note=self.start_note.get().strip() or None,
                end_note=self.end_note.get().strip() or None,
            )
        except ValueError as exc:
            messagebox.showerror("Note range", str(exc), parent=self.root)
            return
        self.register_grid.set_rows(rows)
        self._update_counts()
        self.status_text.set(
            f"Note column {self.start_note.get()}…{self.end_note.get()}: "
            f"{len(rows)} notes — paste your value column (e.g. 70,623528)."
        )
        self.nb.select(0)

    def clear_values(self) -> None:
        rows = self.register_grid.get_rows()
        for r in rows:
            r["value"] = None
        self.register_grid.set_rows(rows)
        self._update_counts()

    def _on_register_change(self) -> None:
        rows = self.register_grid.get_rows()
        if rows:
            self.start_note.set(str(rows[0].get("note") or self.start_note.get()))
            self.end_note.set(str(rows[-1].get("note") or self.end_note.get()))
        self._update_counts()

    def paste_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Paste notes and/or values")
        win.geometry("560x520")
        ttk.Label(
            win,
            text=(
                "Paste ONE of these:\n"
                "1) note + value (tab-separated) — your notes ARE accepted and become the register:\n"
                "     G3\\t70,623528\n"
                "     G#3\\t38,554306\n"
                "2) values only — fills the current note column in order (Build G3→G7 first).\n"
                "3) notes only — rebuilds the note column from your list.\n"
                "European commas OK."
            ),
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=8, pady=6)
        text = tk.Text(win, height=22)
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        text.focus_set()

        def apply() -> None:
            raw = text.get("1.0", tk.END)
            if "(… paste" in raw or not raw.strip():
                messagebox.showinfo("Paste", "Clear the box and paste your real data.", parent=win)
                return
            # Ensure From/To build is applied before value-only paste
            from string_technique_model.extrapolation.register_builder import (
                parse_pasted_note_value_table,
                parse_pasted_values,
            )

            notes, _vals, _w = parse_pasted_note_value_table(raw)
            has_notes = any(notes)
            if not has_notes:
                # value-only: rebuild from From/To so G3→G7 is respected
                self.build_register()
                n_reg = len(self.register_grid.get_rows())
                n_vals = sum(1 for v in parse_pasted_values(raw) if v is not None)
                if n_vals != n_reg:
                    messagebox.showwarning(
                        "Length mismatch",
                        f"Pasted {n_vals} values but note column has {n_reg} notes "
                        f"({self.start_note.get()}→{self.end_note.get()}).\n"
                        "Fix From/To and Build, or paste note+value together.",
                        parent=win,
                    )
            warnings = self.register_grid.paste_values(raw, start_from_selection=False)
            rows = self.register_grid.get_rows()
            if rows:
                self.start_note.set(str(rows[0].get("note") or ""))
                self.end_note.set(str(rows[-1].get("note") or ""))
            self._update_counts()
            self.status_text.set("; ".join(warnings) if warnings else "Paste applied")
            messagebox.showinfo(
                "Accepted",
                f"Notes in table: {len(rows)}\nFilled values: "
                f"{sum(1 for r in rows if r.get('value') is not None)}\n\n"
                + ("\n".join(warnings[:4]) if warnings else "OK"),
                parent=win,
            )
            win.destroy()

        ttk.Button(win, text="Accept pasted notes / values", command=apply).pack(pady=8)

    def return_to_start(self) -> None:
        """Go back to step 1 to edit data / techniques and run a new analysis.

        Keeps the measured register values. Clears previous requests, results,
        and in-memory run state so Generate → Run starts clean.
        """
        has_results = self._last_result is not None or self._last_nonlinear_results is not None
        has_requests = bool(self.request_grid.get_rows())
        if has_results or has_requests:
            ok = messagebox.askyesno(
                "Return to start",
                "Go back to step 1?\n\n"
                "• Measured register values are kept (you can edit them).\n"
                "• Previous requests and results will be cleared.\n"
                "• Then regenerate requests and run a new analysis.",
                parent=self.root,
            )
            if not ok:
                return

        self._last_result = None
        self._last_nonlinear_results = None
        self.request_grid.set_rows([])
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        self.nb.select(0)
        filled = sum(1 for r in self.register_grid.get_rows() if r.get("value") is not None)
        self.status_text.set(
            "Back at start: edit register values or instrument/dynamic, then ▶ Do next step "
            f"({filled} filled notes kept)."
        )
        self._update_counts()

    def go_step2(self) -> None:
        filled = sum(1 for r in self.register_grid.get_rows() if r.get("value") is not None)
        if filled == 0:
            messagebox.showinfo(
                "Step 1 incomplete",
                "Paste/type density values in tab 1 first (you already have the note column).",
                parent=self.root,
            )
            self.nb.select(0)
            return
        self.nb.select(1)
        self.status_text.set(
            f"Step 2: tick techniques, then Generate from filled register ({filled} notes ready)."
        )
        self._update_counts()

    def go_step3(self) -> None:
        if not self.request_grid.get_rows():
            self.generate_requests()
        if not self.request_grid.get_rows():
            return
        self.nb.select(2)
        self.status_text.set("Step 3: click Run requests, then Export results Excel.")
        self._update_counts()

    def do_next_step(self) -> None:
        """One-click advance through 1→2→3."""
        filled = sum(1 for r in self.register_grid.get_rows() if r.get("value") is not None)
        n_req = len(self.request_grid.get_rows())
        if filled == 0:
            self.nb.select(0)
            messagebox.showinfo(
                "Next step",
                "Step 1: paste your density column into the value cells (you already did the notes).",
                parent=self.root,
            )
            return
        if n_req == 0:
            self.go_step2()
            # auto-generate with currently ticked techniques
            self.generate_requests()
            return
        if self._last_result is None:
            self.go_step3()
            self.run_requests()
            return
        messagebox.showinfo(
            "Done",
            "All steps finished. Use Export results Excel, or change techniques and Run again.",
            parent=self.root,
        )

    def _sync_harmonic_mode(self) -> None:
        if self.use_physical_harmonic_range.get():
            self.harmonic_selection_mode.set("configured_physically_plausible_harmonics")
            self.harmonic_sounding_min.set("")
            self.include_low_harmonics.set(True)
        else:
            self.harmonic_selection_mode.set("custom_sounding_range")
            if not self.harmonic_sounding_min.get().strip():
                self.harmonic_sounding_min.set("C6")
            self.include_low_harmonics.set(False)

    def _harmonic_kwargs(self) -> dict[str, Any]:
        mode = self.harmonic_selection_mode.get().strip() or "configured_physically_plausible_harmonics"
        if self.use_physical_harmonic_range.get():
            mode = "configured_physically_plausible_harmonics"
        return {
            "harmonic_sounding_min": self.harmonic_sounding_min.get().strip() or None,
            "harmonic_sounding_max": self.harmonic_sounding_max.get().strip() or "C8",
            "include_low_harmonics": bool(
                self.use_physical_harmonic_range.get() or self.include_low_harmonics.get()
            ),
            "harmonic_selection_mode": mode,
        }

    def generate_requests(self) -> None:
        from string_technique_model.extrapolation.register_builder import (
            generate_requests_for_register,
            measured_with_values_only,
        )

        measured = measured_with_values_only(self.register_grid.get_rows())
        techs = [t for t, var in self.tech_vars.items() if var.get()]
        if not measured:
            messagebox.showinfo("Requests", "Fill at least one register value first.", parent=self.root)
            return
        if not techs:
            messagebox.showinfo("Requests", "Select at least one technique.", parent=self.root)
            return
        hk = self._harmonic_kwargs()
        requests = generate_requests_for_register(
            measured,
            techs,
            harmonic_sounding_min=hk["harmonic_sounding_min"],
            harmonic_sounding_max=hk["harmonic_sounding_max"],
            include_low_harmonics=hk["include_low_harmonics"],
            harmonic_selection_mode=hk["harmonic_selection_mode"],
        )
        self.request_grid.set_rows(requests)
        self._update_counts()
        n_harm = sum(1 for r in requests if str(r.get("technique", "")).endswith("harmonic"))
        self.status_text.set(
            f"Step 2 done: {len(requests)} requests "
            f"({len(measured)} ordinary notes; {n_harm} harmonic sounding targets). Next → Run in tab 3."
        )
        self.nb.select(1)

    def add_request_row(self) -> None:
        self.request_grid.add_empty_row(
            instrument=self.default_instrument.get(),
            dynamic=self.default_dynamic.get(),
        )
        self._update_counts()

    def _measured_filled(self) -> list[dict[str, Any]]:
        from string_technique_model.extrapolation.register_builder import measured_with_values_only

        rows = self.register_grid.get_rows()
        # refresh instrument/dynamic on all rows from defaults
        for r in rows:
            r["instrument"] = self.default_instrument.get()
            r["dynamic"] = self.default_dynamic.get()
        return measured_with_values_only(rows)

    def run_requests(self) -> None:
        measured = self._measured_filled()
        requests = self.request_grid.get_rows()
        if not requests:
            self.generate_requests()
            requests = self.request_grid.get_rows()
        if not measured or not requests:
            messagebox.showinfo(
                "Missing data",
                "Type values into the full register, then generate or enter requests.",
                parent=self.root,
            )
            return
        for req in requests:
            req["instrument"] = req.get("instrument") or self.default_instrument.get()
            req["dynamic"] = req.get("dynamic") or self.default_dynamic.get()

        method = self.extrapolation_method.get().strip() or "hierarchical_spline"
        try:
            if method == "constant":
                from string_technique_model.extrapolation.note_level import (
                    export_note_level_workbook,
                    run_note_level_requests,
                )

                result = run_note_level_requests(measured, requests)
                out = export_note_level_workbook(result, self.output_path.get().strip() or _DEFAULT_OUT)
                self.output_path.set(str(out))
                self._last_result = result
                self._last_nonlinear_results = None
                self._fill_results(result["results"])
                s = result["summary"]
                self.status_text.set(
                    f"M0 constant | Matched {s['n_matched_baseline']}/{s['n_requests']} | "
                    f"numeric: {s['n_numeric_value']} → {out}"
                )
            else:
                from string_technique_model.extrapolation.nonlinear import (
                    export_nonlinear_workbook,
                    predict_register,
                )
                from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
                    clear_harmonic_calibration_cache,
                )
                from string_technique_model.extrapolation.register_builder import TECHNIQUE_SORT_ORDER

                # Always reload measured CSVs so GUI does not serve a stale cache.
                clear_harmonic_calibration_cache()

                techs = []
                for t in TECHNIQUE_SORT_ORDER:
                    if any(str(r.get("technique")) == t for r in requests):
                        techs.append(t)
                for r in requests:
                    t = str(r.get("technique"))
                    if t not in techs:
                        techs.append(t)

                # Stamp provenance on measured rows for auditability
                for m in measured:
                    if self._loaded_workbook_path:
                        m.setdefault("source_workbook_path", self._loaded_workbook_path)
                        m.setdefault("data_status", "measured_research_data")
                        m.setdefault("scientific_use", "allowed_with_workbook_provenance")
                    if self._import_run_id:
                        m.setdefault("import_run_id", self._import_run_id)
                    if not m.get("data_status") and m.get("source_path"):
                        m["data_status"] = "measured_real"
                    if not m.get("data_status"):
                        m["data_status"] = "manual_register_entry"
                        m.setdefault(
                            "scientific_use",
                            "requires_source_workbook_for_doctoral_evidence",
                        )
                        m.setdefault(
                            "source_path",
                            f"gui_manual_entry::{m.get('note')}::{self.default_instrument.get()}",
                        )
                hk = self._harmonic_kwargs()
                all_nl = []
                for tech in techs:
                    all_nl.extend(
                        predict_register(
                            measured,
                            technique=tech,
                            instrument=self.default_instrument.get(),
                            dynamic=self.default_dynamic.get(),
                            method=method,  # type: ignore[arg-type]
                            target_quantity="EWSD_score_acoustic_balanced",
                            **hk,
                        )
                    )
                nl_out = Path(self.output_path.get().strip() or _DEFAULT_OUT)
                # Prefer audit workbook name; keep user path if already nonlinear_*
                if "nonlinear" not in nl_out.name.lower():
                    nl_out = nl_out.with_name("nonlinear_extrapolation_results.xlsx")
                out = export_nonlinear_workbook(
                    all_nl,
                    nl_out,
                    run_metadata={
                        "requested_method": "automatic" if method == "hierarchical_spline" else method,
                        "gui_displayed_method": method,
                        "effective_selection_mode": "automatic"
                        if method == "hierarchical_spline"
                        else method,
                        "harmonic_sounding_min": self.harmonic_sounding_min.get(),
                        "harmonic_sounding_max": self.harmonic_sounding_max.get(),
                        "include_low_harmonics": self.include_low_harmonics.get(),
                    },
                )
                self.output_path.set(str(out))
                self._last_nonlinear_results = all_nl
                adapted = [_adapt_nonlinear_result_for_grid(r) for r in all_nl]
                from string_technique_model.extrapolation.note_level import sort_results_by_technique

                adapted = sort_results_by_technique(adapted)
                self._last_result = {
                    "results": adapted,
                    "summary": {
                        "n_requests": len(adapted),
                        "requested_method": "automatic" if method == "hierarchical_spline" else method,
                        "gui_method_control": method,
                    },
                }
                self._fill_results(adapted)
                n_num = sum(1 for a in adapted if a.get("value") is not None)
                self.status_text.set(
                    f"automatic selection | rows: {len(adapted)} | numeric: {n_num} → {out}"
                )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Run failed", str(exc), parent=self.root)
            return
        self.nb.select(2)

    def _fill_results(self, rows: list[dict[str, Any]]) -> None:
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for r in rows:
            values = []
            for c in _RESULT_COLUMNS:
                v = r.get(c)
                if isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                values.append("" if v is None else str(v))
            self.result_tree.insert("", tk.END, values=values)

    def save_measured_excel(self) -> None:
        import pandas as pd

        path = filedialog.asksaveasfilename(
            title="Save Measured register",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        rows = self.register_grid.get_rows()
        for r in rows:
            r["instrument"] = self.default_instrument.get()
            r["dynamic"] = self.default_dynamic.get()
        frame = pd.DataFrame(
            [
                {
                    "note": r.get("note"),
                    "midi": r.get("midi"),
                    "value": r.get("value"),
                    "instrument": r.get("instrument"),
                    "dynamic": r.get("dynamic"),
                    "technique": r.get("technique") or "ordinary",
                    "quantity": r.get("quantity") or "EWSD_score_acoustic_balanced",
                }
                for r in rows
            ]
        )
        reqs = self.request_grid.get_rows()
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name="Measured", index=False)
            pd.DataFrame(reqs or [{"note": "", "technique": "", "instrument": "", "dynamic": ""}]).to_excel(
                writer, sheet_name="Requests", index=False
            )
        self.status_text.set(f"Saved register: {path}")

    def load_measured_excel(self) -> None:
        import hashlib
        import uuid
        from pathlib import Path as _Path

        from string_technique_model.extrapolation.register_builder import (
            build_empty_register,
            merge_values_into_register,
        )
        from string_technique_model.extrapolation.request_io import load_request_workbook

        path = filedialog.askopenfilename(title="Load Measured register", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        measured, requests, warnings = load_request_workbook(
            path,
            default_instrument=self.default_instrument.get(),
            default_dynamic=self.default_dynamic.get(),
        )
        self._loaded_workbook_path = str(_Path(path).resolve())
        self._import_run_id = uuid.uuid4().hex[:12]
        try:
            digest = hashlib.sha256(_Path(path).read_bytes()).hexdigest()[:16]
        except OSError:
            digest = None
        if measured:
            inst = measured[0].get("instrument") or self.default_instrument.get()
            dyn = measured[0].get("dynamic") or self.default_dynamic.get()
            self.default_instrument.set(inst)
            self.default_dynamic.set(dyn)
            empty = build_empty_register(inst, dyn)
            by_note = {str(m["note"]): float(m["value"]) for m in measured if m.get("value") is not None}
            merged = merge_values_into_register(empty, by_note)
            for i, row in enumerate(merged):
                if row.get("value") is None:
                    continue
                row["source_workbook_path"] = self._loaded_workbook_path
                row["source_workbook_hash"] = digest
                row["source_sheet"] = "Measured"
                row["import_run_id"] = self._import_run_id
                row["data_status"] = "measured_research_data"
                row["source_path"] = f"{_Path(path).name}::Measured::{row.get('note')}::{i}"
            self.register_grid.set_rows(merged)
        if requests:
            self.request_grid.set_rows(requests)
        self._update_counts()
        self.status_text.set("; ".join(warnings[-2:]) if warnings else f"Loaded {path}")

    def export_results(self) -> None:
        if not self._last_result and not self._last_nonlinear_results:
            messagebox.showinfo("Export", "Run requests first (tab 3).", parent=self.root)
            return

        path = filedialog.asksaveasfilename(
            title="Export results to Excel",
            defaultextension=".xlsx",
            initialfile="nonlinear_extrapolation_results.xlsx"
            if self._last_nonlinear_results
            else "note_level_results.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            path = self.output_path.get().strip() or str(_DEFAULT_OUT)
        try:
            if self._last_nonlinear_results:
                from string_technique_model.extrapolation.nonlinear import export_nonlinear_workbook

                out = export_nonlinear_workbook(
                    self._last_nonlinear_results,
                    path,
                    run_metadata={
                        "requested_method": (self._last_result or {}).get("summary", {}).get(
                            "requested_method", "automatic"
                        ),
                        "gui_displayed_method": self.extrapolation_method.get(),
                        "effective_selection_mode": (self._last_result or {}).get("summary", {}).get(
                            "requested_method", "automatic"
                        ),
                        "source_workbook_path": self._loaded_workbook_path,
                        "import_run_id": self._import_run_id,
                    },
                )
            else:
                from string_technique_model.extrapolation.note_level import export_note_level_workbook

                out = export_note_level_workbook(self._last_result, path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc), parent=self.root)
            return
        self.output_path.set(str(out))
        self.status_text.set(f"Excel exported: {out}")
        if messagebox.askyesno(
            "Excel exported",
            f"Saved:\n{out}\n\nSheets include All_Results, Model_Selection_Audit, "
            "Run_Summary, and per-technique sheets.\n\nOpen the file now?",
            parent=self.root,
        ):
            self.open_last_export()

    def reload_calibration_data(self) -> None:
        """Invalidate cached harmonic calibration tables after measured CSVs change."""
        from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
            clear_harmonic_calibration_cache,
            coverage_counts,
            load_raw_harmonic_calibration_table,
            write_coverage_manifests,
        )

        clear_harmonic_calibration_cache()
        write_coverage_manifests()
        table = load_raw_harmonic_calibration_table()
        instruments = sorted(table["instrument"].unique()) if not table.empty else []
        msg = (
            f"Calibration cache cleared.\n"
            f"Loaded instruments: {', '.join(instruments) or '(none)'}\n"
            f"vln art mf notes: {coverage_counts('vln','artificial_harmonic','mf')}\n"
            f"vla art mf notes: {coverage_counts('vla','artificial_harmonic','mf')}\n"
            f"vlc art notes: {coverage_counts('vlc','artificial_harmonic')}\n"
            f"Cross-instrument transfer: disabled"
        )
        self.status_text.set(
            "Calibration reloaded | "
            f"instruments={','.join(instruments) or 'none'} | "
            f"vla_art_mf={coverage_counts('vla','artificial_harmonic','mf')}"
        )
        messagebox.showinfo("Calibration reloaded", msg, parent=self.root)

    def show_calibration_status(self) -> None:
        from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
            coverage_counts,
            load_raw_harmonic_calibration_table,
        )
        from string_technique_model.extrapolation.nonlinear.harmonic_support import (
            DEFAULT_ALLOW_CROSS_INSTRUMENT,
            DEFAULT_ALLOW_INTERPOLATION,
            DEFAULT_PROCESSING_VERSION,
        )

        table = load_raw_harmonic_calibration_table()
        lines = [
            f"PACKAGE_ROOT: {PACKAGE_ROOT}",
            f"SSA/EWSD version: {DEFAULT_PROCESSING_VERSION}",
            f"Interpolation enabled: {DEFAULT_ALLOW_INTERPOLATION}",
            f"Cross-instrument transfer enabled: {DEFAULT_ALLOW_CROSS_INSTRUMENT}",
            "",
            "Coverage (unique sounding pitches from measured tables):",
            f"  violin artificial mf: {coverage_counts('vln','artificial_harmonic','mf')}",
            f"  violin natural mf: {coverage_counts('vln','natural_harmonic','mf')}",
            f"  violin natural p: {coverage_counts('vln','natural_harmonic','p')}",
            f"  viola artificial mf: {coverage_counts('vla','artificial_harmonic','mf')}",
            f"  viola natural: {coverage_counts('vla','natural_harmonic')}",
            f"  cello artificial: {coverage_counts('vlc','artificial_harmonic')}",
            f"  cello natural: {coverage_counts('vlc','natural_harmonic')}",
        ]
        if not table.empty:
            combos = (
                table.groupby(["instrument", "technique", "dynamic", "collection"])
                .size()
                .reset_index(name="n")
            )
            lines.append("")
            lines.append("Loaded technique/dynamic/collection combinations:")
            for row in combos.itertuples(index=False):
                lines.append(
                    f"  {row.instrument} | {row.technique} | {row.dynamic} | "
                    f"{row.collection} | n={row.n}"
                )
        messagebox.showinfo("Calibration status", "\n".join(lines), parent=self.root)

    def open_last_export(self) -> None:
        path = Path(self.output_path.get().strip() or _DEFAULT_OUT)
        if not path.exists():
            messagebox.showinfo("Open Excel", f"File not found:\n{path}\nExport first.", parent=self.root)
            return
        try:
            import os

            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open failed", str(exc), parent=self.root)

    def _update_counts(self) -> None:
        rows = self.register_grid.get_rows()
        filled = sum(1 for r in rows if r.get("value") is not None)
        reqs = len(self.request_grid.get_rows())
        self.counts_text.set(f"Register notes: {len(rows)} | Filled values: {filled} | Requests: {reqs}")
        if filled == 0:
            self.next_steps_text.set(
                "NOW: paste densities into column “value”. Then click ▶ Do next step."
            )
        elif reqs == 0:
            self.next_steps_text.set(
                f"NOW (step 2): open tab “2. Requests”, tick sul_tasto / sul_ponticello / con_sordino, "
                f"click Generate — or press ▶ Do next step ({filled} notes ready)."
            )
        elif self._last_result is None:
            self.next_steps_text.set(
                f"NOW (step 3): open tab “3. Results” and click Run requests "
                f"— or press ▶ Do next step ({reqs} requests ready)."
            )
        else:
            self.next_steps_text.set(
                "DONE: Export Excel if needed. To change data or techniques, click ← Return to start."
            )

    # Compatibility for older smoke tests
    @property
    def _measured(self) -> list[dict[str, Any]]:
        return self._measured_filled()

    @property
    def _requests(self) -> list[dict[str, Any]]:
        return self.request_grid.get_rows()


def launch_extrapolator_gui() -> None:
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    NarrowExtrapolatorApp(root)
    root.mainloop()
