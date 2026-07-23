"""Editable note|value grid for manual full-register entry."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any


class RegisterGrid(ttk.Frame):
    """Editable grid: note + value (both can be typed/pasted)."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_change: Callable[[], None] | None = None,
        get_instrument: Callable[[], str] | None = None,
        get_dynamic: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(master)
        self.on_change = on_change
        self.get_instrument = get_instrument or (lambda: "vln")
        self.get_dynamic = get_dynamic or (lambda: "pp")
        self._rows: list[dict[str, Any]] = []
        self._edit_entry: ttk.Entry | None = None
        self._edit_item: str | None = None
        self._edit_col: str | None = None

        cols = ("note", "midi", "value")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=20, selectmode="browse")
        self.tree.heading("note", text="note (editable)")
        self.tree.heading("midi", text="midi")
        self.tree.heading("value", text="value (type / paste)")
        self.tree.column("note", width=100, stretch=False)
        self.tree.column("midi", width=60, stretch=False)
        self.tree.column("value", width=160, stretch=True)
        yscroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Return>", self._begin_edit)
        self.tree.bind("<<Paste>>", self._paste_event)
        self.tree.bind("<Control-v>", self._paste_event)
        self.tree.bind("<Control-V>", self._paste_event)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._close_edit(commit=False)
        self._rows = [dict(r) for r in rows]
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self._rows:
            val = r.get("value")
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.get("note") or "",
                    "" if r.get("midi") is None else str(r.get("midi")),
                    "" if val is None else str(val).replace(".", ","),  # show European-style
                ),
            )

    def get_rows(self) -> list[dict[str, Any]]:
        self._close_edit(commit=True)
        from string_technique_model.extrapolation.register_builder import parse_number, resolve_note

        items = self.tree.get_children()
        # Allow grid to grow if user added rows via paste rebuild
        out: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            vals = self.tree.item(item, "values")
            note_raw = str(vals[0]).strip() if len(vals) > 0 else ""
            midi_raw = vals[1] if len(vals) > 1 else ""
            val_raw = vals[2] if len(vals) > 2 else ""
            base = dict(self._rows[idx]) if idx < len(self._rows) else {
                "instrument": self.get_instrument(),
                "dynamic": self.get_dynamic(),
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
                "metadata": {},
            }
            resolved = resolve_note(note_raw) if note_raw else None
            if resolved:
                base["note"] = resolved[0]
                base["midi"] = resolved[1]
            else:
                base["note"] = note_raw
                try:
                    base["midi"] = int(str(midi_raw)) if str(midi_raw).strip() else None
                except ValueError:
                    base["midi"] = None
            base["value"] = parse_number(str(val_raw)) if str(val_raw).strip() else None
            base["instrument"] = self.get_instrument()
            base["dynamic"] = self.get_dynamic()
            out.append(base)
        self._rows = out
        return [dict(r) for r in self._rows]

    def _begin_edit(self, event: tk.Event | None = None) -> None:
        if event is not None and getattr(event, "x", None) is not None:
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                # Return key fallback: edit value
                col = "#3"
                sel = self.tree.selection()
                if not sel:
                    return
                item = sel[0]
            else:
                item = self.tree.identify_row(event.y)
                col = self.tree.identify_column(event.x)
                if not item or not col:
                    return
        else:
            sel = self.tree.selection()
            if not sel:
                return
            item = sel[0]
            col = "#3"

        col_index = int(col.replace("#", "")) - 1
        col_name = ("note", "midi", "value")[col_index]
        if col_name == "midi":
            return  # midi derived from note
        bbox = self.tree.bbox(item, col)
        if not bbox:
            return
        self._close_edit(commit=True)
        x, y, w, h = bbox
        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, self.tree.set(item, col_name))
        entry.focus_set()
        entry.select_range(0, tk.END)
        entry.bind("<Return>", lambda _e: self._close_edit(commit=True))
        entry.bind("<Escape>", lambda _e: self._close_edit(commit=False))
        entry.bind("<FocusOut>", lambda _e: self._close_edit(commit=True))
        self._edit_entry = entry
        self._edit_item = item
        self._edit_col = col_name

    def _close_edit(self, commit: bool = True) -> None:
        if self._edit_entry is None or self._edit_item is None or self._edit_col is None:
            return
        if commit:
            raw = self._edit_entry.get().strip()
            self.tree.set(self._edit_item, self._edit_col, raw)
            if self._edit_col == "note" and raw:
                from string_technique_model.extrapolation.register_builder import resolve_note

                resolved = resolve_note(raw)
                if resolved:
                    self.tree.set(self._edit_item, "note", resolved[0])
                    self.tree.set(self._edit_item, "midi", str(resolved[1]))
            if self.on_change:
                self.on_change()
        self._edit_entry.destroy()
        self._edit_entry = None
        self._edit_item = None
        self._edit_col = None

    def _paste_event(self, _event: tk.Event | None = None) -> str:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return "break"
        self.paste_values(text)
        return "break"

    def paste_values(self, text: str, *, start_from_selection: bool = True) -> list[str]:
        """Paste value column or note+value table (accepts inputted notes)."""
        from string_technique_model.extrapolation.register_builder import apply_pasted_table

        rows = self.get_rows()
        start = 0
        if start_from_selection:
            sel = self.tree.selection()
            items = list(self.tree.get_children())
            if sel and items:
                start = items.index(sel[0])
        filled, warnings = apply_pasted_table(
            rows,
            text,
            start_index=start,
            instrument=self.get_instrument(),
            dynamic=self.get_dynamic(),
            rebuild_from_pasted_notes=True,
        )
        self.set_rows(filled)
        if self.on_change:
            self.on_change()
        return warnings


