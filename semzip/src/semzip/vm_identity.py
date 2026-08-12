from __future__ import annotations

from dataclasses import dataclass, field

from .vm_mentions import SlottedText


class AmbiguousEntityIdentity(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    mention_index: int
    surface: str
    entity_id: str
    status: str  # known | provisional


@dataclass(slots=True)
class IdentityStore:
    """Persistent identity table with explicit alias commitment.

    Unknown mention surfaces are assigned provisional occurrence IDs but are *not*
    automatically inserted into the alias index. Therefore two unknown mentions with
    identical text remain distinct until some later resolver explicitly links them.
    """

    _aliases: dict[str, set[str]] = field(default_factory=dict)
    _surfaces: dict[str, set[str]] = field(default_factory=dict)
    _counter: int = 0

    @staticmethod
    def normalize_surface(surface: str) -> str:
        return " ".join(str(surface).strip().casefold().split())

    def register_entity(self, entity_id: str, *, aliases=()) -> str:
        identity = str(entity_id).strip()
        if not identity:
            raise ValueError("entity_id cannot be empty")
        self._surfaces.setdefault(identity, set())
        for alias in aliases:
            self.commit_alias(identity, alias)
        return identity

    def commit_alias(self, entity_id: str, surface: str) -> None:
        identity = self.register_entity(entity_id)
        normalized = self.normalize_surface(surface)
        if not normalized:
            raise ValueError("alias cannot be empty")
        self._aliases.setdefault(normalized, set()).add(identity)
        self._surfaces[identity].add(normalized)

    def alias_candidates(self, surface: str) -> tuple[str, ...]:
        normalized = self.normalize_surface(surface)
        return tuple(sorted(self._aliases.get(normalized, ())))

    def new_provisional_id(self) -> str:
        while True:
            identity = f"entity#{self._counter}"
            self._counter += 1
            if identity not in self._surfaces:
                self._surfaces[identity] = set()
                return identity

    def resolve_surface(self, surface: str) -> tuple[str, str]:
        candidates = self.alias_candidates(surface)
        if len(candidates) == 1:
            return candidates[0], "known"
        if len(candidates) > 1:
            raise AmbiguousEntityIdentity(
                f"surface {surface!r} matches multiple entities: {candidates}"
            )
        return self.new_provisional_id(), "provisional"

    def resolve_slotted(self, slotted: SlottedText) -> tuple[IdentityResolution, ...]:
        result = []
        for index, surface in enumerate(slotted.entities):
            entity_id, status = self.resolve_surface(surface)
            result.append(IdentityResolution(index, surface, entity_id, status))
        return tuple(result)

    def frontend_resolver(self, slotted: SlottedText) -> tuple[str, ...]:
        return tuple(item.entity_id for item in self.resolve_slotted(slotted))
