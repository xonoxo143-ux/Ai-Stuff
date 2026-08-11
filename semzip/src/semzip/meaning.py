from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, TypeAlias, Union

Scalar: TypeAlias = str | int | float | bool
MeaningSequence: TypeAlias = tuple
MeaningValue: TypeAlias = Union[Scalar, "Meaning", MeaningSequence]


@dataclass(frozen=True, slots=True)
class Meaning:
    """Recursive, canonical semantic expression.

    Role values may be atoms, numbers/booleans, nested Meaning objects, or
    canonical tuples of those values. Tuples let the IR preserve sets of
    alternatives/members without inventing numbered role names.
    """

    operator: str
    roles: tuple[tuple[str, MeaningValue], ...]

    @classmethod
    def build(
        cls,
        operator: str,
        roles: Mapping[str, MeaningValue] | None = None,
    ) -> "Meaning":
        clean = [
            (_canon_atom(role), _canon_value(value))
            for role, value in (roles or {}).items()
        ]
        return cls(
            _canon_atom(operator),
            tuple(sorted(clean, key=lambda item: item[0])),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Meaning":
        operator = data.get("operator")
        roles = data.get("roles")
        if not isinstance(operator, str) or not isinstance(roles, Mapping):
            raise ValueError(
                "meaning dict requires string 'operator' and mapping 'roles'"
            )
        decoded: dict[str, MeaningValue] = {}
        for role, value in roles.items():
            if not isinstance(role, str):
                raise ValueError("semantic role names must be strings")
            decoded[role] = _decode_value(value)
        return cls.build(operator, decoded)

    @classmethod
    def from_json(cls, text: str) -> "Meaning":
        data = json.loads(text)
        if not isinstance(data, Mapping):
            raise ValueError("serialized meaning must be a JSON object")
        return cls.from_dict(data)

    def get(self, role: str) -> MeaningValue | None:
        return dict(self.roles).get(_canon_atom(role))

    def atom(self, role: str) -> str:
        value = self.get(role)
        if not isinstance(value, str):
            raise ValueError(
                f"{self.operator}.{_canon_atom(role)} must be an atom"
            )
        return value

    def optional_atom(self, role: str) -> str | None:
        value = self.get(role)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"{self.operator}.{_canon_atom(role)} must be an atom"
            )
        return value

    def expression(self, role: str) -> "Meaning":
        value = self.get(role)
        if not isinstance(value, Meaning):
            raise ValueError(
                f"{self.operator}.{_canon_atom(role)} must be a Meaning"
            )
        return value

    def expressions(self, role: str) -> tuple["Meaning", ...]:
        value = self.get(role)
        if not isinstance(value, tuple) or not all(
            isinstance(item, Meaning) for item in value
        ):
            raise ValueError(
                f"{self.operator}.{_canon_atom(role)} must be a tuple of Meanings"
            )
        return value

    def to_dict(self) -> dict[str, object]:
        return {
            "operator": self.operator,
            "roles": {
                role: _serialize_value(value)
                for role, value in self.roles
            },
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


def _canon_value(value: MeaningValue) -> MeaningValue:
    if isinstance(value, Meaning):
        return value
    if isinstance(value, tuple):
        return tuple(_canon_value(item) for item in value)
    if isinstance(value, str):
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("semantic values cannot be empty")
        return value.casefold().replace(" ", "_")
    if isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"unsupported semantic value: {type(value).__name__}")


def _serialize_value(value: MeaningValue) -> object:
    if isinstance(value, Meaning):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


def _decode_value(value: object) -> MeaningValue:
    if isinstance(value, Mapping):
        return Meaning.from_dict(value)
    if isinstance(value, list):
        return tuple(_decode_value(item) for item in value)
    if isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError(
        f"unsupported serialized semantic value: {type(value).__name__}"
    )
