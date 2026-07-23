"""Compact selected-record editor with pitch-mode and technique panels."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from string_technique_model.metadata_entry.labels import DYNAMICS_ORDERED
from string_technique_model.metadata_entry.models import MetadataEntryRecord
from string_technique_model.metadata_entry.technique_combo import (
    harmonic_panel_visible,
    ontology_technique_choices,
)
from string_technique_model.pitch.modes import PITCH_MODES
from string_technique_model.pitch.registry import get_default_pitch_registry, load_instrument_midi_ranges


class RecordEditor(ttk.Frame):
    def __init__(self, master: tk.Misc, *, on_change: Callable[[int | None, dict[str, Any]], None]) -> None:
        super().__init__(master, padding=6)
        self.on_change = on_change
        self._index: int | None = None
        self._loading = False
        self._vars: dict[str, tk.StringVar | tk.BooleanVar] = {}
        self.registry = get_default_pitch_registry()
        self.ranges = load_instrument_midi_ranges()
        self.choices = ontology_technique_choices()
        self.show_all_pitches = tk.BooleanVar(value=False)

        canvas = tk.Canvas(self, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        self.body = ttk.Frame(canvas)
        self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor=tk.NW)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_core(self.body)
        self.pitch_frame = ttk.LabelFrame(self.body, text="Pitch", padding=6)
        self.pitch_frame.pack(fill=tk.X, pady=4)
        self._build_pitch(self.pitch_frame)

        self.technique_frame = ttk.LabelFrame(self.body, text="Technique combination", padding=6)
        self.technique_frame.pack(fill=tk.X, pady=4)
        self._build_technique(self.technique_frame)

        self.harmonic_frame = ttk.LabelFrame(self.body, text="Harmonic (optional)", padding=6)
        self._build_harmonic(self.harmonic_frame)

        self.bow_frame = self._collapsible(self.body, "Bow contact", self._build_bow)
        self.mute_frame = self._collapsible(self.body, "Mute", self._build_mute)
        self.multi_frame = self._collapsible(self.body, "Multiphonic", self._build_multi)
        self.rec_frame = self._collapsible(self.body, "Recording", self._build_recording)

        ttk.Button(self.body, text="Apply changes", command=self._apply).pack(fill=tk.X, pady=8)

    def _var(self, name: str, value: str = "") -> tk.StringVar:
        var = tk.StringVar(value=value)
        self._vars[name] = var
        return var

    def _entry(self, parent: tk.Misc, label: str, key: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=self._var(key), width=28).grid(row=row, column=1, sticky=tk.EW, pady=2)

    def _combo(self, parent: tk.Misc, label: str, key: str, values: list[str], row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        cb = ttk.Combobox(parent, textvariable=self._var(key), values=values, width=26)
        cb.grid(row=row, column=1, sticky=tk.EW, pady=2)

    def _build_core(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Core", padding=6)
        box.pack(fill=tk.X, pady=4)
        box.columnconfigure(1, weight=1)
        self._entry(box, "Record ID", "record_id", 0)
        self._entry(box, "Audio / source file", "source_file", 1)
        self._combo(box, "Instrument", "instrument", ["vln", "vla", "vlc", "cb", ""], 2)
        self._combo(box, "Dynamic", "dynamic", DYNAMICS_ORDERED, 3)
        self._entry(box, "String", "string_name", 4)
        self._entry(box, "Performer", "performer_id", 5)
        self._entry(box, "Take", "take", 6)
        self._entry(box, "Notes / comments", "notes", 7)

    def _build_pitch(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._combo(parent, "Pitch mode", "pitch_mode", list(PITCH_MODES), 0)
        self._combo(
            parent,
            "Written / sounding",
            "pitch_representation",
            ["written", "sounding", "both", "unresolved"],
            1,
        )
        ttk.Checkbutton(
            parent,
            text="Show all pitches (disable instrument-range filter)",
            variable=self.show_all_pitches,
            command=self._refresh_pitch_choices,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W)

        self.pitch_mode_host = ttk.Frame(parent)
        self.pitch_mode_host.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=4)
        self._pitch_widgets: dict[str, ttk.Frame] = {}
        for mode in PITCH_MODES:
            fr = ttk.Frame(self.pitch_mode_host)
            self._pitch_widgets[mode] = fr
        self._fill_single(self._pitch_widgets["single_note"])
        self._fill_range(self._pitch_widgets["pitch_range"])
        self._fill_multiple(self._pitch_widgets["multiple_notes"])
        self._fill_open(self._pitch_widgets["open_string"])
        ttk.Label(self._pitch_widgets["unpitched_or_noise"], text="No pitch required.").pack(anchor=tk.W)
        ttk.Label(self._pitch_widgets["unknown"], text="Pitch left unknown (null).").pack(anchor=tk.W)

        mode_var = self._vars["pitch_mode"]
        mode_var.trace_add("write", lambda *_: self._show_pitch_mode())
        self._show_pitch_mode()

    def _fill_single(self, fr: ttk.Frame) -> None:
        fr.columnconfigure(1, weight=1)
        self._combo(fr, "Pitch name", "pitch_name", [], 0)
        self._entry(fr, "Letter", "pitch_letter", 1)
        self._combo(fr, "Accidental", "pitch_accidental", ["", "#", "b"], 2)
        self._entry(fr, "Octave", "pitch_octave", 3)
        self._entry(fr, "MIDI", "pitch_midi", 4)
        self._entry(fr, "Written pitch", "pitch_name_written", 5)
        self._entry(fr, "Sounding pitch", "pitch_name_sounding", 6)

    def _fill_range(self, fr: ttk.Frame) -> None:
        fr.columnconfigure(1, weight=1)
        self._combo(fr, "Lowest pitch", "pitch_lowest_name", [], 0)
        self._combo(fr, "Highest pitch", "pitch_highest_name", [], 1)

    def _fill_multiple(self, fr: ttk.Frame) -> None:
        fr.columnconfigure(1, weight=1)
        ttk.Label(fr, text="Pitch list (comma-separated)").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(fr, textvariable=self._var("pitch_names"), width=28).grid(row=0, column=1, sticky=tk.EW)
        self._seq_ordered = tk.BooleanVar(value=False)
        self._vars["pitch_sequence_ordered"] = self._seq_ordered
        ttk.Checkbutton(fr, text="Ordered sequence", variable=self._seq_ordered).grid(
            row=1, column=0, columnspan=2, sticky=tk.W
        )
        ttk.Label(fr, text="Search / pick:").grid(row=2, column=0, sticky=tk.W)
        self.multi_search = tk.StringVar()
        ent = ttk.Entry(fr, textvariable=self.multi_search, width=20)
        ent.grid(row=2, column=1, sticky=tk.W)
        ttk.Button(fr, text="Add pitch", command=self._add_searched_pitch).grid(row=3, column=1, sticky=tk.E)

    def _fill_open(self, fr: ttk.Frame) -> None:
        fr.columnconfigure(1, weight=1)
        self._entry(fr, "Open string", "open_string_name", 0)
        self._entry(fr, "Tuning", "open_string_tuning", 1)
        self._entry(fr, "Written pitch", "open_string_written", 2)
        self._entry(fr, "Sounding pitch", "open_string_sounding", 3)

    def _build_technique(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._combo(parent, "Left-hand regime", "left_hand_regime", self.choices["left_hand_regime"], 0)
        self._combo(parent, "Bow-contact regime", "bow_contact_regime", self.choices["bow_contact_regime"], 1)
        self._combo(parent, "Mute state", "mute_state", self.choices["mute_state"], 2)
        self._combo(parent, "Articulation", "articulation", self.choices["articulation"], 3)
        self._entry(parent, "Additional technique", "additional_technique", 4)
        self._combo(parent, "Legacy technique label", "technique", self.choices["legacy_technique"], 5)
        self._entry(parent, "Summary", "technique_display", 6)

    def _build_harmonic(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._combo(parent, "Natural / artificial", "harmonic_type", ["natural", "artificial", "half", "multiphonic", ""], 0)
        self._entry(parent, "String", "harmonic_string", 1)
        self._entry(parent, "Stopped pitch", "stopped_pitch_name", 2)
        self._entry(parent, "Touched pitch", "touched_pitch_name", 3)
        self._entry(parent, "Sounding pitch", "sounding_pitch_name", 4)
        self._entry(parent, "Harmonic order", "harmonic_order", 5)
        self._combo(
            parent,
            "Touch interval",
            "touched_interval",
            ["perfect_fourth", "major_third", "minor_third", "perfect_fifth", "P4", "M3", "m3", "P5", ""],
            6,
        )
        self._combo(
            parent,
            "Notation represents",
            "notation_represents",
            ["touched_pitch", "sounding_pitch", "both", "unresolved"],
            7,
        )

    def _collapsible(self, parent: tk.Misc, title: str, builder: Callable[[ttk.LabelFrame], None]) -> ttk.LabelFrame:
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.X, pady=2)
        visible = tk.BooleanVar(value=False)
        frame = ttk.LabelFrame(outer, text=title, padding=6)

        def toggle() -> None:
            if visible.get():
                frame.pack(fill=tk.X)
            else:
                frame.pack_forget()

        ttk.Checkbutton(outer, text=f"Show {title.lower()} panel", variable=visible, command=toggle).pack(anchor=tk.W)
        builder(frame)
        return frame

    def _build_bow(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._combo(
            parent,
            "Category",
            "bow_contact_category",
            self.choices["bow_contact_regime"],
            0,
        )
        self._entry(parent, "Beta", "relative_bow_bridge_distance_beta", 1)
        self._entry(parent, "Bow–bridge distance (m)", "bow_bridge_distance_m", 2)
        self._entry(parent, "Speaking length (m)", "speaking_length_m", 3)
        self._entry(parent, "Bow force (N)", "bow_force_n", 4)
        self._entry(parent, "Bow velocity (m/s)", "bow_velocity_m_s", 5)
        self._combo(
            parent,
            "Excitation region",
            "excitation_region",
            ["speaking_string", "directly_on_bridge", "afterlength_behind_bridge", ""],
            6,
        )

    def _build_mute(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._entry(parent, "Mute category", "mute_category", 0)
        self._entry(parent, "Material", "mute_material", 1)
        self._entry(parent, "Mass (e.g. 35 g)", "mute_mass", 2)
        self._entry(parent, "Model", "mute_model", 3)
        self._entry(parent, "Geometry", "mute_geometry", 4)
        self._entry(parent, "Mute type", "mute_type", 5)

    def _build_multi(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._entry(parent, "Configuration ID", "multiphonic_config_id", 0)
        self._entry(parent, "Touching-position ratio", "touching_position_ratio", 1)
        self._entry(parent, "Component pitches", "component_pitches", 2)
        self._entry(parent, "Partials", "observed_partials", 3)
        self._entry(parent, "Stability", "multiphonic_stability", 4)
        self._entry(parent, "Establishment time (s)", "establishment_time_s", 5)

    def _build_recording(self, parent: ttk.LabelFrame) -> None:
        parent.columnconfigure(1, weight=1)
        self._entry(parent, "Sample rate", "sample_rate_hz", 0)
        self._entry(parent, "Bit depth", "bit_depth", 1)
        self._entry(parent, "Channels", "channel_count", 2)
        self._entry(parent, "Microphone", "microphone", 3)
        self._entry(parent, "Distance (m)", "mic_distance_m", 4)
        self._entry(parent, "Room", "room", 5)
        self._entry(parent, "Gain (dB)", "gain_db", 6)
        self._entry(parent, "Recording date", "recording_date", 7)

    def _pitch_choices(self) -> list[str]:
        instrument = str(self._vars.get("instrument", tk.StringVar()).get() or "")
        pitches = self.registry.filter_instrument_range(
            instrument,
            show_all=bool(self.show_all_pitches.get()),
            instrument_ranges=self.ranges,
        )
        return [p.scientific_pitch for p in pitches]

    def _refresh_pitch_choices(self) -> None:
        self._show_pitch_mode()

    def _show_pitch_mode(self) -> None:
        mode = str(self._vars["pitch_mode"].get() or "unknown")
        for _name, fr in self._pitch_widgets.items():
            fr.pack_forget()
        fr = self._pitch_widgets.get(mode) or self._pitch_widgets["unknown"]
        fr.pack(fill=tk.X)
        values = self._pitch_choices()
        for child in fr.winfo_children():
            if isinstance(child, ttk.Combobox):
                child.configure(values=values)

    def _add_searched_pitch(self) -> None:
        q = self.multi_search.get().strip()
        hits = self.registry.search(
            q,
            instrument=str(self._vars["instrument"].get() or "") or None,
            show_all=bool(self.show_all_pitches.get()),
            instrument_ranges=self.ranges,
        )
        if not hits:
            return
        spn = hits[0].scientific_pitch
        cur = str(self._vars["pitch_names"].get() or "")
        names = [p.strip() for p in cur.split(",") if p.strip()]
        if spn not in names:
            names.append(spn)
        pitch_names_var = self._vars["pitch_names"]
        assert isinstance(pitch_names_var, tk.StringVar)
        pitch_names_var.set(", ".join(names))

    def clear(self) -> None:
        self._index = None
        self._loading = True
        for var in self._vars.values():
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            elif isinstance(var, tk.StringVar):
                var.set("")
        mode_var = self._vars["pitch_mode"]
        dyn_var = self._vars["dynamic"]
        assert isinstance(mode_var, tk.StringVar) and isinstance(dyn_var, tk.StringVar)
        mode_var.set("unknown")
        dyn_var.set("unknown")
        self._loading = False
        self.harmonic_frame.pack_forget()

    def load_record(self, record: MetadataEntryRecord, index: int | None = None) -> None:
        self._index = index
        self._loading = True
        data = record.model_dump()
        for key, var in self._vars.items():
            val = data.get(key)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(val))
                continue
            if not isinstance(var, tk.StringVar):
                continue
            if key == "pitch_names" and isinstance(val, list):
                var.set(", ".join(str(x) for x in val))
            elif val is None:
                var.set("")
            else:
                var.set(str(val))
        if not data.get("pitch_mode"):
            mode_var = self._vars["pitch_mode"]
            assert isinstance(mode_var, tk.StringVar)
            mode_var.set("unknown")
        self._show_pitch_mode()
        if harmonic_panel_visible(data):
            self.harmonic_frame.pack(fill=tk.X, pady=4)
        else:
            self.harmonic_frame.pack_forget()
        self._loading = False

    def _apply(self) -> None:
        if self._loading:
            return
        updates: dict[str, Any] = {}
        for key, var in self._vars.items():
            if isinstance(var, tk.BooleanVar):
                updates[key] = bool(var.get())
                continue
            if not isinstance(var, tk.StringVar):
                continue
            text = var.get().strip()
            if text == "":
                updates[key] = None
                continue
            if key in {
                "pitch_midi",
                "pitch_octave",
                "harmonic_order",
                "relative_bow_bridge_distance_beta",
                "bow_bridge_distance_m",
                "speaking_length_m",
                "bow_force_n",
                "bow_velocity_m_s",
                "sample_rate_hz",
                "bit_depth",
                "channel_count",
                "mic_distance_m",
                "gain_db",
                "touching_position_ratio",
                "establishment_time_s",
            }:
                try:
                    updates[key] = float(text) if "." in text else int(text)
                except ValueError:
                    updates[key] = text
            elif key == "pitch_names":
                updates[key] = [p.strip() for p in text.split(",") if p.strip()]
            else:
                updates[key] = text

        # Derive MIDI / letter from pitch_name when single_note
        if updates.get("pitch_mode") == "single_note" and updates.get("pitch_name"):
            rec = self.registry.get_by_spelling(str(updates["pitch_name"]))
            if rec:
                derived = list(updates.get("derived_fields") or [])
                if updates.get("pitch_midi") in (None, ""):
                    updates["pitch_midi"] = rec.midi
                    derived.append("pitch_midi")
                updates["pitch_letter"] = updates.get("pitch_letter") or rec.letter
                updates["pitch_accidental"] = updates.get("pitch_accidental")
                if updates.get("pitch_accidental") in (None, ""):
                    updates["pitch_accidental"] = rec.accidental
                updates["pitch_octave"] = updates.get("pitch_octave") or rec.octave
                # Preserve written/sounding without overwrite
                rep = updates.get("pitch_representation") or "unresolved"
                if rep in {"sounding", "both"} and not updates.get("pitch_name_sounding"):
                    updates["pitch_name_sounding"] = rec.scientific_pitch
                    updates["pitch_midi_sounding"] = rec.midi
                    derived.append("pitch_name_sounding")
                if rep in {"written", "both"} and not updates.get("pitch_name_written"):
                    updates["pitch_name_written"] = rec.scientific_pitch
                    updates["pitch_midi_written"] = rec.midi
                    derived.append("pitch_name_written")
                updates["derived_fields"] = derived

        # Map harmonic_string → string_name if string empty
        if updates.get("harmonic_string") and not updates.get("string_name"):
            updates["string_name"] = updates["harmonic_string"]

        self.on_change(self._index, updates)
