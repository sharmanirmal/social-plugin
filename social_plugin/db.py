"""SQLite database manager — schema creation, migrations, and query helpers."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from social_plugin.utils.logger import get_logger

logger = get_logger()

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- All trending topics fetched daily
CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT,
    author TEXT,
    relevance_score REAL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date TEXT NOT NULL
);

-- Source documents read from Google Docs / PDFs / local files
CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT,
    content TEXT,
    content_hash TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- All generated drafts with full lifecycle tracking
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    content TEXT NOT NULL,
    hashtags TEXT,
    tone TEXT,
    source_reference TEXT,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    posted_at TIMESTAMP,
    post_url TEXT,
    reviewer_notes TEXT,
    error_message TEXT,
    generation_model TEXT,
    generation_tokens INTEGER,
    generation_cost REAL
);

-- Posted content tracking + engagement analytics
CREATE TABLE IF NOT EXISTS post_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id TEXT NOT NULL REFERENCES drafts(id),
    platform TEXT NOT NULL,
    post_url TEXT,
    posted_at TIMESTAMP,
    likes INTEGER DEFAULT 0,
    retweets INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    last_checked_at TIMESTAMP,
    UNIQUE(draft_id)
);

-- Daily run log for pipeline auditing
CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,
    summary TEXT,
    error TEXT
);

-- Config history for audit trail
CREATE TABLE IF NOT EXISTS config_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_hash TEXT,
    config_yaml TEXT
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class Database:
    """SQLite database manager for social-plugin state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        with self.connection() as conn:
            yield conn.cursor()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            # Track schema version
            cur = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            logger.debug("Database initialized at %s", self.db_path)

    # --- Generic helpers ---

    def execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()

    def execute_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def insert(self, table: str, data: dict[str, Any]) -> int | str:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        with self.connection() as conn:
            cur = conn.execute(sql, tuple(data.values()))
            return cur.lastrowid

    def update(self, table: str, data: dict[str, Any], where: str, params: tuple = ()) -> int:
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        with self.connection() as conn:
            cur = conn.execute(sql, tuple(data.values()) + params)
            return cur.rowcount

    # --- Trends ---

    def insert_trend(self, trend: dict) -> int:
        return self.insert("trends", trend)

    def get_trends(self, date: str, source: str | None = None, limit: int = 20) -> list[sqlite3.Row]:
        sql = "SELECT * FROM trends WHERE date = ?"
        params: list = [date]
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY relevance_score DESC LIMIT ?"
        params.append(limit)
        return self.execute(sql, tuple(params))

    # --- Source Documents ---

    def insert_source_document(self, doc: dict) -> int:
        return self.insert("source_documents", doc)

    def get_source_document_by_path(self, source_path: str) -> sqlite3.Row | None:
        return self.execute_one(
            "SELECT * FROM source_documents WHERE source_path = ? ORDER BY fetched_at DESC LIMIT 1",
            (source_path,),
        )

    def get_recent_source_documents(self, hours: int = 24) -> list[sqlite3.Row]:
        return self.execute(
            "SELECT * FROM source_documents WHERE fetched_at > datetime('now', ?)",
            (f"-{hours} hours",),
        )

    # --- Drafts ---

    def insert_draft(self, draft: dict) -> str:
        self.insert("drafts", draft)
        return draft["id"]

    def get_draft(self, draft_id: str) -> sqlite3.Row | None:
        return self.execute_one("SELECT * FROM drafts WHERE id = ?", (draft_id,))

    def get_drafts_by_status(self, status: str, platform: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM drafts WHERE status = ?"
        params: list = [status]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY created_at DESC"
        return self.execute(sql, tuple(params))

    def update_draft_status(self, draft_id: str, status: str, **extra: Any) -> int:
        data = {"status": status}
        data.update(extra)
        return self.update("drafts", data, "id = ?", (draft_id,))

    def get_recent_drafts(self, days: int = 7, platform: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM drafts WHERE created_at > datetime('now', ?)"
        params: list = [f"-{days} days"]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY created_at DESC"
        return self.execute(sql, tuple(params))

    def get_latest_drafts(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.execute("SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,))

    def delete_draft(self, draft_id: str) -> bool:
        with self.connection() as conn:
            # Delete related analytics first
            conn.execute("DELETE FROM post_analytics WHERE draft_id = ?", (draft_id,))
            cur = conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            return cur.rowcount > 0

    # --- Analytics ---

    def insert_analytics(self, data: dict) -> int:
        return self.insert("post_analytics", data)

    def get_analytics(self, draft_id: str) -> sqlite3.Row | None:
        return self.execute_one("SELECT * FROM post_analytics WHERE draft_id = ?", (draft_id,))

    def update_analytics(self, draft_id: str, data: dict) -> int:
        return self.update("post_analytics", data, "draft_id = ?", (draft_id,))

    # --- Run Log ---

    def start_run(self, run_type: str) -> int:
        return self.insert("run_log", {"run_type": run_type})

    def complete_run(self, run_id: int, status: str, summary: dict | None = None, error: str | None = None) -> None:
        data = {
            "completed_at": "CURRENT_TIMESTAMP",
            "status": status,
        }
        if summary:
            data["summary"] = json.dumps(summary)
        if error:
            data["error"] = error
        # Use raw SQL for CURRENT_TIMESTAMP
        with self.connection() as conn:
            conn.execute(
                "UPDATE run_log SET completed_at = CURRENT_TIMESTAMP, status = ?, summary = ?, error = ? WHERE id = ?",
                (status, json.dumps(summary) if summary else None, error, run_id),
            )

    def get_recent_runs(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.execute("SELECT * FROM run_log ORDER BY started_at DESC LIMIT ?", (limit,))

    # --- Config Snapshots ---

    def save_config_snapshot(self, config_hash: str, config_yaml: str) -> int:
        return self.insert("config_snapshots", {"config_hash": config_hash, "config_yaml": config_yaml})

    # --- Expiration ---

    def expire_old_drafts(self, days: int = 7) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE drafts SET status = 'expired' WHERE status = 'pending' AND created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            return cur.rowcount

    # --- Stats ---

    def get_draft_counts_by_status(self) -> dict[str, int]:
        rows = self.execute("SELECT status, COUNT(*) as cnt FROM drafts GROUP BY status")
        return {row["status"]: row["cnt"] for row in rows}

    def get_todays_drafts(self, platform: str | None = None) -> list[sqlite3.Row]:
        """Get drafts generated today for a specific platform."""
        sql = "SELECT * FROM drafts WHERE date(created_at) = date('now')"
        params: list = []
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY created_at DESC"
        return self.execute(sql, tuple(params))

    def get_recent_rejection_notes(self, days: int = 10, platform: str | None = None) -> list[str]:
        """Get recent rejection notes for feedback to LLM."""
        sql = (
            "SELECT reviewer_notes FROM drafts "
            "WHERE status = 'rejected' "
            "AND reviewer_notes IS NOT NULL AND reviewer_notes != '' "
            "AND reviewed_at > datetime('now', ?)"
        )
        params: list = [f"-{days} days"]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY reviewed_at DESC LIMIT 10"
        rows = self.execute(sql, tuple(params))
        return [row["reviewer_notes"] for row in rows]

    def get_recent_approval_notes(self, days: int = 10, platform: str | None = None) -> list[str]:
        """Get recent approval notes (positive signals) for feedback to LLM."""
        sql = (
            "SELECT reviewer_notes FROM drafts "
            "WHERE status IN ('approved', 'posted') "
            "AND reviewer_notes IS NOT NULL AND reviewer_notes != '' "
            "AND reviewed_at > datetime('now', ?)"
        )
        params: list = [f"-{days} days"]
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        sql += " ORDER BY reviewed_at DESC LIMIT 10"
        rows = self.execute(sql, tuple(params))
        return [row["reviewer_notes"] for row in rows]

    def get_posts_count_today(self, platform: str) -> int:
        row = self.execute_one(
            "SELECT COUNT(*) as cnt FROM drafts WHERE platform = ? AND status = 'posted' AND date(posted_at) = date('now')",
            (platform,),
        )
        return row["cnt"] if row else 0
