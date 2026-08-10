from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SemanticGraph:
    """Small canonical semantic graph.

    `predicate` names the semantic event/state. Roles are stored as immutable sorted
    key/value pairs so equivalent graphs serialize identically regardless of parse
    order.
    """

    predicate: str
    roles: tuple[tuple[str, str], ...]
    polarity: bool = True

    @classmethod
    def build(
        cls,
        predicate: str,
        roles: Mapping[str, str],
        *,
        polarity: bool = True,
    ) -> "SemanticGraph":
        predicate = _canon_atom(predicate)
        clean_roles = tuple(
            sorted((_canon_atom(role), _canon_value(value)) for role, value in roles.items())
        )
        return cls(predicate=predicate, roles=clean_roles, polarity=bool(polarity))

    def role(self, name: str) -> str | None:
        target = _canon_atom(name)
        return dict(self.roles).get(target)

    def to_dict(self) -> dict[str, object]:
        return {
            "predicate": self.predicate,
            "polarity": self.polarity,
            "roles": {key: value for key, value in self.roles},
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def semantic_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _canon_atom(value: str) -> str:
    value = " ".join(value.strip().split())
    if not value:
        raise ValueError("semantic atoms cannot be empty")
    return value.upper().replace(" ", "_")


def _canon_value(value: str) -> str:
    value = " ".join(value.strip().split())
    if not value:
        raise ValueError("semantic values cannot be empty")
    return value.casefold()
