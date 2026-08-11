from __future__ import annotations

from dataclasses import dataclass

from .meaning import Meaning
from .schema import validate_meaning
from .world import WorldModel


@dataclass(frozen=True, slots=True)
class QueryAnswer:
    value: str | bool | None
    known: bool

    @classmethod
    def of(cls, value: str | bool | None) -> "QueryAnswer":
        return cls(value=value, known=value is not None)


class WorldQueryEngine:
    """Read-only semantic query layer over WorldModel."""

    def __init__(self, world: WorldModel) -> None:
        self.world = world

    def answer(self, query: Meaning) -> QueryAnswer:
        validate_meaning(query)
        op = query.operator

        if op == "QUERY_VALUE":
            return QueryAnswer.of(
                self.world.fact(query.atom("SUBJECT"), query.atom("DIMENSION"))
            )

        if op == "QUERY_PREVIOUS_VALUE":
            return QueryAnswer.of(
                self.world.previous(query.atom("SUBJECT"), query.atom("DIMENSION"))
            )

        if op == "QUERY_BELIEF":
            return QueryAnswer.of(
                self.world.latest_belief(
                    query.atom("HOLDER"),
                    query.atom("SUBJECT"),
                    query.atom("DIMENSION"),
                )
            )

        if op == "QUERY_BELIEF_TRUE":
            return QueryAnswer.of(
                self.world.belief_is_true(
                    query.atom("HOLDER"),
                    query.atom("SUBJECT"),
                    query.atom("DIMENSION"),
                )
            )

        if op == "QUERY_KNOWS_VALUE":
            return QueryAnswer.of(
                self.world.knows_value(
                    query.atom("HOLDER"),
                    query.atom("SUBJECT"),
                    query.atom("DIMENSION"),
                )
            )

        if op == "QUERY_IS_A":
            return QueryAnswer.of(
                self.world.entity_is_a(
                    query.atom("SUBJECT"),
                    query.atom("ANCESTOR"),
                )
            )

        raise ValueError(f"unsupported query operator {op!r}")