class RequestGrid(ttk.Frame):
    """Editable requests: note + technique (+ optional instrument/dynamic)."""

    def __init__(self, master: tk.Misc, *, on_change: Callable[[], None] | None = None) -> None:
        super().__init__(master)
        self.on_change = on_change
        cols = ("note", "technique", "instrument", "dynamic")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=100, stretch=True)
        yscroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._edit_entry: ttk.Entry | None = None
        self._edit_item: str | None = None
        self._edit_col: str | None = None
        self.tree.bind("<Double-1>", self._begin_edit)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in rows:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.get("note") or "",
                    r.get("technique") or "",
                    r.get("instrument") or "",
                    r.get("dynamic") or "",
                ),
            )

    def get_rows(self) -> list[dict[str, Any]]:
        self._close_edit(commit=True)
        out: list[dict[str, Any]] = []
        for item in self.tree.get_children():
            note, tech, inst, dyn = self.tree.item(item, "values")
            if not str(note).strip() or not str(tech).strip():
                continue
            out.append(
                {
                    "note": str(note).strip(),
                    "technique": str(tech).strip(),
                    "instrument": str(inst).strip() or None,
                    "dynamic": str(dyn).strip() or None,
                    "quantity": "EWSD_score_acoustic_balanced",
                    "metadata": {},
                }
            )
        return out

    def add_empty_row(self, *, instrument: str = "", dynamic: str = "") -> None:
        self.tree.insert("", tk.END, values=("", "", instrument, dynamic))

    def _begin_edit(self, event: tk.Event) -> None:
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or not col:
            return
        col_index = int(col.replace("#", "")) - 1
        col_name = ("note", "technique", "instrument", "dynamic")[col_index]
        bbox = self.tree.bbox(item, col)
        if not bbox:
            return
        self._close_edit(commit=True)
        x, y, w, h = bbox
        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, self.tree.set(item, col_name))
        entry.focus_set()
        entry.bind("<Return>", lambda _e: self._close_edit(commit=True))
        entry.bind("<Escape>", lambda _e: self._close_edit(commit=False))
        entry.bind("<FocusOut>", lambda _e: self._close_edit(commit=True))
        self._edit_entry = entry
        self._edit_item = item
        self._edit_col = col_name

    def _close_edit(self, commit: bool = True) -> None:
        if self._edit_entry is None or self._edit_item is None or self._edit_col is None:
            return
        if commit:
            self.tree.set(self._edit_item, self._edit_col, self._edit_entry.get().strip())
            if self.on_change:
                self.on_change()
        self._edit_entry.destroy()
        self._edit_entry = None
        self._edit_item = None
        self._edit_col = None
