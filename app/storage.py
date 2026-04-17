from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import APP_DATA_DIR, JOB_DB_PATH, JOB_DIR, UPLOAD_DIR


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: Path = JOB_DB_PATH):
        self.db_path = db_path
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT,
                    source_type TEXT NOT NULL,
                    source_value TEXT,
                    error TEXT,
                    progress REAL DEFAULT 0,
                    progress_label TEXT,
                    work_dir TEXT NOT NULL,
                    normalized_audio_path TEXT,
                    midi_path TEXT,
                    musicxml_path TEXT,
                    chords_path TEXT,
                    summary_path TEXT,
                    duration_seconds REAL
                )
                """
            )

    def create_job(self, job_id: str, source_type: str, source_value: str | None, title: str | None = None) -> dict[str, Any]:
        work_dir = (JOB_DIR / job_id).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        now = utcnow()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, created_at, updated_at, status, title, source_type, source_value, work_dir)
                VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (job_id, now, now, title, source_type, source_value, str(work_dir)),
            )
        return self.get_job(job_id)

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        if not fields:
            return self.get_job(job_id)
        fields["updated_at"] = utcnow()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [job_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        data = dict(row)
        return self._augment_job(data)

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._augment_job(dict(row)) for row in rows]

    def _augment_job(self, row: dict[str, Any]) -> dict[str, Any]:
        if row.get("chords_path"):
            chords_path = Path(row["chords_path"])
            if chords_path.exists():
                row["chords"] = json.loads(chords_path.read_text(encoding="utf-8"))
            else:
                row["chords"] = []
        else:
            row["chords"] = []
        if row.get("summary_path"):
            summary_path = Path(row["summary_path"])
            if summary_path.exists():
                row["summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
            else:
                row["summary"] = {}
        else:
            row["summary"] = {}
        return row
