from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram.types import User as TgUser

from gdz_bot.config import Config
from gdz_bot.constants import ADMIN_FOREVER_DAYS, ADMIN_PAGE_SIZE
from gdz_bot.defaults import DEFAULT_SETTINGS


class Database:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._conn: aiosqlite.Connection | None = None
        self._tz = ZoneInfo(config.timezone)
        self._settings_cache: dict[str, str] | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def connect(self) -> None:
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.config.sqlite_path)
        self._conn.row_factory = aiosqlite.Row

        pragmas = [
            "PRAGMA foreign_keys = ON",
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL",
            "PRAGMA temp_store = MEMORY",
            "PRAGMA busy_timeout = 5000",
        ]
        for pragma in pragmas:
            await self._conn.execute(pragma)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def init_schema(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                language_code TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                subscription_expires_at TEXT,
                total_requests INTEGER NOT NULL DEFAULT 0,
                daily_requests INTEGER NOT NULL DEFAULT 0,
                daily_requests_date TEXT,
                selected_class INTEGER,
                selected_subject TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_last_seen
            ON users (last_seen_at DESC);

            CREATE INDEX IF NOT EXISTS idx_users_subscription_expires
            ON users (subscription_expires_at);

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                class_number INTEGER NOT NULL,
                subject_key TEXT NOT NULL,
                task_text TEXT NOT NULL,
                task_file_id TEXT,
                task_file_type TEXT,
                short_description TEXT,
                solution_text TEXT,
                answer_text TEXT,
                confidence_note TEXT,
                quality_mode TEXT NOT NULL,
                reasoning_effort TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                status TEXT NOT NULL,
                error_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_requests_user_created
            ON requests (user_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_requests_created
            ON requests (created_at DESC);

            CREATE TABLE IF NOT EXISTS subscription_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                processed_at TEXT,
                processed_by INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_subscription_requests_status
            ON subscription_requests (status, created_at DESC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_subscription_requests_one_pending
            ON subscription_requests (user_id)
            WHERE status = 'pending';

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        await self.conn.commit()
        await self.ensure_default_settings()

    def _now(self) -> datetime:
        return datetime.now(self._tz)

    def _now_iso(self) -> str:
        return self._now().isoformat(timespec="seconds")

    def _today(self) -> str:
        return self._now().date().isoformat()

    def _admin_forever_iso(self) -> str:
        return (self._now() + timedelta(days=ADMIN_FOREVER_DAYS)).isoformat(timespec="seconds")

    async def ensure_default_settings(self) -> None:
        now = self._now_iso()
        await self.conn.executemany(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            [(key, value, now) for key, value in DEFAULT_SETTINGS.items()],
        )
        await self.conn.commit()
        self._settings_cache = None

    async def get_settings_map(self, *, refresh: bool = False) -> dict[str, str]:
        if self._settings_cache is not None and not refresh:
            return dict(self._settings_cache)

        cursor = await self.conn.execute("SELECT key, value FROM settings ORDER BY key")
        rows = await cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}
        self._settings_cache = settings
        return dict(settings)

    async def update_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, self._now_iso()),
        )
        await self.conn.commit()
        if self._settings_cache is None:
            return
        self._settings_cache[key] = value

    async def upsert_user(self, user: TgUser) -> dict[str, Any]:
        now = self._now_iso()
        today = self._today()
        full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip()
        full_name = full_name or user.username or str(user.id)
        is_admin = 1 if user.id in self.config.admin_ids else 0
        admin_expiry = self._admin_forever_iso() if is_admin else None

        await self.conn.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                full_name,
                language_code,
                is_admin,
                subscription_expires_at,
                daily_requests_date,
                created_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                language_code = excluded.language_code,
                is_admin = excluded.is_admin,
                last_seen_at = excluded.last_seen_at,
                daily_requests = CASE
                    WHEN users.daily_requests_date IS NULL OR users.daily_requests_date <> excluded.daily_requests_date
                        THEN 0
                    ELSE users.daily_requests
                END,
                daily_requests_date = CASE
                    WHEN users.daily_requests_date IS NULL OR users.daily_requests_date <> excluded.daily_requests_date
                        THEN excluded.daily_requests_date
                    ELSE users.daily_requests_date
                END,
                subscription_expires_at = CASE
                    WHEN excluded.is_admin = 1
                        AND (
                            users.subscription_expires_at IS NULL
                            OR users.subscription_expires_at < excluded.subscription_expires_at
                        )
                        THEN excluded.subscription_expires_at
                    ELSE users.subscription_expires_at
                END
            """,
            (
                user.id,
                user.username,
                full_name,
                user.language_code,
                is_admin,
                admin_expiry,
                today,
                now,
                now,
            ),
        )
        await self.conn.commit()

        current = await self.get_user(user.id)
        if current is None:
            raise RuntimeError("Failed to upsert user")
        return current

    async def _normalize_user_daily_usage(
        self,
        user: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if user is None:
            return None

        today = self._today()
        if user["daily_requests_date"] == today:
            return user

        await self.conn.execute(
            """
            UPDATE users
            SET daily_requests = 0,
                daily_requests_date = ?
            WHERE user_id = ?
            """,
            (today, user["user_id"]),
        )
        await self.conn.commit()
        user["daily_requests"] = 0
        user["daily_requests_date"] = today
        return user

    async def get_user(
        self,
        user_id: int,
        *,
        refresh_daily_usage: bool = False,
    ) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        user = dict(row) if row else None
        if refresh_daily_usage:
            return await self._normalize_user_daily_usage(user)
        return user

    async def save_grade(self, user_id: int, grade: int) -> None:
        await self.conn.execute(
            "UPDATE users SET selected_class = ?, selected_subject = NULL WHERE user_id = ?",
            (grade, user_id),
        )
        await self.conn.commit()

    async def save_subject(self, user_id: int, subject_key: str) -> None:
        await self.conn.execute(
            "UPDATE users SET selected_subject = ? WHERE user_id = ?",
            (subject_key, user_id),
        )
        await self.conn.commit()

    async def get_remaining_quota(self, user_id: int, daily_limit: int) -> tuple[int, int]:
        user = await self.get_user(user_id, refresh_daily_usage=True)
        if user is None:
            return daily_limit, 0
        used = int(user["daily_requests"])
        return max(daily_limit - used, 0), used

    async def reserve_quota(self, user_id: int, daily_limit: int) -> tuple[bool, int, int]:
        user = await self.get_user(user_id, refresh_daily_usage=True)
        if user is None:
            return False, 0, daily_limit

        used = int(user["daily_requests"])
        if used >= daily_limit:
            return False, used, 0

        cursor = await self.conn.execute(
            """
            UPDATE users
            SET daily_requests = daily_requests + 1,
                total_requests = total_requests + 1
            WHERE user_id = ? AND daily_requests < ?
            """,
            (user_id, daily_limit),
        )
        await self.conn.commit()

        if cursor.rowcount == 0:
            refreshed = await self.get_user(user_id, refresh_daily_usage=True)
            used = int(refreshed["daily_requests"]) if refreshed else daily_limit
            return False, used, max(daily_limit - used, 0)

        used += 1
        return True, used, max(daily_limit - used, 0)

    async def release_quota(self, user_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE users
            SET daily_requests = CASE WHEN daily_requests > 0 THEN daily_requests - 1 ELSE 0 END,
                total_requests = CASE WHEN total_requests > 0 THEN total_requests - 1 ELSE 0 END
            WHERE user_id = ?
            """,
            (user_id,),
        )
        await self.conn.commit()

    async def create_request(
        self,
        user_id: int,
        class_number: int,
        subject_key: str,
        task_text: str,
        quality_mode: str,
        reasoning_effort: str,
        model_name: str,
        task_file_id: str | None = None,
        task_file_type: str | None = None,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO requests (
                user_id, class_number, subject_key, task_text, task_file_id, task_file_type,
                quality_mode, reasoning_effort, model_name, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?)
            """,
            (
                user_id,
                class_number,
                subject_key,
                task_text,
                task_file_id,
                task_file_type,
                quality_mode,
                reasoning_effort,
                model_name,
                self._now_iso(),
            ),
        )
        await self.conn.commit()
        return int(cursor.lastrowid)

    async def complete_request(
        self,
        request_id: int,
        summary: str,
        solution: str,
        answer: str,
        confidence_note: str,
        usage: dict[str, int | None],
    ) -> None:
        await self.conn.execute(
            """
            UPDATE requests
            SET short_description = ?,
                solution_text = ?,
                answer_text = ?,
                confidence_note = ?,
                prompt_tokens = ?,
                completion_tokens = ?,
                total_tokens = ?,
                status = 'completed'
            WHERE id = ?
            """,
            (
                summary,
                solution,
                answer,
                confidence_note,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
                request_id,
            ),
        )
        await self.conn.commit()

    async def fail_request(self, request_id: int, error_text: str) -> None:
        await self.conn.execute(
            "UPDATE requests SET status = 'failed', error_text = ? WHERE id = ?",
            (error_text, request_id),
        )
        await self.conn.commit()

    async def list_recent_requests(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT *
            FROM requests
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_request(self, request_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def count_users(self) -> int:
        cursor = await self.conn.execute("SELECT COUNT(*) AS total FROM users")
        row = await cursor.fetchone()
        return int(row["total"])

    async def list_users(self, page: int = 1, page_size: int = ADMIN_PAGE_SIZE) -> list[dict[str, Any]]:
        offset = max(page - 1, 0) * page_size
        cursor = await self.conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY is_admin DESC, is_blocked ASC, last_seen_at DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def extend_subscription(self, user_id: int, days: int) -> None:
        user = await self.get_user(user_id)
        if user is None:
            return
        now = self._now()
        expiry_raw = user["subscription_expires_at"]
        expiry = datetime.fromisoformat(expiry_raw) if expiry_raw else now
        base = expiry if expiry > now else now
        new_expiry = base + timedelta(days=days)
        await self.conn.execute(
            "UPDATE users SET subscription_expires_at = ? WHERE user_id = ?",
            (new_expiry.isoformat(timespec="seconds"), user_id),
        )
        await self.conn.commit()

    async def clear_subscription(self, user_id: int) -> None:
        await self.conn.execute(
            "UPDATE users SET subscription_expires_at = NULL WHERE user_id = ?",
            (user_id,),
        )
        await self.conn.commit()

    async def set_blocked(self, user_id: int, blocked: bool) -> None:
        await self.conn.execute(
            "UPDATE users SET is_blocked = ? WHERE user_id = ?",
            (1 if blocked else 0, user_id),
        )
        await self.conn.commit()

    async def reset_user_daily_limit(self, user_id: int) -> None:
        await self.conn.execute(
            "UPDATE users SET daily_requests = 0, daily_requests_date = ? WHERE user_id = ?",
            (self._today(), user_id),
        )
        await self.conn.commit()

    async def create_subscription_request(self, user_id: int, note: str | None = None) -> int | None:
        try:
            cursor = await self.conn.execute(
                """
                INSERT INTO subscription_requests (user_id, note, status, created_at)
                VALUES (?, ?, 'pending', ?)
                """,
                (user_id, note, self._now_iso()),
            )
        except aiosqlite.IntegrityError:
            return None

        await self.conn.commit()
        return int(cursor.lastrowid)

    async def has_pending_subscription_request(self, user_id: int) -> bool:
        cursor = await self.conn.execute(
            """
            SELECT 1
            FROM subscription_requests
            WHERE user_id = ? AND status = 'pending'
            LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return row is not None

    async def list_subscription_requests(self, status: str = "pending", limit: int = 20) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            """
            SELECT sr.*, u.username, u.full_name
            FROM subscription_requests sr
            JOIN users u ON u.user_id = sr.user_id
            WHERE sr.status = ?
            ORDER BY sr.created_at DESC
            LIMIT ?
            """,
            (status, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def mark_subscription_request(
        self,
        request_id: int,
        status: str,
        processed_by: int,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE subscription_requests
            SET status = ?, processed_at = ?, processed_by = ?
            WHERE id = ?
            """,
            (status, self._now_iso(), processed_by, request_id),
        )
        await self.conn.commit()

    async def get_subscription_request(self, request_id: int) -> dict[str, Any] | None:
        cursor = await self.conn.execute(
            """
            SELECT sr.*, u.username, u.full_name
            FROM subscription_requests sr
            JOIN users u ON u.user_id = sr.user_id
            WHERE sr.id = ?
            """,
            (request_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_stats(self) -> dict[str, int]:
        today = self._today()
        now = self._now_iso()

        cursor = await self.conn.execute("SELECT COUNT(*) AS total FROM users")
        users_row = await cursor.fetchone()

        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE subscription_expires_at IS NOT NULL AND subscription_expires_at > ?
            """,
            (now,),
        )
        premium_row = await cursor.fetchone()

        cursor = await self.conn.execute(
            "SELECT COUNT(*) AS total FROM users WHERE substr(last_seen_at, 1, 10) = ?",
            (today,),
        )
        active_today_row = await cursor.fetchone()

        cursor = await self.conn.execute("SELECT COUNT(*) AS total FROM requests")
        requests_row = await cursor.fetchone()

        cursor = await self.conn.execute(
            "SELECT COUNT(*) AS total FROM requests WHERE substr(created_at, 1, 10) = ?",
            (today,),
        )
        today_requests_row = await cursor.fetchone()

        cursor = await self.conn.execute(
            "SELECT COUNT(*) AS total FROM subscription_requests WHERE status = 'pending'"
        )
        pending_subs_row = await cursor.fetchone()

        return {
            "users_total": int(users_row["total"]),
            "premium_total": int(premium_row["total"]),
            "active_today": int(active_today_row["total"]),
            "requests_total": int(requests_row["total"]),
            "requests_today": int(today_requests_row["total"]),
            "pending_subscriptions": int(pending_subs_row["total"]),
        }
