from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from string_technique_model.config import DEFAULT_RUN, PACKAGE_ROOT, load_run_config
from string_technique_model.data_io import (
    INSTRUMENT_DISPLAY,
    TECHNIQUE_DISPLAY,
    get_density,
    list_notes,
    load_all_baselines,
    load_holdout,
)
from string_technique_model.gui_manual_entry import ManualMetricEntryPanel
from string_technique_model.pipeline import lookup_single, run_pipeline


class LegacyScientificApp(ttk.Frame):
    """Legacy multi-panel scientific GUI (opened from Advanced / Tools only)."""

    def __init__(self, master: tk.Misc, *, run_config_path: tk.StringVar | None = None) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)

        self.config_path = run_config_path or tk.StringVar(value=str(DEFAULT_RUN))
        self.instrument = tk.StringVar(value="vln")
        self.technique = tk.StringVar(value="sul_ponticello")
        self.note = tk.StringVar(value="")
        self.dynamic = tk.StringVar(value="mf")
        self.status = tk.StringVar(value="Ready")
        self._baselines: dict = {}
        self._running = False

        self._build()
        self.reload_config()

    def _build(self) -> None:
        if isinstance(self.master, tk.Tk):
            self.master.title("Advanced — String Technique Density Model")
            self.master.minsize(960, 700)
            self.master.geometry("1100x760")

        style = ttk.Style(self.master)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
        style.configure("Muted.TLabel", foreground="#555555")

        header = ttk.Frame(self)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="Advanced scientific tools", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Prediction, literature, descriptors, and pipeline controls (not for ordinary metadata entry).",
            style="Muted.TLabel",
        ).pack(anchor=tk.W)
        self.baseline_collections = tk.StringVar(value="")

        cfg = ttk.LabelFrame(self, text="Configuration", padding=10)
        cfg.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(cfg, text="run.yaml").grid(row=0, column=0, sticky=tk.W)
        entry = ttk.Entry(cfg, textvariable=self.config_path)
        entry.grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(cfg, text="Browse…", command=self.browse_config).grid(row=0, column=2)
        ttk.Button(cfg, text="Reload", command=self.reload_config).grid(row=0, column=3, padx=(6, 0))
        cfg.columnconfigure(1, weight=1)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        lookup_tab = ttk.Frame(notebook)
        manual_tab = ttk.Frame(notebook)
        notebook.add(lookup_tab, text="Lookup / pipeline")
        notebook.add(manual_tab, text="Manual Metric Entry")
        self.manual_panel = ManualMetricEntryPanel(manual_tab, run_config_path=self.config_path)
        self.manual_panel.pack(fill=tk.BOTH, expand=True)

        body = ttk.Panedwindow(lookup_tab, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        select = ttk.LabelFrame(left, text="Selection", padding=10)
        select.pack(fill=tk.X)

        ttk.Label(select, text="Instrument").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.inst_combo = ttk.Combobox(
            select,
            textvariable=self.instrument,
            values=["vln", "vla", "vlc", "cb"],
            state="readonly",
            width=28,
        )
        self.inst_combo.grid(row=0, column=1, sticky=tk.EW, pady=3)
        self.inst_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_instrument_change())

        ttk.Label(select, text="Technique").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.tech_combo = ttk.Combobox(
            select,
            textvariable=self.technique,
            values=[
                "artificial_harmonic",
                "sul_ponticello",
                "sul_tasto",
                "con_sordino",
            ],
            state="readonly",
            width=28,
        )
        self.tech_combo.grid(row=1, column=1, sticky=tk.EW, pady=3)

        ttk.Label(select, text="Note").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.note_combo = ttk.Combobox(select, textvariable=self.note, state="readonly", width=28)
        self.note_combo.grid(row=2, column=1, sticky=tk.EW, pady=3)

        ttk.Label(select, text="Dynamic").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.dyn_combo = ttk.Combobox(
            select,
            textvariable=self.dynamic,
            values=["pp", "mf", "ff"],
            state="readonly",
            width=28,
        )
        self.dyn_combo.grid(row=3, column=1, sticky=tk.EW, pady=3)
        ttk.Label(select, text="Baselines").grid(row=4, column=0, sticky=tk.NW, pady=3)
        ttk.Label(select, textvariable=self.baseline_collections, wraplength=260).grid(
            row=4, column=1, sticky=tk.W, pady=3
        )
        select.columnconfigure(1, weight=1)

        actions = ttk.LabelFrame(left, text="Actions", padding=10)
        actions.pack(fill=tk.X, pady=10)
        ttk.Button(actions, text="Look up cell", command=self.lookup_cell).pack(fill=tk.X, pady=3)
        ttk.Button(actions, text="Show ordinary baseline table", command=self.show_baseline).pack(
            fill=tk.X, pady=3
        )
        ttk.Button(actions, text="Show holdout (if available)", command=self.show_holdout).pack(
            fill=tk.X, pady=3
        )
        ttk.Separator(actions).pack(fill=tk.X, pady=8)
        ttk.Button(actions, text="Run full pipeline", command=self.run_full).pack(fill=tk.X, pady=3)
        ttk.Button(actions, text="Open outputs folder", command=self.open_outputs).pack(
            fill=tk.X, pady=3
        )

        help_box = ttk.LabelFrame(left, text="Legend", padding=10)
        help_box.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            help_box,
            text=(
                "vln=Violin  vla=Viola  vlc=Cello  cb=Double bass\n\n"
                "Collections are discovered from configs/collections.yaml. "
                "Add a schema under configs/schemas/ — no code changes required.\n\n"
                "Literature parameters are currently empty, so technique cells "
                "return not_estimable_from_current_evidence until curated.\n\n"
                "Validation collections are isolated from calibration."
            ),
            wraplength=320,
            justify=tk.LEFT,
            style="Muted.TLabel",
        ).pack(anchor=tk.W)

        out = ttk.LabelFrame(right, text="Results / log", padding=10)
        out.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(out, wrap=tk.WORD, font=("Consolas", 10), height=30)
        scroll = ttk.Scrollbar(out, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        status = ttk.Frame(self)
        status.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(status, textvariable=self.status).pack(side=tk.LEFT)
        ttk.Label(status, text=f"Project: {PACKAGE_ROOT}", style="Muted.TLabel").pack(side=tk.RIGHT)

    def browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Select run.yaml",
            initialdir=str(PACKAGE_ROOT / "configs"),
            filetypes=[("YAML", "*.yaml;*.yml"), ("All files", "*.*")],
        )
        if path:
            self.config_path.set(path)
            self.reload_config()

    def reload_config(self) -> None:
        try:
            cfg = load_run_config(self.config_path.get())
            paths = cfg["paths_resolved"]
            self._baselines = load_all_baselines(paths["baselines_dir"])
            techs = cfg.get("techniques") or []
            if techs:
                self.tech_combo["values"] = techs
                if self.technique.get() not in techs:
                    self.technique.set(techs[0])
            insts = cfg.get("instruments") or ["vln", "vla", "vlc", "cb"]
            self.inst_combo["values"] = insts
            if self.instrument.get() not in insts:
                self.instrument.set(insts[0])
            run = cfg.get("run") or {}
            baselines = run.get("baseline_collection_ids") or []
            self.baseline_collections.set(", ".join(baselines) or "(none)")
            self._on_instrument_change()
            self.status.set("Configuration loaded")
            self._write(
                "Loaded run config.\n"
                f"  baseline_collection_ids: {baselines}\n"
                f"  validation_collection_ids: {run.get('validation_collection_ids')}\n"
                f"  pooling: {run.get('pooling')}\n"
                f"  target_metric_definition_id: {run.get('target_metric_definition_id')}\n"
                f"  instruments: {insts}\n"
                f"  techniques: {techs}\n"
                f"  n_draws: {cfg.get('n_draws')}\n"
            )
        except Exception as exc:  # noqa: BLE001 - show in GUI
            messagebox.showerror("Config error", str(exc))
            self.status.set("Config error")

    def _on_instrument_change(self) -> None:
        code = self.instrument.get()
        baseline = self._baselines.get(code)
        if not baseline:
            self.note_combo["values"] = []
            self.note.set("")
            return
        notes = list_notes(baseline)
        self.note_combo["values"] = notes
        if notes and self.note.get() not in notes:
            # Prefer a middle-register default when available.
            preferred = "A4" if "A4" in notes else notes[len(notes) // 2]
            self.note.set(preferred)

    def _write(self, text: str, *, clear: bool = True) -> None:
        if clear:
            self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, text)
        self.text.see(tk.END)

    def _append(self, text: str) -> None:
        self.text.insert(tk.END, text + "\n")
        self.text.see(tk.END)

    def lookup_cell(self) -> None:
        try:
            result = lookup_single(
                self.instrument.get(),
                self.technique.get(),
                self.note.get(),
                self.dynamic.get(),
                run_config_path=self.config_path.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Lookup failed", str(exc))
            return

        inst = INSTRUMENT_DISPLAY.get(result["instrument"], result["instrument"])
        tech = TECHNIQUE_DISPLAY.get(result["technique"], result["technique"])
        lines = [
            "=== Cell lookup ===",
            f"Instrument : {inst} ({result['instrument']})",
            f"Technique  : {tech} ({result['technique']})",
            f"Note       : {result['note']}",
            f"Dynamic    : {result['dynamic']}",
            "",
            f"Ordinary density : {self._fmt(result.get('ordinary_density'))}",
            f"Estimated density: {self._fmt(result.get('estimated_density'))}",
            f"Mean / std       : {self._fmt(result.get('estimated_mean'))} / {self._fmt(result.get('estimated_std'))}",
            f"95% CI           : [{self._fmt(result.get('ci_low'))}, {self._fmt(result.get('ci_high'))}]",
            f"Status           : {result.get('estimation_status')}",
            f"Evidence         : {result.get('evidence_note')}",
            f"Baselines        : {result.get('baseline_collection_ids')}",
            f"Pooling method   : {result.get('pooling_method')}",
            f"Weights          : {result.get('collection_weights')}",
            f"Excluded         : {result.get('excluded_collections')}",
            "",
            f"Holdout available: {result.get('holdout_available')}",
            f"Holdout density  : {self._fmt(result.get('holdout_density'))}",
            f"Abs error        : {self._fmt(result.get('abs_error'))}",
            f"Comparison       : {result.get('comparison_status')}",
        ]
        self._write("\n".join(lines) + "\n")
        self.status.set(str(result.get("estimation_status")))

    def show_baseline(self) -> None:
        code = self.instrument.get()
        baseline = self._baselines.get(code)
        if not baseline:
            messagebox.showwarning("No data", f"No baseline for {code}")
            return
        rows = []
        for note, dyns in (baseline.get("spectral_data") or {}).items():
            rows.append(
                f"{note:6}  pp={self._fmt(dyns.get('pp')):>10}  "
                f"mf={self._fmt(dyns.get('mf')):>10}  ff={self._fmt(dyns.get('ff')):>10}"
            )
        name = INSTRUMENT_DISPLAY.get(code, code)
        self._write(
            f"=== Ordinary CDM baseline: {name} ===\n"
            f"Metric: {baseline.get('metric')}\n"
            f"File  : {baseline.get('_path')}\n\n" + "\n".join(rows) + "\n"
        )
        self.status.set(f"Baseline rows: {len(rows)}")

    def show_holdout(self) -> None:
        try:
            cfg = load_run_config(self.config_path.get())
            holdout = load_holdout(
                self.instrument.get(),
                self.technique.get(),
                cfg["paths_resolved"]["validation_holdout_dir"],
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Holdout error", str(exc))
            return
        if not holdout:
            messagebox.showinfo(
                "No holdout",
                "No validation holdout file for this instrument/technique pair.",
            )
            return
        rows = []
        baseline = self._baselines.get(self.instrument.get(), {})
        for note, dyns in (holdout.get("spectral_data") or {}).items():
            ord_mf = get_density(baseline, note, "mf")
            rows.append(
                f"{note:6}  pp={self._fmt(dyns.get('pp')):>10}  "
                f"mf={self._fmt(dyns.get('mf')):>10}  ff={self._fmt(dyns.get('ff')):>10}"
                f"   | ordinary mf={self._fmt(ord_mf)}"
            )
        tech = TECHNIQUE_DISPLAY.get(self.technique.get(), self.technique.get())
        self._write(
            f"=== Holdout measured technique: {tech} ===\n"
            f"Usage: {holdout.get('usage')}\n"
            f"File : {holdout.get('_path')}\n\n" + "\n".join(rows) + "\n"
        )
        self.status.set(f"Holdout rows: {len(rows)}")

    def run_full(self) -> None:
        if self._running:
            return
        self._running = True
        self.status.set("Running pipeline…")
        self._write("Starting full pipeline…\n", clear=True)

        def work() -> None:
            try:
                summary = run_pipeline(
                    self.config_path.get(),
                    progress=lambda msg: self.master.after(0, lambda m=msg: self._append(m)),
                )
                slim = {k: v for k, v in summary.items() if not k.endswith("_rows")}
                text = "\n=== Run summary ===\n"
                for key, value in slim.items():
                    if key == "outputs":
                        text += "outputs:\n"
                        for ok, ov in (value or {}).items():
                            text += f"  {ok}: {ov}\n"
                    else:
                        text += f"{key}: {value}\n"
                self.master.after(0, lambda: self._finish_ok(text))
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                self.master.after(0, lambda m=message: self._finish_err(m))

        threading.Thread(target=work, daemon=True).start()

    def _finish_ok(self, text: str) -> None:
        self._append(text)
        self._running = False
        self.status.set("Run complete")
        messagebox.showinfo("Pipeline finished", "Outputs written under the outputs/ folder.")

    def _finish_err(self, message: str) -> None:
        self._append("ERROR: " + message)
        self._running = False
        self.status.set("Run failed")
        messagebox.showerror("Pipeline failed", message)

    def open_outputs(self) -> None:
        try:
            cfg = load_run_config(self.config_path.get())
            path = Path(cfg["paths_resolved"]["outputs_dir"])
            path.mkdir(parents=True, exist_ok=True)
            import os

            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open failed", str(exc))

    @staticmethod
    def _fmt(value: object) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value)


def launch_legacy_gui() -> None:
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    LegacyScientificApp(root)
    root.mainloop()


# Back-compat alias
StringTechniqueApp = LegacyScientificApp


def main() -> None:
    launch_legacy_gui()


if __name__ == "__main__":
    main()
