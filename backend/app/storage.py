import json
import sqlite3
from pathlib import Path
from typing import Optional

from app.schemas import RunReport


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

