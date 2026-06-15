import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from app.schemas import InterviewSession, RunReport, ResumeQualityReport, VoiceInterviewSession


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

    def delete_run(self, run_id: str) -> bool:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        return cursor.rowcount > 0

    def delete_all_runs(self) -> int:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("DELETE FROM runs")
        return cursor.rowcount

    def get_latest_run_by_jd_text_hash(self, jd_text_hash: str) -> Optional[RunReport]:
        for report in self.list_runs():
            if report.metadata.jd_text_hash == jd_text_hash:
                return report
        return None

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

    def delete_all_interview_sessions(self) -> int:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("DELETE FROM interview_sessions")
        return cursor.rowcount

    def save_voice_interview_session(self, session: VoiceInterviewSession) -> None:
        payload = session.model_dump(mode="json")
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO voice_interview_sessions
                    (voice_session_id, interview_session_id, status, updated_at, session_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.voice_session_id,
                    session.interview_session_id,
                    session.status,
                    session.updated_at.isoformat(),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_voice_interview_session(self, voice_session_id: str) -> Optional[VoiceInterviewSession]:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(
                "SELECT session_json FROM voice_interview_sessions WHERE voice_session_id = ?",
                (voice_session_id,),
            ).fetchone()
        if not row:
            return None
        return VoiceInterviewSession.model_validate(json.loads(row[0]))

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
                CREATE TABLE IF NOT EXISTS resume_documents (
                    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    content_type TEXT,
                    storage_key TEXT,
                    storage_url TEXT,
                    resume_text TEXT NOT NULL,
                    analyze_status TEXT NOT NULL DEFAULT 'PENDING',
                    analyze_error TEXT,
                    uploaded_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resume_analyses (
                    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resume_id INTEGER NOT NULL,
                    overall_score INTEGER NOT NULL,
                    project_score INTEGER NOT NULL,
                    skill_match_score INTEGER NOT NULL,
                    content_score INTEGER NOT NULL,
                    structure_score INTEGER NOT NULL,
                    expression_score INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    strengths_json TEXT,
                    suggestions_json TEXT,
                    original_text TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (resume_id) REFERENCES resume_documents (resume_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_resume_analyses_resume_id_created_at
                ON resume_analyses (resume_id, created_at DESC)
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_interview_sessions (
                    voice_session_id TEXT PRIMARY KEY,
                    interview_session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    session_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_voice_interview_sessions_interview_session
                ON voice_interview_sessions (interview_session_id)
                """
            )

    def save_resume_record(
        self,
        file_hash: str,
        filename: str,
        file_size: int,
        content_type: Optional[str],
        resume_text: str,
        storage_key: str = "",
        storage_url: str = "",
    ) -> int:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO resume_documents (
                    file_hash,
                    filename,
                    file_size,
                    content_type,
                    storage_key,
                    storage_url,
                    resume_text,
                    analyze_status,
                    analyze_error,
                    uploaded_at,
                    updated_at,
                    access_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', NULL, ?, ?, 1)
                """,
                (file_hash, filename, file_size, content_type, storage_key, storage_url, resume_text, now, now),
            )
            return cursor.lastrowid

    def get_resume_by_hash(self, file_hash: str) -> Optional[dict[str, object]]:
        row = self._get_resume_row_by_hash(file_hash)
        if not row:
            return None
        return self._resume_row_to_dict(row)

    def _get_resume_row_by_hash(self, file_hash: str) -> Optional[sqlite3.Row]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM resume_documents WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()

    def get_resume(self, resume_id: int) -> Optional[dict[str, object]]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM resume_documents WHERE resume_id = ?",
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return self._resume_row_to_dict(row)

    def list_resumes(self) -> List[dict[str, object]]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    d.resume_id AS resume_id,
                    d.filename,
                    d.file_size,
                    d.uploaded_at,
                    d.access_count,
                    d.analyze_status,
                    d.analyze_error,
                    a.overall_score AS latest_score,
                    a.created_at AS last_analyzed_at
                FROM resume_documents d
                LEFT JOIN resume_analyses a
                ON a.analysis_id = (
                    SELECT ra.analysis_id
                    FROM resume_analyses ra
                    WHERE ra.resume_id = d.resume_id
                    ORDER BY datetime(ra.created_at) DESC
                    LIMIT 1
                )
                ORDER BY datetime(d.uploaded_at) DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def increment_resume_access_count(self, resume_id: int) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                UPDATE resume_documents
                SET access_count = access_count + 1,
                    updated_at = ?
                WHERE resume_id = ?
                """,
                (now, resume_id),
            )

    def set_resume_analysis_status(
        self,
        resume_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                UPDATE resume_documents
                SET analyze_status = ?, analyze_error = ?, updated_at = ?
                WHERE resume_id = ?
                """,
                (status, error, now, resume_id),
            )

    def save_resume_analysis(
        self,
        resume_id: int,
        report: ResumeQualityReport,
        original_text: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        score_detail = report.score_detail
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT INTO resume_analyses (
                    resume_id,
                    overall_score,
                    project_score,
                    skill_match_score,
                    content_score,
                    structure_score,
                    expression_score,
                    summary,
                    strengths_json,
                    suggestions_json,
                    original_text,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resume_id,
                    int(report.overall_score),
                    int(score_detail.project_score),
                    int(score_detail.skill_match_score),
                    int(score_detail.content_score),
                    int(score_detail.structure_score),
                    int(score_detail.expression_score),
                    report.summary or "",
                    json.dumps([item for item in report.strengths], ensure_ascii=False),
                    json.dumps([item.model_dump(mode="json") for item in report.suggestions], ensure_ascii=False),
                    original_text,
                    now,
                ),
            )

    def get_latest_resume_analysis(self, resume_id: int) -> Optional[dict[str, object]]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM resume_analyses
                WHERE resume_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """,
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_resume_analyses(self, resume_id: int) -> List[dict[str, object]]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM resume_analyses
                WHERE resume_id = ?
                ORDER BY datetime(created_at) DESC
                """,
                (resume_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_resume(self, resume_id: int) -> bool:
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute("DELETE FROM resume_documents WHERE resume_id = ?", (resume_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                conn.execute("DELETE FROM resume_analyses WHERE resume_id = ?", (resume_id,))
            return deleted

    def delete_all_resumes(self) -> int:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("DELETE FROM resume_analyses")
            cursor = conn.execute("DELETE FROM resume_documents")
            return cursor.rowcount

    def get_resume_file_text(self, resume_id: int) -> Optional[str]:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(
                "SELECT resume_text FROM resume_documents WHERE resume_id = ?",
                (resume_id,),
            ).fetchone()
        if row is None:
            return None
        return row[0]

    def _resume_row_to_dict(self, row: sqlite3.Row) -> dict[str, object]:
        return {
            "resume_id": row["resume_id"],
            "filename": row["filename"],
            "file_size": row["file_size"],
            "content_type": row["content_type"],
            "storage_key": row["storage_key"] or "",
            "storage_url": row["storage_url"] or "",
            "resume_text": row["resume_text"],
            "analyze_status": row["analyze_status"],
            "analyze_error": row["analyze_error"],
            "uploaded_at": row["uploaded_at"],
            "updated_at": row["updated_at"],
            "access_count": row["access_count"],
        }
