"""Principal metadata-entry window: table + compact record editor."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from string_technique_model.config import DEFAULT_RUN
from string_technique_model.gui_metadata.advanced import open_advanced_tools
from string_technique_model.gui_metadata.editor import RecordEditor
from string_technique_model.gui_metadata.table import MetadataTable
from string_technique_model.metadata_entry.collection import MetadataCollection
from string_technique_model.metadata_entry.labels import DEFAULT_TABLE_COLUMNS, label_for
from string_technique_model.metadata_entry.models import SCHEMA_VERSION


class MetadataEntryApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.root = master
        self.pack(fill=tk.BOTH, expand=True)
        self.collection = MetadataCollection()
        self.run_config_path = tk.StringVar(value=str(DEFAULT_RUN))
        self.status_text = tk.StringVar(value="Ready")
        self.editor_visible = tk.BooleanVar(value=True)
        self._clipboard_cell: str | None = None
        self.table: MetadataTable
        self.editor: RecordEditor
        self._build()
        self.collection.add_record()
        self.refresh_all()

    def _build(self) -> None:
        self.root.title("Metadata Entry")
        self.root.minsize(1000, 640)
        self.root.geometry("1280x780")
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        self._build_menu()
        self._build_toolbar()

        self.paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(self.paned)
        right = ttk.Frame(self.paned, width=360)
        self.paned.add(left, weight=4)
        self.paned.add(right, weight=1)
        self._editor_pane = right

        row_btns = ttk.Frame(left)
        row_btns.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(row_btns, text="Add Record", command=self.add_record).pack(side=tk.LEFT, padx=2)
        ttk.Button(row_btns, text="Duplicate Record", command=self.duplicate_record).pack(side=tk.LEFT, padx=2)
        ttk.Button(row_btns, text="Delete Record", command=self.delete_records).pack(side=tk.LEFT, padx=2)
        ttk.Button(row_btns, text="Choose audio…", command=self.choose_audio).pack(side=tk.LEFT, padx=8)
        ttk.Label(row_btns, text="Filter:").pack(side=tk.LEFT, padx=(12, 2))
        self.filter_var = tk.StringVar()
        filt = ttk.Entry(row_btns, textvariable=self.filter_var, width=24)
        filt.pack(side=tk.LEFT)
        filt.bind("<KeyRelease>", lambda _e: self.table.apply_filter(self.filter_var.get()))

        self.table = MetadataTable(
            left,
            columns=list(DEFAULT_TABLE_COLUMNS),
            on_select=self._on_table_select,
            on_cell_edit=self._on_cell_edit,
            label_fn=label_for,
        )
        self.table.pack(fill=tk.BOTH, expand=True)

        self.editor = RecordEditor(right, on_change=self._on_editor_change)
        self.editor.pack(fill=tk.BOTH, expand=True)

        status = ttk.Frame(self)
        status.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=4)
        ttk.Label(status, textvariable=self.status_text).pack(side=tk.LEFT)
        self.root.bind_all("<Control-z>", lambda _e: self._undo())
        self.root.bind_all("<Control-y>", lambda _e: self._redo())
        self.root.bind_all("<Control-s>", lambda _e: self.save())
        self.root.bind_all("<Control-n>", lambda _e: self.new_collection())
        self.root.bind_all("<Control-o>", lambda _e: self.open_collection())

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label="New", command=self.new_collection, accelerator="Ctrl+N")
        file_m.add_command(label="Open…", command=self.open_collection, accelerator="Ctrl+O")
        file_m.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        file_m.add_command(label="Save As…", command=self.save_as)
        file_m.add_separator()
        file_m.add_command(label="Import…", command=self.import_file)
        file_m.add_command(label="Export…", command=self.export_file)
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_m)

        edit_m = tk.Menu(menubar, tearoff=0)
        edit_m.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        edit_m.add_command(label="Redo", command=self._redo, accelerator="Ctrl+Y")
        edit_m.add_separator()
        edit_m.add_command(label="Add Record", command=self.add_record)
        edit_m.add_command(label="Duplicate Record", command=self.duplicate_record)
        edit_m.add_command(label="Delete Record", command=self.delete_records)
        edit_m.add_command(label="Fill Down", command=self.fill_down)
        menubar.add_cascade(label="Edit", menu=edit_m)

        view_m = tk.Menu(menubar, tearoff=0)
        view_m.add_checkbutton(
            label="Show record editor",
            variable=self.editor_visible,
            command=self._toggle_editor,
        )
        view_m.add_command(label="Configure columns…", command=self.configure_columns)
        menubar.add_cascade(label="View", menu=view_m)

        tools_m = tk.Menu(menubar, tearoff=0)
        tools_m.add_command(label="Validate", command=self.validate)
        tools_m.add_separator()
        tools_m.add_command(label="Advanced scientific tools…", command=self.open_advanced)
        menubar.add_cascade(label="Tools", menu=tools_m)

        help_m = tk.Menu(menubar, tearoff=0)
        help_m.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=help_m)
        self.root.configure(menu=menubar)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(fill=tk.X)
        for text, cmd in (
            ("New", self.new_collection),
            ("Open", self.open_collection),
            ("Save", self.save),
            ("Import", self.import_file),
            ("Export", self.export_file),
            ("Validate", self.validate),
        ):
            ttk.Button(bar, text=text, command=cmd).pack(side=tk.LEFT, padx=2)
        ttk.Label(bar, text=f"Schema {SCHEMA_VERSION}", foreground="#666").pack(side=tk.RIGHT)

    def _toggle_editor(self) -> None:
        if self.editor_visible.get():
            try:
                self.paned.add(self._editor_pane, weight=1)
            except tk.TclError:
                pass
            self.editor.pack(fill=tk.BOTH, expand=True)
        else:
            try:
                self.paned.forget(self._editor_pane)
            except tk.TclError:
                pass

    def refresh_all(self) -> None:
        self.table.set_rows(self.collection.records)
        sel = self.table.selected_indices()
        if sel:
            self.editor.load_record(self.collection.records[sel[0]])
        elif self.collection.records:
            self.editor.load_record(self.collection.records[0])
            self.table.select_index(0)
        else:
            self.editor.clear()
        self._update_status()

    def _update_status(self) -> None:
        c = self.collection.counts()
        path = str(self.collection.path) if self.collection.path else "(unsaved)"
        dirty = " *" if self.collection.dirty else ""
        self.status_text.set(
            f"Records: {c['total']}  |  OK: {c['ok']}  |  Warnings: {c['warnings']}  |  "
            f"Errors: {c['errors']}  |  File: {path}{dirty}"
        )

    def _on_table_select(self, indices: list[int]) -> None:
        if indices and 0 <= indices[0] < len(self.collection.records):
            self.editor.load_record(self.collection.records[indices[0]], index=indices[0])

    def _on_cell_edit(self, index: int, field: str, value: str) -> None:
        parsed: Any = None if value.strip() == "" else value
        self.collection.update_record(index, {field: parsed})
        self.refresh_all()
        self.table.select_index(index)

    def _on_editor_change(self, index: int | None, updates: dict[str, Any]) -> None:
        if index is None or index < 0 or index >= len(self.collection.records):
            return
        self.collection.update_record(index, updates)
        self.refresh_all()
        self.table.select_index(index)

    def add_record(self) -> None:
        self.collection.add_record()
        self.refresh_all()
        self.table.select_index(len(self.collection.records) - 1)

    def duplicate_record(self) -> None:
        sel = self.table.selected_indices()
        if not sel:
            messagebox.showinfo("Duplicate", "Select a record first.")
            return
        self.collection.duplicate_record(sel[0])
        self.refresh_all()
        self.table.select_index(sel[0] + 1)

    def delete_records(self) -> None:
        sel = self.table.selected_indices()
        if not sel:
            return
        if not messagebox.askyesno("Delete", f"Delete {len(sel)} record(s)?"):
            return
        self.collection.delete_records(sel)
        self.refresh_all()

    def choose_audio(self) -> None:
        sel = self.table.selected_indices()
        if not sel:
            messagebox.showinfo("Audio", "Select a record first.")
            return
        path = filedialog.askopenfilename(
            title="Select audio / source file",
            filetypes=[
                ("Audio", "*.wav *.flac *.aiff *.aif *.mp3"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.collection.update_record(sel[0], {"source_file": path, "audio_file": path})
            self.refresh_all()
            self.table.select_index(sel[0])

    def fill_down(self) -> None:
        sel = self.table.selected_indices()
        col = self.table.active_column()
        if len(sel) < 2 or not col:
            messagebox.showinfo("Fill Down", "Select a block of rows and a column (click a header), then Fill Down.")
            return
        self.collection.fill_down(col, min(sel), max(sel))
        self.refresh_all()

    def validate(self) -> None:
        report = self.collection.validate()
        self.refresh_all()
        messagebox.showinfo(
            "Validation",
            f"Errors: {report.n_errors}\nWarnings: {report.n_warnings}\nInformation: {report.n_info}",
        )

    def new_collection(self) -> None:
        if self.collection.dirty and not messagebox.askyesno("New", "Discard unsaved changes?"):
            return
        name = simpledialog.askstring("New collection", "Collection ID:", initialvalue="untitled_collection")
        if not name:
            return
        self.collection.new_collection(collection_id=name, display_name=name)
        self.collection.add_record()
        self.refresh_all()

    def open_collection(self) -> None:
        path = filedialog.askopenfilename(
            title="Open metadata collection",
            filetypes=[("Metadata", "*.json *.csv *.parquet"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            problems = self.collection.load(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open failed", str(exc))
            return
        self.refresh_all()
        if problems:
            messagebox.showwarning("Import notes", "\n".join(problems[:20]))

    def save(self) -> None:
        if self.collection.path is None:
            self.save_as()
            return
        try:
            suffix = self.collection.path.suffix.lower()
            if suffix == ".csv":
                self.collection.save_csv(self.collection.path)
            else:
                self.collection.save_json(self.collection.path.with_suffix(".json") if suffix == ".parquet" else self.collection.path)
            self._update_status()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", str(exc))

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save metadata collection",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")],
        )
        if not path:
            return
        self.collection.path = Path(path)
        self.save()

    def import_file(self) -> None:
        self.open_collection()

    def export_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export metadata",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("Parquet", "*.parquet")],
        )
        if not path:
            return
        try:
            self.collection.export(path, columns=self.table.visible_columns())
            messagebox.showinfo("Export", f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def configure_columns(self) -> None:
        self.table.configure_visible_columns(self.root)

    def open_advanced(self) -> None:
        open_advanced_tools(self.root, run_config_path=self.run_config_path)

    def _undo(self) -> None:
        if self.collection.undo():
            self.refresh_all()

    def _redo(self) -> None:
        if self.collection.redo():
            self.refresh_all()

    def _about(self) -> None:
        messagebox.showinfo(
            "About",
            "Metadata Entry\n\n"
            "Enter one row per recording, file, excerpt, or analysis unit.\n"
            "Scientific prediction and literature tools are under Tools → Advanced.",
        )


def launch_metadata_gui() -> None:
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    MetadataEntryApp(root)
    root.mainloop()
