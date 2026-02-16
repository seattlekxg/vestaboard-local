"""SQLite database for scheduled messages and settings."""

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from .config import config


@dataclass
class ScheduledMessage:
    """A scheduled message."""
    id: Optional[int]
    name: str
    message_type: str  # "text", "weather", "stocks", "calendar", "news"
    content: Optional[str]  # For text messages
    cron_expression: str  # Cron schedule (e.g., "0 8 * * *" for 8am daily)
    enabled: bool = True
    last_run: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class MessageLog:
    """Log entry for sent messages."""
    id: Optional[int]
    message_type: str
    content: str
    sent_at: datetime
    success: bool


class Storage:
    """SQLite storage for Vestaboard automation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT,
                cron_expression TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                last_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS message_log (
                id INTEGER PRIMARY KEY,
                message_type TEXT NOT NULL,
                content TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_scheduled_enabled
                ON scheduled_messages(enabled);
            CREATE INDEX IF NOT EXISTS idx_log_sent
                ON message_log(sent_at);
        """)

        conn.commit()
        conn.close()

    # ========== Scheduled Messages ==========

    def save_scheduled_message(self, msg: ScheduledMessage) -> int:
        """Save or update a scheduled message."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if msg.id:
            cursor.execute("""
                UPDATE scheduled_messages
                SET name = ?, message_type = ?, content = ?,
                    cron_expression = ?, enabled = ?
                WHERE id = ?
            """, (msg.name, msg.message_type, msg.content,
                  msg.cron_expression, msg.enabled, msg.id))
            msg_id = msg.id
        else:
            cursor.execute("""
                INSERT INTO scheduled_messages
                    (name, message_type, content, cron_expression, enabled)
                VALUES (?, ?, ?, ?, ?)
            """, (msg.name, msg.message_type, msg.content,
                  msg.cron_expression, msg.enabled))
            msg_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return msg_id

    def get_scheduled_messages(self, enabled_only: bool = False) -> list[ScheduledMessage]:
        """Get all scheduled messages."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if enabled_only:
            cursor.execute(
                "SELECT * FROM scheduled_messages WHERE enabled = TRUE ORDER BY name"
            )
        else:
            cursor.execute("SELECT * FROM scheduled_messages ORDER BY name")

        messages = []
        for row in cursor.fetchall():
            messages.append(ScheduledMessage(
                id=row["id"],
                name=row["name"],
                message_type=row["message_type"],
                content=row["content"],
                cron_expression=row["cron_expression"],
                enabled=bool(row["enabled"]),
                last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            ))

        conn.close()
        return messages

    def get_scheduled_message(self, msg_id: int) -> Optional[ScheduledMessage]:
        """Get a scheduled message by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM scheduled_messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return ScheduledMessage(
            id=row["id"],
            name=row["name"],
            message_type=row["message_type"],
            content=row["content"],
            cron_expression=row["cron_expression"],
            enabled=bool(row["enabled"]),
            last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )

    def delete_scheduled_message(self, msg_id: int) -> bool:
        """Delete a scheduled message."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scheduled_messages WHERE id = ?", (msg_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def update_last_run(self, msg_id: int):
        """Update the last run time for a scheduled message."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scheduled_messages SET last_run = ? WHERE id = ?",
            (datetime.now().isoformat(), msg_id)
        )
        conn.commit()
        conn.close()

    # ========== Message Log ==========

    def log_message(self, message_type: str, content: str, success: bool):
        """Log a sent message."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO message_log (message_type, content, success)
            VALUES (?, ?, ?)
        """, (message_type, content, success))
        conn.commit()
        conn.close()

    def get_message_log(self, limit: int = 50) -> list[MessageLog]:
        """Get recent message log entries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM message_log ORDER BY sent_at DESC LIMIT ?",
            (limit,)
        )

        logs = []
        for row in cursor.fetchall():
            logs.append(MessageLog(
                id=row["id"],
                message_type=row["message_type"],
                content=row["content"],
                sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else datetime.now(),
                success=bool(row["success"])
            ))

        conn.close()
        return logs

    # ========== Settings ==========

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        """Set a setting value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
        conn.close()
