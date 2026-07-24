"""Deterministic source-priority resolver for calibrated harmonic descriptors.

Priority order (acceptance architecture):
  1. exact measured (same instrument, collection, technique, note, dynamic)
  2. same-instrument dynamic transfer within same collection + processing domain
  3. same-instrument multi-collection measured model (same note/dynamic)
  4. optional interpolation inside observed register (disabled by default)
  5. experimental cross-instrument transfer (disabled by default)
  6. unsupported / NA
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.baseline.pitch import pitch_name_to_midi
from string_technique_model.extrapolation.nonlinear.harmonic_support import (
    DEFAULT_ALLOW_CROSS_INSTRUMENT,
    DEFAULT_ALLOW_INTERPOLATION,
    DEFAULT_ALLOW_POOLED_ORDINARY_FALLBACK,
    DEFAULT_PROCESSING_VERSION,
    TRANSFER_FORMULA_ORDINARY_RATIO,
    HarmonicSupportClass,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_MEASURED_DIR = _REPO_ROOT / "data" / "harmonic_calibration" / "measured"
_MANIFEST_DIR = _REPO_ROOT / "data" / "harmonic_calibration" / "manifests"

_INSTRUMENT_ALIASES = {
    "violin": "vln",
    "vln": "vln",
    "viola": "vla",
    "vla": "vla",
    "cello": "vlc",
    "violoncello": "vlc",
    "vlc": "vlc",
    "double_bass": "cb",
    "contrabass": "cb",
    "cb": "cb",
}


def _norm_inst(instrument: str) -> str:
    return _INSTRUMENT_ALIASES.get(str(instrument).strip().lower(), str(instrument).strip().lower())


def _norm_tech(technique: str) -> str:
    t = str(technique).strip().lower()
    if t in {"arco_artificial_harmonic", "art_harm", "artificial"}:
        return "artificial_harmonic"
    if t in {"arco_natural_harmonic", "nat_harm", "natural"}:
        return "natural_harmonic"
    return t


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class OrdinaryAnchor:
    instrument: str
    collection: str
    note: str
    dynamic: str
    value: float
    quantity: str = "EWSD_score_acoustic_balanced"
    processing_version: str = DEFAULT_PROCESSING_VERSION
    record_id: str = ""


@dataclass
class CandidateRecord:
    priority: int
    support_class: str
    accepted: bool
    rejection_reason: str | None
    collection: str | None = None
    source_dynamic: str | None = None
    source_note: str | None = None
    source_instrument: str | None = None
    mean: float | None = None
    detail: str = ""


@dataclass
class HarmonicResolution:
    support_class: HarmonicSupportClass
    mean: float | None
    sd: float | None
    measured_or_extrapolated: str
    target_instrument: str
    target_technique: str
    target_dynamic: str
    target_note: str
    source_instrument: str | None = None
    source_collection: str | None = None
    source_technique: str | None = None
    source_dynamic: str | None = None
    source_note: str | None = None
    source_record_ids: list[str] = field(default_factory=list)
    ordinary_baseline_record_ids: list[str] = field(default_factory=list)
    transfer_method: str | None = None
    transfer_formula: str | None = None
    transfer_gate_status: str = "not_applicable"
    cross_instrument_transfer_enabled: bool = False
    interpolation_enabled: bool = False
    selection_reason: str = ""
    rejection_reason: str | None = None
    candidates: list[CandidateRecord] = field(default_factory=list)
    processing_version: str = DEFAULT_PROCESSING_VERSION
    na_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["support_class"] = self.support_class.value
        return d


@lru_cache(maxsize=4)
def load_raw_harmonic_calibration_table(measured_dir: str | None = None) -> pd.DataFrame:
    """Load per-collection measured rows (no cross-collection averaging)."""
    root = Path(measured_dir) if measured_dir else _DEFAULT_MEASURED_DIR
    cols = [
        "instrument",
        "technique",
        "dynamic",
        "note",
        "value",
        "collection",
        "quantity",
        "processing_version",
        "source_file",
        "source_hash",
        "record_id",
    ]
    if not root.is_dir():
        return pd.DataFrame(columns=cols)
    frames: list[pd.DataFrame] = []
    for path in sorted(root.glob("*.csv")):
        if path.stem.endswith("_smoke"):
            continue
        df = pd.read_csv(path)
        if "value" not in df.columns or "note" not in df.columns:
            continue
        df = df.copy()
        df["instrument"] = df.get("instrument", "vln").map(_norm_inst)
        df["technique"] = df["technique"].map(_norm_tech)
        df["dynamic"] = df["dynamic"].astype(str).str.strip().str.lower()
        df["note"] = df["note"].astype(str).str.strip()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df[df["value"].notna()]
        if df.empty:
            continue
        if "collection" not in df.columns:
            df["collection"] = path.stem
        df["collection"] = df["collection"].astype(str).str.strip().str.lower()
        # Expand multi-collection labels from legacy merges into one label only
        # (raw loads should already be single-collection files).
        df["quantity"] = df.get("quantity", "EWSD_score_acoustic_balanced")
        df["processing_version"] = df.get("processing_version", DEFAULT_PROCESSING_VERSION)
        df["processing_version"] = df["processing_version"].fillna(DEFAULT_PROCESSING_VERSION)
        df["source_file"] = str(path.as_posix())
        df["source_hash"] = _file_sha256(path)
        df["record_id"] = [
            f"{r.instrument}|{r.technique}|{r.collection}|{r.dynamic}|{r.note}|{path.stem}"
            for r in df.itertuples(index=False)
        ]
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


def clear_harmonic_calibration_cache() -> None:
    load_raw_harmonic_calibration_table.cache_clear()
    # Keep legacy alias cache clear for GUI reload
    try:
        from string_technique_model.extrapolation.nonlinear.harmonic_calibration_table import (
            clear_calibrated_harmonic_table_cache,
        )

        clear_calibrated_harmonic_table_cache()
    except Exception:
        pass


def has_calibrated_harmonic_coverage(
    instrument: str,
    technique: str,
    *,
    measured_dir: str | None = None,
) -> bool:
    table = load_raw_harmonic_calibration_table(measured_dir)
    if table.empty:
        return False
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    return bool(((table["instrument"] == inst) & (table["technique"] == tech)).any())


def _ordinary_lookup(
    ordinary_rows: list[OrdinaryAnchor] | None,
    *,
    instrument: str,
    collection: str,
    note: str,
    dynamic: str,
    quantity: str,
    processing_version: str,
) -> OrdinaryAnchor | None:
    if not ordinary_rows:
        return None
    hits = [
        o
        for o in ordinary_rows
        if _norm_inst(o.instrument) == instrument
        and str(o.collection).lower() == collection
        and str(o.note).strip() == note
        and str(o.dynamic).lower() == dynamic
        and str(o.quantity) == quantity
        and str(o.processing_version) == processing_version
    ]
    return hits[0] if hits else None


def resolve_harmonic_value(
    *,
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
    ordinary_rows: list[OrdinaryAnchor] | None = None,
    measured_dir: str | None = None,
    allow_interpolation: bool = DEFAULT_ALLOW_INTERPOLATION,
    allow_cross_instrument: bool = DEFAULT_ALLOW_CROSS_INSTRUMENT,
    allow_pooled_ordinary_fallback: bool = DEFAULT_ALLOW_POOLED_ORDINARY_FALLBACK,
    quantity: str = "EWSD_score_acoustic_balanced",
    processing_version: str = DEFAULT_PROCESSING_VERSION,
) -> HarmonicResolution:
    """Resolve one harmonic target with full candidate audit trail."""
    del allow_pooled_ordinary_fallback  # reserved; pooled fallback stays disabled
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    note_s = str(note).strip()
    dyn = str(dynamic).strip().lower()
    table = load_raw_harmonic_calibration_table(measured_dir)
    candidates: list[CandidateRecord] = []

    base_kwargs = dict(
        target_instrument=inst,
        target_technique=tech,
        target_dynamic=dyn,
        target_note=note_s,
        cross_instrument_transfer_enabled=allow_cross_instrument,
        interpolation_enabled=allow_interpolation,
        processing_version=processing_version,
        candidates=candidates,
    )

    same_inst = table[(table["instrument"] == inst) & (table["technique"] == tech)] if not table.empty else table
    if same_inst.empty:
        # Priority 5: cross-instrument (disabled by default)
        if allow_cross_instrument and not table.empty:
            candidates.append(
                CandidateRecord(
                    priority=5,
                    support_class=HarmonicSupportClass.CROSS_INSTRUMENT_TRANSFER.value,
                    accepted=False,
                    rejection_reason="cross_instrument_transfer_not_implemented",
                    detail="Flag enabled but no implemented cross-instrument model",
                )
            )
        else:
            candidates.append(
                CandidateRecord(
                    priority=5,
                    support_class=HarmonicSupportClass.CROSS_INSTRUMENT_TRANSFER.value,
                    accepted=False,
                    rejection_reason="cross_instrument_transfer_disabled",
                )
            )
        candidates.append(
            CandidateRecord(
                priority=6,
                support_class=HarmonicSupportClass.UNSUPPORTED.value,
                accepted=True,
                rejection_reason=None,
                detail="no_same_instrument_calibration_rows",
            )
        )
        return HarmonicResolution(
            support_class=HarmonicSupportClass.UNSUPPORTED,
            mean=None,
            sd=None,
            measured_or_extrapolated="unavailable",
            selection_reason="no_same_instrument_calibration_data",
            rejection_reason="no_same_instrument_calibration_data",
            na_reason="no_harmonic_acoustic_calibration_data",
            **base_kwargs,
        )

    # --- Priority 1: exact measured same collection ---
    exact = same_inst[(same_inst["note"] == note_s) & (same_inst["dynamic"] == dyn)]
    if not exact.empty:
        # Prefer single-collection rows; if multiple collections, still priority-1 only
        # when ONE collection has the exact key. Multi-collection → priority 3.
        by_coll = exact.groupby("collection", as_index=False).agg(
            value=("value", "mean"),
            record_id=("record_id", lambda s: ";".join(sorted(set(s)))),
            source_hash=("source_hash", "first"),
        )
        if len(by_coll) == 1:
            row = by_coll.iloc[0]
            candidates.append(
                CandidateRecord(
                    priority=1,
                    support_class=HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED.value,
                    accepted=True,
                    rejection_reason=None,
                    collection=str(row["collection"]),
                    source_dynamic=dyn,
                    source_note=note_s,
                    source_instrument=inst,
                    mean=float(row["value"]),
                )
            )
            return HarmonicResolution(
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED,
                mean=float(row["value"]),
                sd=None,
                measured_or_extrapolated="measured",
                source_instrument=inst,
                source_collection=str(row["collection"]),
                source_technique=tech,
                source_dynamic=dyn,
                source_note=note_s,
                source_record_ids=str(row["record_id"]).split(";"),
                transfer_method="exact_measured",
                transfer_gate_status="not_applicable",
                selection_reason="exact_same_instrument_collection_note_dynamic",
                **base_kwargs,
            )
        candidates.append(
            CandidateRecord(
                priority=1,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED.value,
                accepted=False,
                rejection_reason="multiple_collections_at_exact_key_defer_to_multi_collection",
                detail=f"collections={sorted(by_coll['collection'].tolist())}",
            )
        )
    else:
        candidates.append(
            CandidateRecord(
                priority=1,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED.value,
                accepted=False,
                rejection_reason="no_exact_measured_key",
            )
        )

    # --- Priority 2: same-collection dynamic transfer with ordinary ratio ---
    note_rows = same_inst[same_inst["note"] == note_s]
    preferred = ["mf", "p", "mp", "pp", "f", "ff"]
    transfer_attempted = False
    if not note_rows.empty:
        for collection, g in note_rows.groupby("collection"):
            coll = str(collection)
            src_row = None
            for d in preferred:
                hit = g[g["dynamic"] == d]
                if not hit.empty and d != dyn:
                    src_row = hit.iloc[0]
                    break
            if src_row is None:
                continue
            src_dyn = str(src_row["dynamic"])
            src_val = float(src_row["value"])
            src_pv = str(src_row.get("processing_version") or processing_version)
            o_src = _ordinary_lookup(
                ordinary_rows,
                instrument=inst,
                collection=coll,
                note=note_s,
                dynamic=src_dyn,
                quantity=quantity,
                processing_version=src_pv,
            )
            o_tgt = _ordinary_lookup(
                ordinary_rows,
                instrument=inst,
                collection=coll,
                note=note_s,
                dynamic=dyn,
                quantity=quantity,
                processing_version=src_pv,
            )
            transfer_attempted = True
            if o_src is None or o_tgt is None:
                candidates.append(
                    CandidateRecord(
                        priority=2,
                        support_class=HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER.value,
                        accepted=False,
                        rejection_reason="ordinary_same_note_pair_unavailable",
                        collection=coll,
                        source_dynamic=src_dyn,
                        source_note=note_s,
                        source_instrument=inst,
                        detail="require same-note ordinary at source and target dynamics; pooled GUI mean forbidden",
                    )
                )
                continue
            if o_src.value <= 0:
                candidates.append(
                    CandidateRecord(
                        priority=2,
                        support_class=HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER.value,
                        accepted=False,
                        rejection_reason="ordinary_source_non_positive",
                        collection=coll,
                        source_dynamic=src_dyn,
                    )
                )
                continue
            transferred = src_val * (float(o_tgt.value) / float(o_src.value))
            candidates.append(
                CandidateRecord(
                    priority=2,
                    support_class=HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER.value,
                    accepted=True,
                    rejection_reason=None,
                    collection=coll,
                    source_dynamic=src_dyn,
                    source_note=note_s,
                    source_instrument=inst,
                    mean=float(transferred),
                )
            )
            return HarmonicResolution(
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER,
                mean=float(transferred),
                sd=abs(transferred) * 0.15,
                measured_or_extrapolated="extrapolated",
                source_instrument=inst,
                source_collection=coll,
                source_technique=tech,
                source_dynamic=src_dyn,
                source_note=note_s,
                source_record_ids=[str(src_row["record_id"])],
                ordinary_baseline_record_ids=[
                    o_src.record_id or f"ord|{inst}|{coll}|{note_s}|{src_dyn}",
                    o_tgt.record_id or f"ord|{inst}|{coll}|{note_s}|{dyn}",
                ],
                transfer_method="ordinary_dynamic_ratio_same_collection_same_note",
                transfer_formula=TRANSFER_FORMULA_ORDINARY_RATIO,
                transfer_gate_status="passed",
                selection_reason="same_instrument_same_collection_dynamic_transfer",
                **base_kwargs,
            )
    if not transfer_attempted:
        candidates.append(
            CandidateRecord(
                priority=2,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_DYNAMIC_TRANSFER.value,
                accepted=False,
                rejection_reason="no_same_note_source_dynamic_for_transfer",
            )
        )

    # --- Priority 3: multi-collection measured at same note+dynamic ---
    if not exact.empty and exact["collection"].nunique() > 1:
        mean_val = float(exact["value"].mean())
        colls = "+".join(sorted(exact["collection"].astype(str).unique()))
        ids = sorted(exact["record_id"].astype(str).unique().tolist())
        candidates.append(
            CandidateRecord(
                priority=3,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED.value,
                accepted=True,
                rejection_reason=None,
                collection=colls,
                source_dynamic=dyn,
                source_note=note_s,
                source_instrument=inst,
                mean=mean_val,
            )
        )
        return HarmonicResolution(
            support_class=HarmonicSupportClass.SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED,
            mean=mean_val,
            sd=float(exact["value"].std(ddof=0)) if len(exact) > 1 else None,
            measured_or_extrapolated="measured",
            source_instrument=inst,
            source_collection=colls,
            source_technique=tech,
            source_dynamic=dyn,
            source_note=note_s,
            source_record_ids=ids,
            transfer_method="multi_collection_mean",
            transfer_gate_status="not_applicable",
            selection_reason="same_instrument_multi_collection_measured",
            **base_kwargs,
        )
    candidates.append(
        CandidateRecord(
            priority=3,
            support_class=HarmonicSupportClass.SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED.value,
            accepted=False,
            rejection_reason="no_multi_collection_exact_key",
        )
    )

    # --- Priority 4: interpolation (disabled by default) ---
    if allow_interpolation:
        candidates.append(
            CandidateRecord(
                priority=4,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_INTERPOLATED.value,
                accepted=False,
                rejection_reason="interpolation_not_implemented",
            )
        )
    else:
        candidates.append(
            CandidateRecord(
                priority=4,
                support_class=HarmonicSupportClass.SAME_INSTRUMENT_INTERPOLATED.value,
                accepted=False,
                rejection_reason="interpolation_disabled",
            )
        )

    # --- Priority 5: cross-instrument ---
    candidates.append(
        CandidateRecord(
            priority=5,
            support_class=HarmonicSupportClass.CROSS_INSTRUMENT_TRANSFER.value,
            accepted=False,
            rejection_reason=(
                "cross_instrument_transfer_disabled"
                if not allow_cross_instrument
                else "cross_instrument_transfer_not_implemented"
            ),
        )
    )

    # --- Priority 6: unsupported ---
    candidates.append(
        CandidateRecord(
            priority=6,
            support_class=HarmonicSupportClass.UNSUPPORTED.value,
            accepted=True,
            rejection_reason=None,
            detail="exhausted_priority_ladder",
        )
    )
    covered = bool(len(same_inst))
    return HarmonicResolution(
        support_class=HarmonicSupportClass.UNSUPPORTED,
        mean=None,
        sd=None,
        measured_or_extrapolated="unavailable",
        selection_reason="no_admissible_source_under_priority_gates",
        rejection_reason="no_admissible_source_under_priority_gates",
        na_reason=(
            "no_calibrated_harmonic_value_for_target"
            if covered
            else "no_harmonic_acoustic_calibration_data"
        ),
        transfer_gate_status="failed_or_not_applicable",
        **base_kwargs,
    )


def measured_notes_for(
    instrument: str,
    technique: str,
    *,
    measured_dir: str | None = None,
) -> set[str]:
    table = load_raw_harmonic_calibration_table(measured_dir)
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    sub = table[(table["instrument"] == inst) & (table["technique"] == tech)]
    return set(sub["note"].astype(str)) if not sub.empty else set()


def build_coverage_manifest_rows(
    *,
    instrument: str,
    techniques: tuple[str, ...] = ("artificial_harmonic", "natural_harmonic"),
    measured_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Machine-readable coverage rows for one instrument."""
    table = load_raw_harmonic_calibration_table(measured_dir)
    inst = _norm_inst(instrument)
    rows: list[dict[str, Any]] = []
    if table.empty:
        for tech in techniques:
            rows.append(
                {
                    "instrument": inst,
                    "collection": "",
                    "technique": tech,
                    "dynamic": "",
                    "measured_sounding_pitches": "",
                    "missing_sounding_pitches": "",
                    "min_measured_pitch": "",
                    "max_measured_pitch": "",
                    "n_measured_notes": 0,
                    "n_transferred_notes": 0,
                    "n_interpolated_notes": 0,
                    "n_unavailable_notes": "unknown_until_request_set",
                    "ssa_ewsd_version": DEFAULT_PROCESSING_VERSION,
                    "source_files": "",
                    "source_hashes": "",
                    "known_omissions": "no_calibration_tables",
                    "calibration_status": "unavailable",
                }
            )
        return rows

    sub_all = table[table["instrument"] == inst]
    for tech in techniques:
        tech_sub = sub_all[sub_all["technique"] == tech]
        if tech_sub.empty:
            rows.append(
                {
                    "instrument": inst,
                    "collection": "",
                    "technique": tech,
                    "dynamic": "",
                    "measured_sounding_pitches": "",
                    "missing_sounding_pitches": "",
                    "min_measured_pitch": "",
                    "max_measured_pitch": "",
                    "n_measured_notes": 0,
                    "n_transferred_notes": 0,
                    "n_interpolated_notes": 0,
                    "n_unavailable_notes": "unknown_until_request_set",
                    "ssa_ewsd_version": DEFAULT_PROCESSING_VERSION,
                    "source_files": "",
                    "source_hashes": "",
                    "known_omissions": "no_calibration_for_technique",
                    "calibration_status": "unavailable",
                }
            )
            continue
        for (collection, dynamic), g in tech_sub.groupby(["collection", "dynamic"]):
            notes = sorted(g["note"].astype(str).unique(), key=lambda n: (pitch_name_to_midi(n) or 999, n))
            files = sorted(g["source_file"].astype(str).unique())
            hashes = sorted(g["source_hash"].astype(str).unique())
            rows.append(
                {
                    "instrument": inst,
                    "collection": collection,
                    "technique": tech,
                    "dynamic": dynamic,
                    "measured_sounding_pitches": ";".join(notes),
                    "missing_sounding_pitches": "",  # filled relative to request sets at export time
                    "min_measured_pitch": notes[0] if notes else "",
                    "max_measured_pitch": notes[-1] if notes else "",
                    "n_measured_notes": len(notes),
                    "n_transferred_notes": 0,
                    "n_interpolated_notes": 0,
                    "n_unavailable_notes": "unknown_until_request_set",
                    "ssa_ewsd_version": DEFAULT_PROCESSING_VERSION,
                    "source_files": ";".join(files),
                    "source_hashes": ";".join(hashes),
                    "known_omissions": "",
                    "calibration_status": "calibrated_limited_coverage",
                }
            )
    return rows


def write_coverage_manifests(measured_dir: str | None = None) -> dict[str, Path]:
    _MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    mapping = {
        "vln": "coverage_violin_harmonics.csv",
        "vla": "coverage_viola_harmonics.csv",
        "vlc": "coverage_cello_harmonics.csv",
    }
    for inst, name in mapping.items():
        rows = build_coverage_manifest_rows(instrument=inst, measured_dir=measured_dir)
        path = _MANIFEST_DIR / name
        pd.DataFrame(rows).to_csv(path, index=False)
        out[inst] = path
    return out


def coverage_counts(
    instrument: str,
    technique: str,
    dynamic: str | None = None,
    *,
    measured_dir: str | None = None,
) -> int:
    """Unique sounding pitches for instrument×technique[×dynamic] from raw tables."""
    table = load_raw_harmonic_calibration_table(measured_dir)
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    sub = table[(table["instrument"] == inst) & (table["technique"] == tech)]
    if dynamic is not None:
        sub = sub[sub["dynamic"] == str(dynamic).lower()]
    if sub.empty:
        return 0
    return int(sub["note"].nunique())
