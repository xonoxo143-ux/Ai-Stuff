from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping


def _semantic_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[A-Za-z0-9]+",
            str(value).casefold(),
        )
        if len(token) > 2
    }


def _semantic_overlap_score(
    query: str,
    key: str,
    value: Any,
) -> float:
    query_tokens = _semantic_tokens(query)
    if not query_tokens:
        return 0.0
    document_tokens = _semantic_tokens(
        f"{key} {value}"
    )
    return (
        len(query_tokens & document_tokens)
        / len(query_tokens)
    )


@dataclass
class MemoryConfig:
    max_active_items: int = 32
    max_recent_episodes: int = 16


@dataclass
class AgentMemory:
    """Keeps current state, events, world knowledge, and capability history distinct."""

    config: MemoryConfig = field(default_factory=MemoryConfig)
    active: dict[str, Any] = field(default_factory=dict)
    episodes: list[dict[str, Any]] = field(default_factory=list)
    semantic: dict[str, Any] = field(default_factory=dict)
    capability_stats: dict[str, dict[str, float]] = field(default_factory=dict)

    def last_turn_id(self) -> int:
        turns = [
            int(event.get("turn", 0) or 0)
            for event in self.episodes
        ]
        return max(turns, default=0)

    def recent_episodes(self) -> list[Mapping[str, Any]]:
        n = self.config.max_recent_episodes
        return list(self.episodes[-n:])

    def append_episode(self, event: Mapping[str, Any]) -> None:
        self.episodes.append(dict(event))

    def update_active(self, updates: Mapping[str, Any]) -> None:
        for key, value in updates.items():
            self.active[str(key)] = value
        while len(self.active) > self.config.max_active_items:
            oldest = next(iter(self.active))
            del self.active[oldest]

    def update_semantic(self, updates: Mapping[str, Any]) -> None:
        for key, value in updates.items():
            self.semantic[str(key)] = value

    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        rows = []
        for key, value in self.semantic.items():
            score = _semantic_overlap_score(
                query,
                key,
                value,
            )
            if score <= 0.0:
                continue
            rows.append(
                {
                    "key": key,
                    "value": value,
                    "score": score,
                }
            )
        rows.sort(
            key=lambda row: (
                -float(row["score"]),
                str(row["key"]),
            )
        )
        return rows[: max(0, int(limit))]

    def record_capability(self, name: str, *, success: bool, cost: float) -> None:
        row = self.capability_stats.setdefault(
            name,
            {"calls": 0.0, "successes": 0.0, "total_cost": 0.0},
        )
        row["calls"] += 1.0
        row["successes"] += 1.0 if success else 0.0
        row["total_cost"] += float(cost)
