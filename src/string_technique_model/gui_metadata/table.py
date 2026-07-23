"""Spreadsheet-like metadata table (ttk.Treeview)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

from string_technique_model.metadata_entry.labels import DEFAULT_TABLE_COLUMNS, FIELD_LABELS, label_for
from string_technique_model.metadata_entry.models import MetadataEntryRecord


class MetadataTable(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        columns: list[str],
        on_select: Callable[[list[int]], None] | None = None,
        on_cell_edit: Callable[[int, str, str], None] | None = None,
        label_fn: Callable[[str], str] = label_for,
    ) -> None:
        super().__init__(master)
        self.columns = list(columns)
        self._all_columns = list(dict.fromkeys([*DEFAULT_TABLE_COLUMNS, *FIELD_LABELS.keys()]))
        self.on_select = on_select
        self.on_cell_edit = on_cell_edit
        self.label_fn = label_fn
        self._rows: list[MetadataEntryRecord] = []
        self._filter = ""
        self._sort_col: str | None = None
        self._sort_reverse = False
        self._active_column: str | None = columns[0] if columns else None
        self._iid_to_index: dict[str, int] = {}

        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", selectmode="extended")
        ys = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._apply_headings()
        self.tree.bind("<<TreeviewSelect>>", self._emit_select)
        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Return>", self._begin_edit)
        self.tree.bind("<Control-c>", self._copy)
        self.tree.bind("<Control-v>", self._paste)
        self.tree.bind("<Control-d>", lambda e: self._fill_down_shortcut())
        self._clip: str | None = None

    def _apply_headings(self) -> None:
        self.tree["columns"] = self.columns
        for col in self.columns:
            self.tree.heading(col, text=self.label_fn(col), command=self._make_sort_command(col))
            self.tree.column(col, width=120, minwidth=60, stretch=True)

    def _make_sort_command(self, col: str) -> Callable[[], None]:
        def _cmd() -> None:
            self._sort_by(col)

        return _cmd

    def visible_columns(self) -> list[str]:
        return list(self.columns)

    def active_column(self) -> str | None:
        return self._active_column

    def set_rows(self, rows: list[MetadataEntryRecord]) -> None:
        self._rows = list(rows)
        self._redraw()

    def apply_filter(self, text: str) -> None:
        self._filter = (text or "").strip().lower()
        self._redraw()

    def selected_indices(self) -> list[int]:
        out: list[int] = []
        for iid in self.tree.selection():
            if iid in self._iid_to_index:
                out.append(self._iid_to_index[iid])
        return sorted(set(out))

    def select_index(self, index: int) -> None:
        for iid, idx in self._iid_to_index.items():
            if idx == index:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self._emit_select()
                return

    def _cell_value(self, rec: MetadataEntryRecord, col: str) -> str:
        data = rec.model_dump()
        if col == "pitch_name_sounding" and not data.get(col):
            return rec.display_pitch()
        val = data.get(col)
        if val is None:
            return ""
        if isinstance(val, list):
            return ", ".join(str(x) for x in val)
        return str(val)

    def _filtered_indices(self) -> list[int]:
        indices = list(range(len(self._rows)))
        if self._filter:
            kept = []
            for i in indices:
                blob = " ".join(self._cell_value(self._rows[i], c) for c in self.columns).lower()
                if self._filter in blob:
                    kept.append(i)
            indices = kept
        if self._sort_col and self._sort_col in self.columns:
            indices.sort(
                key=lambda i: self._cell_value(self._rows[i], self._sort_col or "").lower(),
                reverse=self._sort_reverse,
            )
        return indices

    def _redraw(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._iid_to_index.clear()
        for i in self._filtered_indices():
            rec = self._rows[i]
            values = [self._cell_value(rec, c) for c in self.columns]
            iid = self.tree.insert("", tk.END, values=values)
            self._iid_to_index[iid] = i
            status = (rec.validation_status or "").lower()
            if status == "error":
                self.tree.item(iid, tags=("error",))
            elif status == "warning":
                self.tree.item(iid, tags=("warning",))
        self.tree.tag_configure("error", background="#ffe0e0")
        self.tree.tag_configure("warning", background="#fff6d5")

    def _emit_select(self, _event: Any = None) -> None:
        if self.on_select:
            self.on_select(self.selected_indices())

    def _sort_by(self, col: str) -> None:
        self._active_column = col
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._redraw()

    def _begin_edit(self, event: Any = None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        index = self._iid_to_index.get(iid)
        if index is None:
            return
        col = self._active_column or self.columns[0]
        # Determine column from click if possible
        if event is not None and getattr(event, "x", None) is not None:
            region = self.tree.identify("region", event.x, event.y)
            if region == "cell":
                col_id = self.tree.identify_column(event.x)
                try:
                    col_index = int(col_id.replace("#", "")) - 1
                    if 0 <= col_index < len(self.columns):
                        col = self.columns[col_index]
                        self._active_column = col
                except ValueError:
                    pass
        current = self._cell_value(self._rows[index], col)
        editor = tk.Toplevel(self)
        editor.title(f"Edit {self.label_fn(col)}")
        editor.transient(self.winfo_toplevel())
        ttk.Label(editor, text=self.label_fn(col)).pack(anchor=tk.W, padx=10, pady=(10, 2))
        var = tk.StringVar(value=current)
        entry = ttk.Entry(editor, textvariable=var, width=48)
        entry.pack(padx=10, pady=4)
        entry.focus_set()
        entry.selection_range(0, tk.END)

        def commit() -> None:
            if self.on_cell_edit:
                self.on_cell_edit(index, col, var.get())
            editor.destroy()

        ttk.Button(editor, text="OK", command=commit).pack(pady=8)
        entry.bind("<Return>", lambda _e: commit())
        entry.bind("<Escape>", lambda _e: editor.destroy())

    def _copy(self, _event: Any = None) -> str:
        sel = self.selected_indices()
        col = self._active_column or self.columns[0]
        if not sel:
            return "break"
        self._clip = self._cell_value(self._rows[sel[0]], col)
        self.clipboard_clear()
        self.clipboard_append(self._clip)
        return "break"

    def _paste(self, _event: Any = None) -> str:
        sel = self.selected_indices()
        col = self._active_column or self.columns[0]
        if not sel or not self.on_cell_edit:
            return "break"
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = self._clip or ""
        for index in sel:
            self.on_cell_edit(index, col, text)
        return "break"

    def _fill_down_shortcut(self) -> str:
        # Handled at app level preferably; here copy first cell down selection
        sel = self.selected_indices()
        col = self._active_column or self.columns[0]
        if len(sel) < 2 or not self.on_cell_edit:
            return "break"
        value = self._cell_value(self._rows[sel[0]], col)
        for index in sel[1:]:
            self.on_cell_edit(index, col, value)
        return "break"

    def configure_visible_columns(self, master: tk.Misc) -> None:
        win = tk.Toplevel(master)
        win.title("Visible columns")
        vars_map: dict[str, tk.BooleanVar] = {}
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        for i, col in enumerate(self._all_columns):
            var = tk.BooleanVar(value=col in self.columns)
            vars_map[col] = var
            ttk.Checkbutton(frame, text=self.label_fn(col), variable=var).grid(
                row=i // 2, column=i % 2, sticky=tk.W, padx=6, pady=2
            )

        def apply() -> None:
            chosen = [c for c, v in vars_map.items() if v.get()]
            if not chosen:
                messagebox.showwarning("Columns", "Select at least one column.", parent=win)
                return
            self.columns = chosen
            self._apply_headings()
            self._redraw()
            win.destroy()

        ttk.Button(win, text="Apply", command=apply).pack(pady=8)
