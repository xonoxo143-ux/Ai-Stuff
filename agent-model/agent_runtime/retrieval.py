from __future__ import annotations

import json
from typing import Any, Protocol

from .contracts import (
    CapabilityContext,
    CapabilityOffer,
    CapabilityResult,
    CapabilityRole,
    PublicMessage,
)


class SemanticSearchMemory(Protocol):
    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        ...


class SemanticRetrievalCapability:
    """Cheap replaceable lexical retrieval baseline."""

    name = "semantic-retrieval"
    role = CapabilityRole.CONTRIBUTOR
    contract_version = "0.1"

    def __init__(
        self,
        memory: SemanticSearchMemory,
        *,
        limit: int = 3,
        min_score: float = 0.25,
        estimated_cost: float = 0.02,
    ) -> None:
        self.memory = memory
        self.limit = int(limit)
        self.min_score = float(min_score)
        self.estimated_cost = float(
            estimated_cost
        )
        self._cached_turn: tuple[
            int,
            str,
            list[dict[str, Any]],
        ] | None = None

    def _search(
        self,
        context: CapabilityContext,
    ) -> list[dict[str, Any]]:
        key = (
            context.turn_id,
            context.user_text,
        )
        if (
            self._cached_turn is not None
            and self._cached_turn[:2] == key
        ):
            return self._cached_turn[2]
        rows = self.memory.search_semantic(
            context.user_text,
            limit=self.limit,
        )
        self._cached_turn = (
            context.turn_id,
            context.user_text,
            rows,
        )
        return rows

    def offer(
        self,
        context: CapabilityContext,
    ) -> CapabilityOffer | None:
        rows = self._search(context)
        if not rows:
            return None
        top_score = float(
            rows[0]["score"]
        )
        if top_score < self.min_score:
            return None
        return CapabilityOffer(
            capability=self.name,
            relevance=min(
                1.0,
                0.25 + top_score,
            ),
            estimated_cost=self.estimated_cost,
            confidence=top_score,
            tags=("memory", "retrieval"),
        )

    @staticmethod
    def _display(value: Any) -> str:
        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ) or value is None:
            return str(value)
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )

    def run(
        self,
        context: CapabilityContext,
    ) -> CapabilityResult:
        rows = self._search(context)
        messages = tuple(
            PublicMessage(
                kind="fact",
                content=(
                    f"{row['key']}="
                    f"{self._display(row['value'])}"
                ),
                source=self.name,
                confidence=float(
                    row["score"]
                ),
                metadata={
                    "memory_key":
                        str(row["key"]),
                    "retrieval_score":
                        float(row["score"]),
                },
            )
            for row in rows
            if float(row["score"])
            >= self.min_score
        )
        return CapabilityResult(
            messages=messages,
            measured_cost=
                self.estimated_cost,
        )
