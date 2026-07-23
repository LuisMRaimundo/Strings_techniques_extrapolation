"""Manual Metric Entry workspace (Tkinter) — thin UI over ManualEntryService."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from string_technique_model.config import PACKAGE_ROOT
from string_technique_model.manual_entry.constants import (
    CANONICAL_DYNAMICS,
    CANONICAL_TECHNIQUES,
    COLLECTION_ROLES,
    COLLECTION_TYPES,
    INSTRUMENT_DISPLAY,
    MEASURED_OR_ESTIMATED,
)
from string_technique_model.manual_entry.services import ManualEntryService


class ManualMetricEntryPanel(ttk.Frame):
    """GUI workspace: Manual Metric Entry."""

    def __init__(self, master: tk.Misc, *, run_config_path: tk.StringVar | None = None) -> None:
        super().__init__(master, padding=8)
        self.run_config_path = run_config_path
        self.service = ManualEntryService(
            run_config_path=run_config_path.get() if run_config_path else None
        )
        self.status = tk.StringVar(value="Manual Metric Entry — draft mode")
        self._table_rows: list[dict[str, Any]] = []
        self._undo: list[list[dict[str, Any]]] = []
        self._redo: list[list[dict[str, Any]]] = []
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Manual Metric Entry", font=("Segoe UI Semibold", 14)).pack(anchor=tk.W)
        ttk.Label(
            self,
            text=(
                "Enter observations → validate → commit as a registered collection. "
                "Values never write directly into baselines, literature, or predictions."
            ),
            wraplength=900,
        ).pack(anchor=tk.W, pady=(0, 8))

        # Collection metadata
        meta = ttk.LabelFrame(self, text="Collection metadata (required before save)", padding=8)
        meta.pack(fill=tk.X, pady=4)
        self.collection_id = tk.StringVar()
        self.display_name = tk.StringVar()
        self.collection_type = tk.StringVar(value="manually_transcribed")
        self.collection_role = tk.StringVar(value="descriptive_comparison")
        self.metric_definition_id = tk.StringVar(value="ewsd_v1")
        self.created_by = tk.StringVar(value="")
        self.measured_or_estimated = tk.StringVar(value="manually_transcribed")
        self.source_description = tk.StringVar(value="")

        fields = [
            ("collection_id", self.collection_id),
            ("display_name", self.display_name),
            ("created_by", self.created_by),
            ("source_description", self.source_description),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(meta, text=label).grid(row=i // 2, column=(i % 2) * 2, sticky=tk.W, padx=4, pady=2)
            ttk.Entry(meta, textvariable=var, width=36).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky=tk.EW, padx=4, pady=2
            )
        ttk.Label(meta, text="collection_type").grid(row=2, column=0, sticky=tk.W, padx=4)
        ttk.Combobox(
            meta,
            textvariable=self.collection_type,
            values=sorted(COLLECTION_TYPES),
            state="readonly",
            width=33,
        ).grid(row=2, column=1, sticky=tk.W, padx=4)
        ttk.Label(meta, text="collection_role").grid(row=2, column=2, sticky=tk.W, padx=4)
        ttk.Combobox(
            meta,
            textvariable=self.collection_role,
            values=sorted(COLLECTION_ROLES),
            state="readonly",
            width=33,
        ).grid(row=2, column=3, sticky=tk.W, padx=4)
        ttk.Label(meta, text="metric_definition_id").grid(row=3, column=0, sticky=tk.W, padx=4)
        self.metric_combo = ttk.Combobox(
            meta,
            textvariable=self.metric_definition_id,
            values=sorted(self.service.metrics.definitions),
            state="readonly",
            width=33,
        )
        self.metric_combo.grid(row=3, column=1, sticky=tk.W, padx=4)
        self.metric_combo.bind("<<ComboboxSelected>>", lambda _e: self._show_metric_info())
        ttk.Label(meta, text="measured_or_estimated").grid(row=3, column=2, sticky=tk.W, padx=4)
        ttk.Combobox(
            meta,
            textvariable=self.measured_or_estimated,
            values=sorted(MEASURED_OR_ESTIMATED),
            state="readonly",
            width=33,
        ).grid(row=3, column=3, sticky=tk.W, padx=4)

        self.metric_info = tk.StringVar(value="")
        ttk.Label(meta, textvariable=self.metric_info, wraplength=880).grid(
            row=4, column=0, columnspan=4, sticky=tk.W, pady=4
        )
        opt = ttk.LabelFrame(meta, text="Optional provenance", padding=6)
        opt.grid(row=5, column=0, columnspan=4, sticky=tk.EW, pady=4)
        self.opt_institution = tk.StringVar()
        self.opt_performer = tk.StringVar()
        self.opt_citation = tk.StringVar()
        self.opt_licence = tk.StringVar()
        self.opt_notes = tk.StringVar()
        for i, (lab, var) in enumerate(
            [
                ("institution", self.opt_institution),
                ("performer", self.opt_performer),
                ("citation", self.opt_citation),
                ("licence", self.opt_licence),
                ("notes", self.opt_notes),
            ]
        ):
            ttk.Label(opt, text=lab).grid(row=i // 3, column=(i % 3) * 2, sticky=tk.W, padx=2)
            ttk.Entry(opt, textvariable=var, width=28).grid(
                row=i // 3, column=(i % 3) * 2 + 1, sticky=tk.EW, padx=2
            )
        btns = ttk.Frame(meta)
        btns.grid(row=6, column=0, columnspan=4, sticky=tk.W, pady=4)
        ttk.Button(btns, text="Create / update draft collection", command=self.create_collection).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="Register new metric definition…", command=self.register_metric).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="Download data-entry templates", command=self.download_templates).pack(
            side=tk.LEFT, padx=2
        )

        # Notebook for entry modes
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, pady=6)

        form = ttk.Frame(nb, padding=8)
        table = ttk.Frame(nb, padding=8)
        grid = ttk.Frame(nb, padding=8)
        paste = ttk.Frame(nb, padding=8)
        browser = ttk.Frame(nb, padding=8)
        nb.add(form, text="Single observation")
        nb.add(table, text="Table")
        nb.add(grid, text="Pitch × dynamic grid")
        nb.add(paste, text="Spreadsheet paste")
        nb.add(browser, text="Collection browser")

        self._build_form(form)
        self._build_table(table)
        self._build_grid(grid)
        self._build_paste(paste)
        self._build_browser(browser)

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=4)
        ttk.Button(actions, text="Validate draft", command=self.validate_draft).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Review & commit…", command=self.commit_collection).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Assign collection role…", command=self.assign_role).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions, text="Technique mapping editor…", command=self.edit_technique_mapping).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(actions, textvariable=self.status).pack(side=tk.RIGHT)
        self._show_metric_info()

    def _build_form(self, parent: ttk.Frame) -> None:
        self.f_instrument = tk.StringVar(value="vln")
        self.f_technique = tk.StringVar(value="ordinary")
        self.f_technique_other = tk.StringVar(value="")
        self.f_pitch = tk.StringVar(value="A4")
        self.f_midi = tk.StringVar(value="69")
        self.f_hz = tk.StringVar(value="")
        self.f_dynamic = tk.StringVar(value="mf")
        self.f_density = tk.StringVar(value="")
        self.f_cb_transp = tk.StringVar(value="-12")
        self.f_cb_confirm = tk.BooleanVar(value=False)
        self.f_harmonic_order = tk.StringVar(value="")
        self.f_mute_type = tk.StringVar(value="")
        self.f_bow_ratio = tk.StringVar(value="")

        r = 0
        ttk.Label(parent, text="Instrument").grid(row=r, column=0, sticky=tk.W)
        inst_vals = [f"{k} — {INSTRUMENT_DISPLAY[k]}" for k in ("vln", "vla", "vlc", "cb")]
        self.inst_combo = ttk.Combobox(
            parent, textvariable=self.f_instrument, values=["vln", "vla", "vlc", "cb"], state="readonly"
        )
        self.inst_combo.grid(row=r, column=1, sticky=tk.EW)
        self.inst_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_conditional())
        ttk.Label(parent, text=" / ".join(inst_vals), wraplength=420).grid(row=r, column=2, sticky=tk.W)

        r += 1
        ttk.Label(parent, text="Technique").grid(row=r, column=0, sticky=tk.W)
        ttk.Combobox(
            parent,
            textvariable=self.f_technique,
            values=sorted(CANONICAL_TECHNIQUES) + ["(other)"],
            state="readonly",
        ).grid(row=r, column=1, sticky=tk.EW)
        ttk.Entry(parent, textvariable=self.f_technique_other).grid(row=r, column=2, sticky=tk.EW)
        ttk.Label(parent, text="Other source label →").grid(row=r, column=2, sticky=tk.W)
        # fix layout: other entry on next row
        r += 1
        ttk.Label(parent, text="Other technique label").grid(row=r, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.f_technique_other).grid(row=r, column=1, columnspan=2, sticky=tk.EW)

        r += 1
        ttk.Label(parent, text="Pitch name").grid(row=r, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.f_pitch).grid(row=r, column=1, sticky=tk.EW)
        ttk.Label(parent, text="MIDI").grid(row=r, column=2, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.f_midi, width=8).grid(row=r, column=2, sticky=tk.E)

        r += 1
        ttk.Label(parent, text="Fundamental Hz").grid(row=r, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.f_hz).grid(row=r, column=1, sticky=tk.EW)

        r += 1
        ttk.Label(parent, text="Dynamic").grid(row=r, column=0, sticky=tk.W)
        ttk.Combobox(
            parent, textvariable=self.f_dynamic, values=sorted(CANONICAL_DYNAMICS), state="readonly"
        ).grid(row=r, column=1, sticky=tk.EW)

        r += 1
        ttk.Label(parent, text="density_value").grid(row=r, column=0, sticky=tk.W)
        ttk.Entry(parent, textvariable=self.f_density).grid(row=r, column=1, sticky=tk.EW)

        self.cb_frame = ttk.LabelFrame(parent, text="Double bass transposition", padding=6)
        self.cb_frame.grid(row=r + 1, column=0, columnspan=3, sticky=tk.EW, pady=6)
        ttk.Label(self.cb_frame, text="Transposition (semitones)").grid(row=0, column=0)
        ttk.Entry(self.cb_frame, textvariable=self.f_cb_transp, width=8).grid(row=0, column=1)
        ttk.Checkbutton(
            self.cb_frame,
            text="I confirm the calculated sounding pitch",
            variable=self.f_cb_confirm,
        ).grid(row=0, column=2, padx=8)

        self.cond_frame = ttk.LabelFrame(parent, text="Technique-specific fields", padding=6)
        self.cond_frame.grid(row=r + 2, column=0, columnspan=3, sticky=tk.EW, pady=6)
        ttk.Label(self.cond_frame, text="harmonic_order").grid(row=0, column=0)
        ttk.Entry(self.cond_frame, textvariable=self.f_harmonic_order, width=10).grid(row=0, column=1)
        ttk.Label(self.cond_frame, text="mute_type").grid(row=0, column=2)
        ttk.Entry(self.cond_frame, textvariable=self.f_mute_type, width=12).grid(row=0, column=3)
        ttk.Label(self.cond_frame, text="bow_position_ratio").grid(row=0, column=4)
        ttk.Entry(self.cond_frame, textvariable=self.f_bow_ratio, width=10).grid(row=0, column=5)

        ttk.Button(parent, text="Add observation to table", command=self.add_from_form).grid(
            row=r + 3, column=0, columnspan=3, sticky=tk.W, pady=8
        )
        parent.columnconfigure(1, weight=1)
        self._update_conditional()

    def _build_table(self, parent: ttk.Frame) -> None:
        cols = (
            "instrument",
            "technique",
            "pitch_name_sounding",
            "dynamic",
            "density_value",
            "metric_definition_id",
            "status",
        )
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110)
        self.tree.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, pady=4)
        for text, cmd in [
            ("Add row", self.table_add_row),
            ("Duplicate row", self.table_duplicate),
            ("Delete row", self.table_delete),
            ("Fill down", self.table_fill_down),
            ("Undo", self.table_undo),
            ("Redo", self.table_redo),
            ("Validate all", self.validate_draft),
            ("Save draft", self.save_table_draft),
            ("Filter invalid", self.filter_invalid),
        ]:
            ttk.Button(bar, text=text, command=cmd).pack(side=tk.LEFT, padx=2)

    def _build_grid(self, parent: ttk.Frame) -> None:
        self.g_instrument = tk.StringVar(value="vln")
        self.g_technique = tk.StringVar(value="ordinary")
        self.g_text = tk.Text(parent, height=12, font=("Consolas", 10))
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Instrument").pack(side=tk.LEFT)
        ttk.Combobox(
            top, textvariable=self.g_instrument, values=["vln", "vla", "vlc", "cb"], width=8, state="readonly"
        ).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Technique").pack(side=tk.LEFT)
        ttk.Combobox(
            top,
            textvariable=self.g_technique,
            values=sorted(CANONICAL_TECHNIQUES),
            width=20,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Load empty grid template", command=self.load_grid_template).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(top, text="Convert grid → table", command=self.grid_to_table).pack(side=tk.LEFT, padx=4)
        self.g_text.pack(fill=tk.BOTH, expand=True, pady=4)
        self.g_text.insert(
            "1.0",
            "pitch\tpp\tmf\tff\nG3\t\t\t\nG#3\t\t\t\nA3\t\t\t\n",
        )

    def _build_paste(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="Paste a rectangular range (TSV/CSV). Confirm column mapping before import.",
        ).pack(anchor=tk.W)
        self.paste_text = tk.Text(parent, height=10, font=("Consolas", 10))
        self.paste_text.pack(fill=tk.BOTH, expand=True)
        self.paste_info = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.paste_info, wraplength=880).pack(anchor=tk.W)
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Preview paste", command=self.preview_paste).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Import into table (after confirm)", command=self.import_paste).pack(
            side=tk.LEFT, padx=2
        )
        self._paste_preview = None

    def _build_browser(self, parent: ttk.Frame) -> None:
        self.browser_list = tk.Listbox(parent, height=10)
        self.browser_list.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Refresh", command=self.refresh_browser).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Load draft into table", command=self.load_selected_draft).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(bar, text="Confirm duplicates for commit", command=self.confirm_duplicates).pack(
            side=tk.LEFT, padx=2
        )

    # --- helpers --------------------------------------------------------------

    def _meta(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id.get().strip(),
            "display_name": self.display_name.get().strip(),
            "collection_type": self.collection_type.get(),
            "collection_role": self.collection_role.get(),
            "metric_definition_id": self.metric_definition_id.get(),
            "created_by": self.created_by.get().strip(),
            "measured_or_estimated": self.measured_or_estimated.get(),
            "source_description": self.source_description.get().strip(),
            "workflow_state": "draft",
            "institution": self.opt_institution.get().strip() or None,
            "performer": self.opt_performer.get().strip() or None,
            "citation": self.opt_citation.get().strip() or None,
            "licence": self.opt_licence.get().strip() or None,
            "notes": self.opt_notes.get().strip() or None,
        }

    def _show_metric_info(self) -> None:
        mid = self.metric_definition_id.get()
        try:
            m = self.service.metrics.get(mid)
            cfg = m.config
            compat = self.service.metrics.compare(mid, "ewsd_v1")
            self.metric_info.set(
                f"{m.name} v{m.version} | domain={cfg.get('mathematical_domain')} | "
                f"unit={cfg.get('unit')} | normalisation={cfg.get('normalisation')} | "
                f"freq={cfg.get('frequency_range_id')} | window={cfg.get('analysis_window_id')} | "
                f"compatibility vs ewsd_v1: {compat.status}"
            )
        except Exception as exc:  # noqa: BLE001
            self.metric_info.set(str(exc))

    def _update_conditional(self) -> None:
        # show/hide CB frame
        if self.f_instrument.get() == "cb":
            self.cb_frame.grid()
        else:
            self.cb_frame.grid_remove()

    def _push_undo(self) -> None:
        self._undo.append([dict(r) for r in self._table_rows])
        self._redo.clear()

    def _refresh_tree(self, rows: list[dict[str, Any]] | None = None) -> None:
        if rows is not None:
            self._table_rows = rows
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self._table_rows:
            status = "ok"
            if r.get("instrument_mapping_status") == "unsupported_instrument":
                status = "invalid"
            elif r.get("technique_mapping_status") == "unmapped":
                status = "unmapped"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.get("instrument"),
                    r.get("original_technique_label") or r.get("technique"),
                    r.get("pitch_name_sounding"),
                    r.get("original_dynamic_label") or r.get("dynamic"),
                    r.get("density_value"),
                    r.get("metric_definition_id"),
                    status,
                ),
            )

    # --- actions --------------------------------------------------------------

    def create_collection(self) -> None:
        try:
            meta = self.service.create_collection(self._meta())
            self.collection_id.set(meta["collection_id"])
            self.status.set(f"Draft collection ready: {meta['collection_id']}")
            messagebox.showinfo("Draft", f"Collection draft created: {meta['collection_id']}")
            self.refresh_browser()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Metadata error", str(exc))

    def add_from_form(self) -> None:
        tech = self.f_technique.get()
        if tech == "(other)" or self.f_technique_other.get().strip():
            tech_label = self.f_technique_other.get().strip() or tech
        else:
            tech_label = tech
        row: dict[str, Any] = {
            "instrument": self.f_instrument.get(),
            "technique": tech_label,
            "original_technique_label": tech_label,
            "pitch_name_sounding": self.f_pitch.get().strip() or None,
            "pitch_midi_sounding": self.f_midi.get().strip() or None,
            "fundamental_hz": self.f_hz.get().strip() or None,
            "dynamic": self.f_dynamic.get(),
            "original_dynamic_label": self.f_dynamic.get(),
            "density_value": self.f_density.get(),
            "metric_definition_id": self.metric_definition_id.get(),
            "measured_or_estimated": self.measured_or_estimated.get(),
            "harmonic_order": self.f_harmonic_order.get() or None,
            "mute_type": self.f_mute_type.get() or None,
            "bow_position_ratio": self.f_bow_ratio.get() or None,
            "cb_transposition_semitones": int(self.f_cb_transp.get() or 0)
            if self.f_instrument.get() == "cb"
            else None,
            "cb_sounding_confirmed": bool(self.f_cb_confirm.get())
            if self.f_instrument.get() == "cb"
            else True,
            "input_method": "single_form",
        }
        if self.f_instrument.get() == "cb":
            row["pitch_name_written"] = self.f_pitch.get().strip()
            row["pitch_midi_written"] = self.f_midi.get().strip() or None
        self._push_undo()
        self._table_rows.append(row)
        self._refresh_tree()
        self.status.set(f"Rows in table: {len(self._table_rows)}")

    def table_add_row(self) -> None:
        self._push_undo()
        self._table_rows.append(
            {
                "instrument": "vln",
                "technique": "ordinary",
                "pitch_name_sounding": "A4",
                "dynamic": "mf",
                "density_value": "",
                "metric_definition_id": self.metric_definition_id.get(),
                "measured_or_estimated": self.measured_or_estimated.get(),
            }
        )
        self._refresh_tree()

    def table_duplicate(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self._push_undo()
        self._table_rows.insert(idx + 1, dict(self._table_rows[idx]))
        self._refresh_tree()

    def table_delete(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self._push_undo()
        del self._table_rows[idx]
        self._refresh_tree()

    def table_fill_down(self) -> None:
        if len(self._table_rows) < 2:
            return
        self._push_undo()
        src = self._table_rows[0]
        for i in range(1, len(self._table_rows)):
            for key in ("instrument", "technique", "metric_definition_id", "measured_or_estimated"):
                if not self._table_rows[i].get(key):
                    self._table_rows[i][key] = src.get(key)
        self._refresh_tree()

    def table_undo(self) -> None:
        if not self._undo:
            return
        self._redo.append([dict(r) for r in self._table_rows])
        self._refresh_tree(self._undo.pop())

    def table_redo(self) -> None:
        if not self._redo:
            return
        self._undo.append([dict(r) for r in self._table_rows])
        self._refresh_tree(self._redo.pop())

    def save_table_draft(self) -> None:
        try:
            if not self.collection_id.get().strip():
                self.create_collection()
            self.service.create_collection(self._meta())
            saved = self.service.save_draft_rows(
                self.collection_id.get().strip(),
                self._table_rows,
                user=self.created_by.get().strip() or "gui_user",
                input_method="table_entry",
            )
            self._refresh_tree(saved)
            self.status.set(f"Draft saved ({len(saved)} rows)")
            messagebox.showinfo("Draft", f"Saved {len(saved)} draft rows.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", str(exc))

    def validate_draft(self) -> None:
        try:
            self.save_table_draft()
            report = self.service.validate_draft(self.collection_id.get().strip())
            lines = [
                f"Status: {report.status}",
                f"Valid: {report.n_valid}  Warnings: {report.n_warning}  Invalid: {report.n_invalid}",
                "",
            ]
            for issue in report.issues[:40]:
                lines.append(
                    f"row={issue.row} field={issue.field} value={issue.invalid_value!r} "
                    f"reason={issue.reason} → {issue.required_correction}"
                )
            messagebox.showinfo("Validation", "\n".join(lines) if lines else "OK")
            self.status.set(report.status)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Validation failed", str(exc))

    def filter_invalid(self) -> None:
        try:
            report = self.service.validate_draft(self.collection_id.get().strip())
            bad = {i.row for i in report.issues if i.severity == "error" and i.row is not None}
            filtered = [r for i, r in enumerate(self._table_rows) if i in bad]
            self._refresh_tree(filtered)
            self.status.set(f"Showing {len(filtered)} invalid rows")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Filter failed", str(exc))

    def commit_collection(self) -> None:
        try:
            self.save_table_draft()
            cid = self.collection_id.get().strip()
            summary = self.service.review_summary(cid)
            msg = (
                f"Collection: {cid}\n"
                f"Observations: {summary['observation_count']}\n"
                f"Instruments: {summary['instruments']}\n"
                f"Techniques: {summary['techniques']}\n"
                f"Dynamics: {summary['dynamics']}\n"
                f"Pitch range: {summary['pitch_ranges']}\n"
                f"Metrics: {summary['metric_definitions']}\n"
                f"Errors: {len(summary['errors'])}\n"
                f"Warnings: {len(summary['warnings'])}\n"
                f"Duplicates: {summary['duplicate_count']}\n"
                f"Provenance complete: {summary['provenance_completeness']}\n\n"
                "Commit creates a registered canonical collection "
                "(not baseline/prediction outputs).\nContinue?"
            )
            if not messagebox.askyesno("Review & commit", msg):
                return
            result = self.service.commit_collection(
                cid, user=self.created_by.get().strip() or "gui_user", confirm=True
            )
            messagebox.showinfo(
                "Committed",
                f"Committed {result.n_records} records\n"
                f"Parquet: {result.parquet_path}\nCSV: {result.csv_path}\n"
                f"commit_id: {result.commit_id}",
            )
            self.status.set("committed")
            self.refresh_browser()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Commit failed", str(exc))

    def assign_role(self) -> None:
        cid = self.collection_id.get().strip()
        role = simpledialog.askstring(
            "Assign collection role",
            f"Role for {cid} ({', '.join(sorted(COLLECTION_ROLES))}):",
            initialvalue=self.collection_role.get(),
        )
        if not role:
            return
        try:
            result = self.service.assign_role(cid, role.strip())
            if result.get("blocked"):
                messagebox.showerror(
                    "Role blocked",
                    "Data-leakage / validation blocked assignment:\n" + "\n".join(result.get("reasons") or []),
                )
            else:
                messagebox.showinfo("Role assigned", str(result))
                self.collection_role.set(role.strip())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Role error", str(exc))

    def edit_technique_mapping(self) -> None:
        original = simpledialog.askstring("Technique mapping", "Original technique label:")
        if not original:
            return
        canonical = simpledialog.askstring(
            "Technique mapping",
            f"Canonical code ({', '.join(sorted(CANONICAL_TECHNIQUES))}):",
        )
        if not canonical:
            return
        justification = simpledialog.askstring("Technique mapping", "Mapping justification:") or ""
        try:
            rec = self.service.mapping.register_technique_mapping(
                original,
                canonical.strip(),
                justification=justification,
                user=self.created_by.get().strip() or "gui_user",
            )
            messagebox.showinfo("Mapped", str(rec.to_dict()))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Mapping error", str(exc))

    def load_grid_template(self) -> None:
        self.g_text.delete("1.0", tk.END)
        self.g_text.insert("1.0", "pitch\tpp\tmf\tff\nG3\t\t\t\nG#3\t\t\t\nA3\t\t\t\nA#3\t\t\t\nB3\t\t\t\nC4\t\t\t\n")

    def grid_to_table(self) -> None:
        from io import StringIO

        import pandas as pd

        try:
            df = pd.read_csv(StringIO(self.g_text.get("1.0", tk.END)), sep="\t")
            rows = self.service.grid_to_long(
                df,
                instrument=self.g_instrument.get(),
                technique=self.g_technique.get(),
                metric_definition_id=self.metric_definition_id.get(),
                measured_or_estimated=self.measured_or_estimated.get(),
            )
            self._push_undo()
            self._table_rows.extend(rows)
            self._refresh_tree()
            self.status.set(f"Grid converted to {len(rows)} long-format rows")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Grid error", str(exc))

    def preview_paste(self) -> None:
        try:
            preview = self.service.preview_paste(self.paste_text.get("1.0", tk.END))
            self._paste_preview = preview
            if preview.ambiguous_mappings:
                self.paste_info.set(
                    "Ambiguous column mapping — confirm before import: "
                    + str(preview.ambiguous_mappings)
                    + f" | suggested={preview.column_mapping}"
                )
            else:
                self.paste_info.set(
                    f"imported={preview.n_imported} valid={preview.n_valid} "
                    f"warn={preview.n_warning} invalid={preview.n_invalid} "
                    f"dups={preview.n_duplicates} unsupported_inst={preview.n_unsupported_instruments} "
                    f"unmapped_tech={preview.n_unmapped_techniques} unmapped_dyn={preview.n_unmapped_dynamics} "
                    f"map={preview.column_mapping}"
                )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Paste preview failed", str(exc))

    def import_paste(self) -> None:
        if self._paste_preview is None:
            self.preview_paste()
        preview = self._paste_preview
        if preview is None:
            return
        if preview.ambiguous_mappings:
            if not messagebox.askyesno(
                "Confirm mapping",
                "Ambiguous columns detected. Use suggested mapping?\n" + str(preview.column_mapping),
            ):
                return
            preview = self.service.preview_paste(
                self.paste_text.get("1.0", tk.END),
                column_mapping=preview.column_mapping,
                confirmed_ambiguous=True,
            )
            self._paste_preview = preview
        if not messagebox.askyesno("Import paste", f"Import {preview.n_imported} rows into the table?"):
            return
        self._push_undo()
        self._table_rows.extend(preview.rows)
        self._refresh_tree()
        self.status.set(f"Pasted {preview.n_imported} rows")

    def download_templates(self) -> None:
        try:
            paths = self.service.download_templates()
            messagebox.showinfo("Templates", "Wrote:\n" + "\n".join(str(p) for p in paths.values()))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Template error", str(exc))

    def register_metric(self) -> None:
        mid = simpledialog.askstring("New metric", "metric_definition_id:")
        if not mid:
            return
        name = simpledialog.askstring("New metric", "name:") or mid
        try:
            entry = self.service.register_metric_definition(
                {
                    "metric_definition_id": mid,
                    "name": name,
                    "version": "1.0",
                    "formula": "unresolved",
                    "mathematical_domain": "positive",
                    "unit": "dimensionless",
                    "normalisation": "unresolved",
                    "frequency_range": "unresolved",
                    "temporal_window": "unresolved",
                    "amplitude_or_power_convention": "unresolved",
                    "thresholding": None,
                    "aggregation_method": "sustained_note_summary",
                    "notes": "Registered from Manual Metric Entry GUI",
                }
            )
            self.metric_combo["values"] = sorted(self.service.metrics.definitions)
            messagebox.showinfo(
                "Metric registered",
                f"{entry['metric_definition_id']} status={entry['metric_definition_status']} "
                f"usable_for_pooling={entry['usable_for_pooling']}",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Metric error", str(exc))

    def refresh_browser(self) -> None:
        self.browser_list.delete(0, tk.END)
        for item in self.service.store.list_collections():
            self.browser_list.insert(
                tk.END,
                f"{item['collection_id']} | {item['workflow_state']} | role={item['collection_role']}",
            )

    def load_selected_draft(self) -> None:
        sel = self.browser_list.curselection()
        if not sel:
            return
        line = self.browser_list.get(sel[0])
        cid = line.split("|", 1)[0].strip()
        self.collection_id.set(cid)
        meta = self.service.store.load_collection_meta(cid) or {}
        self.display_name.set(str(meta.get("display_name") or ""))
        self.created_by.set(str(meta.get("created_by") or ""))
        self.source_description.set(str(meta.get("source_description") or ""))
        rows = self.service.store.load_draft_records(cid)
        if not rows and meta.get("workflow_state") == "committed":
            path = PACKAGE_ROOT / "outputs" / "imported" / f"{cid}.parquet"
            if path.exists():
                import pandas as pd

                rows = pd.read_parquet(path).to_dict(orient="records")
        self._refresh_tree(rows)
        self.status.set(f"Loaded {cid}")

    def confirm_duplicates(self) -> None:
        try:
            meta = self._meta()
            meta["duplicates_confirmed"] = True
            self.service.create_collection(meta)
            messagebox.showinfo("Duplicates", "duplicates_confirmed=True stored on collection metadata")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", str(exc))
