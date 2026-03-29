"""SQLite-based historical usage tracker."""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_DIR = Path.home() / ".claude" / "plugins" / "my-claude-monitor"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "usage_history.db"

SCHEMA_VERSION = 1

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS usage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    timestamp_iso TEXT NOT NULL,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    five_hour_pct REAL,
    seven_day_pct REAL,
    session_duration_ms INTEGER DEFAULT 0,
    project_name TEXT,
    project_dir TEXT,
    context_used_pct INTEGER DEFAULT 0,
    context_window_size INTEGER DEFAULT 0
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON usage_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshots_project ON usage_snapshots(project_name);
"""

CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class UsageTracker:
    """Logs usage snapshots to a local SQLite database."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None

    def _ensure_db(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(CREATE_TABLE + CREATE_INDEX + CREATE_META)
        conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        self._conn = conn
        return conn

    def log_snapshot(
        self,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        five_hour_pct: float | None = None,
        seven_day_pct: float | None = None,
        session_duration_ms: int = 0,
        project_name: str = "",
        project_dir: str = "",
        context_used_pct: int = 0,
        context_window_size: int = 0,
    ) -> None:
        """Log a single usage snapshot."""
        try:
            conn = self._ensure_db()
            now = time.time()
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO usage_snapshots
                   (timestamp, timestamp_iso, model, input_tokens, output_tokens,
                    cost_usd, five_hour_pct, seven_day_pct, session_duration_ms,
                    project_name, project_dir, context_used_pct, context_window_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (now, now_iso, model, input_tokens, output_tokens,
                 cost_usd, five_hour_pct, seven_day_pct, session_duration_ms,
                 project_name, project_dir, context_used_pct, context_window_size),
            )
            conn.commit()
        except Exception:
            pass  # Never crash the statusline for tracking failures

    def get_daily_summary(self, days: int = 7) -> list[dict]:
        """Get daily usage summary for the last N days."""
        conn = self._ensure_db()
        cutoff = time.time() - (days * 86400)
        rows = conn.execute(
            """SELECT
                date(timestamp_iso) as day,
                COUNT(*) as snapshots,
                MAX(input_tokens) as max_input_tokens,
                MAX(output_tokens) as max_output_tokens,
                MAX(cost_usd) as max_cost_usd,
                MAX(five_hour_pct) as peak_5h_pct,
                MAX(seven_day_pct) as peak_7d_pct,
                MAX(session_duration_ms) as max_duration_ms,
                COUNT(DISTINCT project_name) as projects_count
               FROM usage_snapshots
               WHERE timestamp > ?
               GROUP BY date(timestamp_iso)
               ORDER BY day DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_weekly_summary(self, weeks: int = 4) -> list[dict]:
        """Get weekly usage summary."""
        conn = self._ensure_db()
        cutoff = time.time() - (weeks * 7 * 86400)
        rows = conn.execute(
            """SELECT
                strftime('%Y-W%W', timestamp_iso) as week,
                COUNT(*) as snapshots,
                MAX(cost_usd) as max_cost_usd,
                MAX(five_hour_pct) as peak_5h_pct,
                MAX(seven_day_pct) as peak_7d_pct,
                COUNT(DISTINCT project_name) as projects_count
               FROM usage_snapshots
               WHERE timestamp > ?
               GROUP BY strftime('%Y-W%W', timestamp_iso)
               ORDER BY week DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_project_stats(self, days: int = 30) -> list[dict]:
        """Get most expensive projects."""
        conn = self._ensure_db()
        cutoff = time.time() - (days * 86400)
        rows = conn.execute(
            """SELECT
                project_name,
                COUNT(*) as snapshots,
                MAX(cost_usd) as max_cost_usd,
                MAX(input_tokens) as max_input_tokens,
                MAX(output_tokens) as max_output_tokens,
                AVG(session_duration_ms) as avg_duration_ms,
                MAX(session_duration_ms) as max_duration_ms,
                MAX(five_hour_pct) as peak_5h_pct
               FROM usage_snapshots
               WHERE timestamp > ? AND project_name != ''
               GROUP BY project_name
               ORDER BY max_cost_usd DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session_stats(self, days: int = 30) -> dict:
        """Get overall session statistics."""
        conn = self._ensure_db()
        cutoff = time.time() - (days * 86400)
        row = conn.execute(
            """SELECT
                COUNT(*) as total_snapshots,
                COUNT(DISTINCT date(timestamp_iso)) as active_days,
                COUNT(DISTINCT project_name) as total_projects,
                MAX(cost_usd) as total_max_cost,
                AVG(session_duration_ms) as avg_duration_ms,
                MAX(five_hour_pct) as peak_5h_pct,
                MAX(seven_day_pct) as peak_7d_pct,
                SUM(CASE WHEN five_hour_pct >= 80 THEN 1 ELSE 0 END) as times_over_80
               FROM usage_snapshots
               WHERE timestamp > ?""",
            (cutoff,),
        ).fetchone()
        return dict(row) if row else {}

    def get_all_snapshots_json(self, days: int = 7) -> list[dict]:
        """Get raw snapshots as dicts for JSON export."""
        conn = self._ensure_db()
        cutoff = time.time() - (days * 86400)
        rows = conn.execute(
            """SELECT * FROM usage_snapshots
               WHERE timestamp > ?
               ORDER BY timestamp DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
