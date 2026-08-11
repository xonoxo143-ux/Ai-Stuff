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
    """Versionable semantic-library relation vocabulary.

    Relation IDs are compiler-facing handles, not VM opcodes. The Semantic VM
    kernel can execute any normalized relation dimension; untrusted compilers may
    only emit IDs present in the registry they were trained against.
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
                    f"relation {normalized!r} already has id {existing.relation_id}"
                )
            return existing
        if relation_id is None:
            relation_id = 0
            while relation_id in self._by_id:
                relation_id += 1
        if isinstance(relation_id, bool) or not isinstance(relation_id, int) or relation_id < 0:
            raise ValueError("relation_id must be a non-negative integer")
        if relation_id in self._by_id:
            raise ValueError(f"relation id {relation_id} is already registered")
        spec = RelationSpec(relation_id, normalized)
        self._by_id[relation_id] = spec
        self._by_name[normalized] = spec
        return spec

    def resolve_id(self, relation_id: int) -> RelationSpec:
        try:
            return self._by_id[relation_id]
        except KeyError as exc:
            raise KeyError(f"unknown relation id {relation_id}") from exc

    def resolve_name(self, name: str) -> RelationSpec:
        normalized = atom(name)
        try:
            return self._by_name[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown relation {normalized!r}") from exc

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
