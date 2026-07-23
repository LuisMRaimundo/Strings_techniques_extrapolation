"""SQLite persistence for manual drafts, versions, mappings, and audit."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS manual_collections (
    collection_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    collection_type TEXT NOT NULL,
    collection_role TEXT NOT NULL,
    metric_definition_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    measured_or_estimated TEXT NOT NULL,
    source_description TEXT NOT NULL,
    workflow_state TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    commit_id TEXT,
    superseded_by TEXT
);

CREATE TABLE IF NOT EXISTS manual_collection_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    workflow_state TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    user TEXT,
    timestamp_utc TEXT NOT NULL,
    reason TEXT,
    UNIQUE(collection_id, version_no)
);

CREATE TABLE IF NOT EXISTS manual_records (
    record_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    record_version INTEGER NOT NULL,
    record_status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    fingerprint TEXT,
    supersedes_record_id TEXT,
    created_by TEXT,
    created_at_utc TEXT NOT NULL,
    last_edit_by TEXT,
    last_edit_at_utc TEXT NOT NULL,
    input_method TEXT
);

CREATE TABLE IF NOT EXISTS manual_record_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    record_version INTEGER NOT NULL,
    collection_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    record_status TEXT NOT NULL,
    user TEXT,
    timestamp_utc TEXT NOT NULL,
    reason TEXT,
    supersedes_record_id TEXT,
    UNIQUE(record_id, record_version)
);

CREATE TABLE IF NOT EXISTS technique_mappings (
    original_label TEXT PRIMARY KEY,
    canonical_code TEXT,
    mapping_status TEXT NOT NULL,
    justification TEXT,
    user TEXT,
    timestamp_utc TEXT NOT NULL,
    mapping_version TEXT
);

CREATE TABLE IF NOT EXISTS dynamic_mappings (
    original_label TEXT PRIMARY KEY,
    canonical_code TEXT,
    mapping_status TEXT NOT NULL,
    justification TEXT,
    user TEXT,
    timestamp_utc TEXT NOT NULL,
    mapping_version TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id TEXT,
    record_id TEXT,
    action TEXT NOT NULL,
    user TEXT,
    timestamp_utc TEXT NOT NULL,
    detail_json TEXT
);

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    status TEXT NOT NULL,
    report_json TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ManualEntryStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def collection_exists(self, collection_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM manual_collections WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()
            return row is not None

    def upsert_draft_collection(self, meta: dict[str, Any], *, user: str | None = None) -> None:
        now = utc_now()
        cid = meta["collection_id"]
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT created_at_utc FROM manual_collections WHERE collection_id = ?",
                (cid,),
            ).fetchone()
            created = existing["created_at_utc"] if existing else now
            conn.execute(
                """
                INSERT INTO manual_collections (
                    collection_id, display_name, collection_type, collection_role,
                    metric_definition_id, created_by, measured_or_estimated,
                    source_description, workflow_state, metadata_json,
                    created_at_utc, updated_at_utc, commit_id, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    collection_type=excluded.collection_type,
                    collection_role=excluded.collection_role,
                    metric_definition_id=excluded.metric_definition_id,
                    created_by=excluded.created_by,
                    measured_or_estimated=excluded.measured_or_estimated,
                    source_description=excluded.source_description,
                    workflow_state=excluded.workflow_state,
                    metadata_json=excluded.metadata_json,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    cid,
                    meta["display_name"],
                    meta["collection_type"],
                    meta["collection_role"],
                    meta["metric_definition_id"],
                    meta["created_by"],
                    meta["measured_or_estimated"],
                    meta["source_description"],
                    meta.get("workflow_state", "draft"),
                    json.dumps(meta, ensure_ascii=True, default=str),
                    created,
                    now,
                    meta.get("commit_id"),
                    meta.get("superseded_by"),
                ),
            )
            ver = conn.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 AS n FROM manual_collection_versions WHERE collection_id = ?",
                (cid,),
            ).fetchone()["n"]
            conn.execute(
                """
                INSERT INTO manual_collection_versions (
                    collection_id, version_no, workflow_state, metadata_json, user, timestamp_utc, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    ver,
                    meta.get("workflow_state", "draft"),
                    json.dumps(meta, ensure_ascii=True, default=str),
                    user or meta.get("created_by"),
                    now,
                    meta.get("version_reason"),
                ),
            )
            self._audit(
                conn,
                cid,
                None,
                "upsert_draft_collection",
                user or meta.get("created_by"),
                {"version_no": ver},
            )

    def replace_draft_records(
        self,
        collection_id: str,
        records: list[dict[str, Any]],
        *,
        user: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            # Keep version history of previous drafts
            old = conn.execute(
                "SELECT * FROM manual_records WHERE collection_id = ? AND record_status = 'draft'",
                (collection_id,),
            ).fetchall()
            for row in old:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO manual_record_versions (
                        record_id, record_version, collection_id, payload_json,
                        record_status, user, timestamp_utc, reason, supersedes_record_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["record_id"],
                        row["record_version"],
                        collection_id,
                        row["payload_json"],
                        row["record_status"],
                        user,
                        now,
                        "replaced_draft",
                        row["supersedes_record_id"],
                    ),
                )
            conn.execute(
                "DELETE FROM manual_records WHERE collection_id = ? AND record_status = 'draft'",
                (collection_id,),
            )
            for rec in records:
                conn.execute(
                    """
                    INSERT INTO manual_records (
                        record_id, collection_id, record_version, record_status,
                        payload_json, fingerprint, supersedes_record_id,
                        created_by, created_at_utc, last_edit_by, last_edit_at_utc, input_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec["record_id"],
                        collection_id,
                        int(rec.get("record_version", 1)),
                        rec.get("record_status", "draft"),
                        json.dumps(rec, ensure_ascii=True, default=str),
                        rec.get("fingerprint"),
                        rec.get("supersedes_record_id"),
                        rec.get("created_by") or user,
                        rec.get("created_at_utc") or now,
                        rec.get("last_edit_by") or user,
                        now,
                        rec.get("input_method"),
                    ),
                )
            self._audit(conn, collection_id, None, "replace_draft_records", user, {"n": len(records)})

    def load_draft_records(self, collection_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM manual_records WHERE collection_id = ? AND record_status = 'draft' ORDER BY record_id",
                (collection_id,),
            ).fetchall()
            return [json.loads(r["payload_json"]) for r in rows]

    def load_collection_meta(self, collection_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT metadata_json, workflow_state, commit_id FROM manual_collections WHERE collection_id = ?",
                (collection_id,),
            ).fetchone()
            if not row:
                return None
            meta = json.loads(row["metadata_json"])
            meta["workflow_state"] = row["workflow_state"]
            meta["commit_id"] = row["commit_id"]
            return meta

    def set_workflow_state(self, collection_id: str, state: str, *, user: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE manual_collections SET workflow_state = ?, updated_at_utc = ? WHERE collection_id = ?",
                (state, utc_now(), collection_id),
            )
            self._audit(conn, collection_id, None, "set_workflow_state", user, {"state": state})

    def mark_committed(
        self,
        collection_id: str,
        *,
        commit_id: str,
        user: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE manual_collections
                SET workflow_state = 'committed', commit_id = ?, updated_at_utc = ?
                WHERE collection_id = ?
                """,
                (commit_id, now, collection_id),
            )
            conn.execute(
                """
                UPDATE manual_records
                SET record_status = 'committed', last_edit_at_utc = ?
                WHERE collection_id = ? AND record_status = 'draft'
                """,
                (now, collection_id),
            )
            self._audit(conn, collection_id, None, "commit", user, {"commit_id": commit_id})

    def save_validation(self, collection_id: str, report: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO validation_results (collection_id, timestamp_utc, status, report_json)
                VALUES (?, ?, ?, ?)
                """,
                (collection_id, utc_now(), report.get("status"), json.dumps(report, ensure_ascii=True)),
            )

    def supersede_record(
        self,
        old_record_id: str,
        new_record: dict[str, Any],
        *,
        user: str,
        reason: str,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            old = conn.execute(
                "SELECT * FROM manual_records WHERE record_id = ?",
                (old_record_id,),
            ).fetchone()
            if not old:
                raise KeyError(old_record_id)
            conn.execute(
                """
                INSERT INTO manual_record_versions (
                    record_id, record_version, collection_id, payload_json,
                    record_status, user, timestamp_utc, reason, supersedes_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    old["record_id"],
                    old["record_version"],
                    old["collection_id"],
                    old["payload_json"],
                    old["record_status"],
                    user,
                    now,
                    reason,
                    old["supersedes_record_id"],
                ),
            )
            conn.execute(
                "UPDATE manual_records SET record_status = 'superseded', last_edit_by = ?, last_edit_at_utc = ? WHERE record_id = ?",
                (user, now, old_record_id),
            )
            new_record = dict(new_record)
            new_record["supersedes_record_id"] = old_record_id
            new_record["record_version"] = int(old["record_version"]) + 1
            new_record.setdefault("record_status", "draft")
            conn.execute(
                """
                INSERT INTO manual_records (
                    record_id, collection_id, record_version, record_status,
                    payload_json, fingerprint, supersedes_record_id,
                    created_by, created_at_utc, last_edit_by, last_edit_at_utc, input_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_record["record_id"],
                    new_record["collection_id"],
                    new_record["record_version"],
                    new_record["record_status"],
                    json.dumps(new_record, ensure_ascii=True, default=str),
                    new_record.get("fingerprint"),
                    old_record_id,
                    new_record.get("created_by") or user,
                    new_record.get("created_at_utc") or now,
                    user,
                    now,
                    new_record.get("input_method"),
                ),
            )
            self._audit(
                conn,
                new_record["collection_id"],
                new_record["record_id"],
                "supersede_record",
                user,
                {"old": old_record_id, "reason": reason},
            )

    def logical_delete_record(self, record_id: str, *, user: str, reason: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            old = conn.execute(
                "SELECT * FROM manual_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if not old:
                raise KeyError(record_id)
            conn.execute(
                """
                INSERT INTO manual_record_versions (
                    record_id, record_version, collection_id, payload_json,
                    record_status, user, timestamp_utc, reason, supersedes_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    old["record_id"],
                    old["record_version"],
                    old["collection_id"],
                    old["payload_json"],
                    old["record_status"],
                    user,
                    now,
                    reason,
                    old["supersedes_record_id"],
                ),
            )
            conn.execute(
                "UPDATE manual_records SET record_status = 'deleted_logically', last_edit_by = ?, last_edit_at_utc = ? WHERE record_id = ?",
                (user, now, record_id),
            )
            self._audit(conn, old["collection_id"], record_id, "logical_delete", user, {"reason": reason})

    def list_record_versions(self, record_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM manual_record_versions WHERE record_id = ? ORDER BY record_version",
                (record_id,),
            ).fetchall()
            out = []
            for r in rows:
                payload = json.loads(r["payload_json"])
                payload["record_status_at_version"] = r["record_status"]
                payload["version_user"] = r["user"]
                payload["version_timestamp_utc"] = r["timestamp_utc"]
                payload["version_reason"] = r["reason"]
                out.append(payload)
            return out

    def audit_rows(self, collection_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE collection_id = ? ORDER BY audit_id",
                (collection_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_collections(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT collection_id, display_name, workflow_state, collection_role, commit_id FROM manual_collections ORDER BY collection_id"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _audit(
        conn: sqlite3.Connection,
        collection_id: str | None,
        record_id: str | None,
        action: str,
        user: str | None,
        detail: dict[str, Any] | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log (collection_id, record_id, action, user, timestamp_utc, detail_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                record_id,
                action,
                user,
                utc_now(),
                json.dumps(detail or {}, ensure_ascii=True),
            ),
        )
