from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .memory import (
    MemoryConfig,
    _semantic_overlap_score,
    _semantic_tokens,
)


class SQLiteAgentMemory:
    """Small durable memory backend using only Python's stdlib SQLite."""

    def __init__(
        self,
        path: str | Path,
        config: MemoryConfig | None = None,
    ) -> None:
        self.path = str(path)
        self.config = config or MemoryConfig()
        self._db = sqlite3.connect(self.path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS active_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                seq INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER,
                event_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS semantic_memory (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capability_stats (
                name TEXT PRIMARY KEY,
                calls REAL NOT NULL,
                successes REAL NOT NULL,
                total_cost REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                int_value INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS semantic_fts
            USING fts5(
                key,
                text,
                tokenize='unicode61'
            );
            """
        )
        self._db.commit()
        self._ensure_semantic_fts()

    def _ensure_semantic_fts(self) -> None:
        semantic_count = int(
            self._db.execute(
                "SELECT COUNT(*) FROM semantic_memory"
            ).fetchone()[0]
        )
        indexed_count = int(
            self._db.execute(
                "SELECT COUNT(*) FROM semantic_fts"
            ).fetchone()[0]
        )
        if semantic_count == indexed_count:
            return
        self._db.execute(
            "DELETE FROM semantic_fts"
        )
        rows = self._db.execute(
            (
                "SELECT key, value_json "
                "FROM semantic_memory"
            )
        ).fetchall()
        self._db.executemany(
            (
                "INSERT INTO semantic_fts"
                "(key, text) VALUES(?, ?)"
            ),
            rows,
        )
        self._db.commit()

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _load(value: str) -> Any:
        return json.loads(value)

    def _next_seq(self, key: str) -> int:
        row = self._db.execute(
            (
                "SELECT int_value FROM meta "
                "WHERE key = ?"
            ),
            (key,),
        ).fetchone()
        value = (
            int(row[0]) if row else 0
        ) + 1
        self._db.execute(
            """
            INSERT INTO meta(key, int_value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET
                int_value = excluded.int_value
            """,
            (key, value),
        )
        return value

    @property
    def active(self) -> dict[str, Any]:
        rows = self._db.execute(
            (
                "SELECT key, value_json "
                "FROM active_state ORDER BY seq"
            )
        ).fetchall()
        return {
            key: self._load(value)
            for key, value in rows
        }

    @property
    def episodes(
        self,
    ) -> list[dict[str, Any]]:
        rows = self._db.execute(
            (
                "SELECT event_json FROM episodes "
                "ORDER BY id"
            )
        ).fetchall()
        return [
            self._load(row[0])
            for row in rows
        ]

    @property
    def semantic(self) -> dict[str, Any]:
        rows = self._db.execute(
            (
                "SELECT key, value_json "
                "FROM semantic_memory "
                "ORDER BY key"
            )
        ).fetchall()
        return {
            key: self._load(value)
            for key, value in rows
        }

    @property
    def capability_stats(
        self,
    ) -> dict[str, dict[str, float]]:
        rows = self._db.execute(
            """
            SELECT
                name,
                calls,
                successes,
                total_cost
            FROM capability_stats
            ORDER BY name
            """
        ).fetchall()
        return {
            name: {
                "calls": float(calls),
                "successes":
                    float(successes),
                "total_cost":
                    float(total_cost),
            }
            for (
                name,
                calls,
                successes,
                total_cost,
            ) in rows
        }

    def last_turn_id(self) -> int:
        row = self._db.execute(
            (
                "SELECT COALESCE(MAX(turn), 0) "
                "FROM episodes"
            )
        ).fetchone()
        return int(row[0] or 0)

    def recent_episodes(
        self,
    ) -> list[Mapping[str, Any]]:
        rows = self._db.execute(
            """
            SELECT event_json
            FROM episodes
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                self.config.max_recent_episodes,
            ),
        ).fetchall()
        return [
            self._load(row[0])
            for row in reversed(rows)
        ]

    def append_episode(
        self,
        event: Mapping[str, Any],
    ) -> None:
        payload = dict(event)
        turn = payload.get("turn")
        self._db.execute(
            (
                "INSERT INTO episodes"
                "(turn, event_json) "
                "VALUES(?, ?)"
            ),
            (
                (
                    int(turn)
                    if turn is not None
                    else None
                ),
                self._dump(payload),
            ),
        )
        self._db.commit()

    def update_active(
        self,
        updates: Mapping[str, Any],
    ) -> None:
        for key, value in updates.items():
            seq = self._next_seq(
                "active_seq"
            )
            self._db.execute(
                """
                INSERT INTO active_state(
                    key,
                    value_json,
                    seq
                )
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json =
                        excluded.value_json,
                    seq = excluded.seq
                """,
                (
                    str(key),
                    self._dump(value),
                    seq,
                ),
            )

        count = self._db.execute(
            "SELECT COUNT(*) FROM active_state"
        ).fetchone()[0]
        excess = (
            int(count)
            - self.config.max_active_items
        )
        if excess > 0:
            self._db.execute(
                """
                DELETE FROM active_state
                WHERE key IN (
                    SELECT key
                    FROM active_state
                    ORDER BY seq ASC
                    LIMIT ?
                )
                """,
                (excess,),
            )
        self._db.commit()

    def update_semantic(
        self,
        updates: Mapping[str, Any],
    ) -> None:
        for key, value in updates.items():
            key_text = str(key)
            value_json = self._dump(value)
            self._db.execute(
                """
                INSERT INTO semantic_memory(
                    key,
                    value_json
                )
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json =
                        excluded.value_json
                """,
                (
                    key_text,
                    value_json,
                ),
            )
            self._db.execute(
                (
                    "DELETE FROM semantic_fts "
                    "WHERE key = ?"
                ),
                (key_text,),
            )
            self._db.execute(
                (
                    "INSERT INTO semantic_fts"
                    "(key, text) VALUES(?, ?)"
                ),
                (
                    key_text,
                    value_json,
                ),
            )
        self._db.commit()

    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        tokens = sorted(
            _semantic_tokens(query)
        )
        if not tokens or limit <= 0:
            return []
        expression = " OR ".join(
            f'"{token}"'
            for token in tokens
        )
        candidate_limit = max(
            int(limit) * 4,
            int(limit),
        )
        rows = self._db.execute(
            """
            SELECT key
            FROM semantic_fts
            WHERE semantic_fts MATCH ?
            ORDER BY bm25(semantic_fts)
            LIMIT ?
            """,
            (
                expression,
                candidate_limit,
            ),
        ).fetchall()

        results = []
        for (key,) in rows:
            stored = self._db.execute(
                (
                    "SELECT value_json "
                    "FROM semantic_memory "
                    "WHERE key = ?"
                ),
                (key,),
            ).fetchone()
            if stored is None:
                continue
            value = self._load(stored[0])
            score = _semantic_overlap_score(
                query,
                str(key),
                value,
            )
            if score <= 0.0:
                continue
            results.append(
                {
                    "key": str(key),
                    "value": value,
                    "score": score,
                }
            )

        results.sort(
            key=lambda row: (
                -float(row["score"]),
                str(row["key"]),
            )
        )
        return results[: int(limit)]

    def record_capability(
        self,
        name: str,
        *,
        success: bool,
        cost: float,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO capability_stats(
                name,
                calls,
                successes,
                total_cost
            )
            VALUES(?, 1, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                calls = calls + 1,
                successes =
                    successes
                    + excluded.successes,
                total_cost =
                    total_cost
                    + excluded.total_cost
            """,
            (
                str(name),
                (
                    1.0
                    if success
                    else 0.0
                ),
                float(cost),
            ),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def __enter__(
        self,
    ) -> "SQLiteAgentMemory":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:
        self.close()
