import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from app.schemas import InterviewSession, RunReport


class RunStorage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_run(self, report: RunReport) -> None:
        payload = report.model_dump(mode="json")
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, created_at, jd_profile_json, report_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    report.run_id,
                    report.created_at.isoformat(),
                    json.dumps(payload["jd_profile"], ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_run(self, run_id: str) -> Optional[RunReport]:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute("SELECT report_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return RunReport.model_validate(json.loads(row[0]))

    def list_runs(self) -> List[RunReport]:
        with sqlite3.connect(self.database_path) as conn:
            rows = conn.execute(
                "SELECT report_json FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [RunReport.model_validate(json.loads(row[0])) for row in rows]

    def save_interview_session(self, session: InterviewSession) -> None:
        payload = session.model_dump(mode="json")
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO interview_sessions
                    (session_id, run_id, candidate_id, status, updated_at, session_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.run_id,
                    session.candidate_id,
                    session.status,
                    session.updated_at.isoformat(),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_interview_session(self, session_id: str) -> Optional[InterviewSession]:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(
                "SELECT session_json FROM interview_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return InterviewSession.model_validate(json.loads(row[0]))

    def list_interview_sessions(self, run_id: Optional[str] = None) -> List[InterviewSession]:
        with sqlite3.connect(self.database_path) as conn:
            if run_id:
                rows = conn.execute(
                    """
                    SELECT session_json FROM interview_sessions
                    WHERE run_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT session_json FROM interview_sessions ORDER BY updated_at DESC"
                ).fetchall()
        return [InterviewSession.model_validate(json.loads(row[0])) for row in rows]

    def delete_interview_session(self, session_id: str) -> bool:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                "DELETE FROM interview_sessions WHERE session_id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0

    def get_setting(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO app_settings (key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )

    def _init_db(self) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    jd_profile_json TEXT NOT NULL,
                    report_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_sessions (
                    session_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    session_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interview_sessions_run_candidate
                ON interview_sessions (run_id, candidate_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
