from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .vm_ledger import atom


@dataclass(frozen=True, slots=True)
class RelationSpec:
    relation_id: int
    name: str


class RelationRegistry:
    """Versionable semantic state-dimension vocabulary.

    The historical name is kept for compatibility. Entries such as `owner`,
    `location`, `temperature`, or `powered` are state dimensions/fields; they are not
    VM opcodes and do not all need to be relations in the linguistic sense.

    IDs are compiler-facing handles. The kernel can execute any normalized dimension;
    untrusted compilers may emit only IDs present in the registry they were trained
    against.
    """

    def __init__(self, names=()):
        self._by_id: dict[int, RelationSpec] = {}
        self._by_name: dict[str, RelationSpec] = {}
        for name in names:
            self.register(name)

    def register(self, name: str, *, relation_id: int | None = None) -> RelationSpec:
        normalized = atom(name)
        if normalized in self._by_name:
            existing = self._by_name[normalized]
            if relation_id is not None and relation_id != existing.relation_id:
                raise ValueError(
                    f"dimension {normalized!r} already has id {existing.relation_id}"
                )
            return existing
        if relation_id is None:
            relation_id = 0
            while relation_id in self._by_id:
                relation_id += 1
        if isinstance(relation_id, bool) or not isinstance(relation_id, int) or relation_id < 0:
            raise ValueError("dimension id must be a non-negative integer")
        if relation_id in self._by_id:
            raise ValueError(f"dimension id {relation_id} is already registered")
        spec = RelationSpec(relation_id, normalized)
        self._by_id[relation_id] = spec
        self._by_name[normalized] = spec
        return spec

    def resolve_id(self, relation_id: int) -> RelationSpec:
        try:
            return self._by_id[relation_id]
        except KeyError as exc:
            raise KeyError(f"unknown semantic dimension id {relation_id}") from exc

    def resolve_name(self, name: str) -> RelationSpec:
        normalized = atom(name)
        try:
            return self._by_name[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown semantic dimension {normalized!r}") from exc

    def __contains__(self, value) -> bool:
        if isinstance(value, int) and not isinstance(value, bool):
            return value in self._by_id
        try:
            return atom(value) in self._by_name
        except Exception:
            return False

    def specs(self) -> tuple[RelationSpec, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def names(self) -> tuple[str, ...]:
        return tuple(spec.name for spec in self.specs())

    def signature(self) -> str:
        payload = json.dumps(
            [(spec.relation_id, spec.name) for spec in self.specs()],
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


DEFAULT_RELATION_REGISTRY = RelationRegistry(("owner", "possessor", "location"))

# Preferred algebra-facing vocabulary. Old names remain stable for experiment code.
DimensionSpec = RelationSpec
DimensionRegistry = RelationRegistry
DEFAULT_DIMENSION_REGISTRY = DEFAULT_RELATION_REGISTRY
