from __future__ import annotations

from dataclasses import dataclass, field

from .model import Event, FactKey, atom


@dataclass(slots=True)
class World:
    """Event-sourced RP world with cached projections for cheap queries."""

    events: list[Event] = field(default_factory=list)
    facts: dict[FactKey, str] = field(default_factory=dict)
    entities: set[str] = field(default_factory=set)

    @property
    def clock(self) -> int:
        return len(self.events)

    def fact(self, subject: str, dimension: str) -> str | None:
        return self.facts.get((atom(subject), atom(dimension)))

    def exists(self, entity: str) -> bool:
        return atom(entity) in self.entities

    def establish(self, subject: str, dimension: str, value: str, *, actor: str = "system") -> Event:
        subject, dimension, value = atom(subject), atom(dimension), atom(value)
        self.entities.add(subject)
        event = Event.build(
            self.clock + 1,
            "establish",
            actor,
            object_id=subject,
            data={"dimension": dimension, "value": value},
        )
        self._record(event)
        return event

    def create_entity(
        self,
        entity: str,
        entity_type: str,
        *,
        location: str | None = None,
        owner: str | None = None,
        possessor: str | None = None,
    ) -> tuple[Event, ...]:
        entity = atom(entity)
        if self.exists(entity):
            raise ValueError(f"entity already exists: {entity}")
        out = [self.establish(entity, "type", entity_type)]
        if location is not None:
            out.append(self.establish(entity, "location", location))
        if owner is not None:
            out.append(self.establish(entity, "owner", owner))
        if possessor is not None:
            out.append(self.establish(entity, "possessor", possessor))
        return tuple(out)

    def move(self, actor: str, destination: str) -> Event:
        actor = atom(actor)
        if not self.exists(actor):
            return self._fail("move", actor, reason="unknown_actor", location=destination)
        old = self.fact(actor, "location")
        event = Event.build(
            self.clock + 1,
            "move",
            actor,
            location=destination,
            data={"before": old or "unknown", "after": atom(destination)},
        )
        self._record(event)
        return event

    def take(self, actor: str, object_id: str, *, from_actor: str | None = None) -> Event:
        actor, object_id = atom(actor), atom(object_id)
        source = atom(from_actor) if from_actor else self.fact(object_id, "possessor")
        if not self.exists(actor):
            return self._fail("take", actor, object_id=object_id, reason="unknown_actor")
        if not self.exists(object_id):
            return self._fail("take", actor, object_id=object_id, target=source, reason="unknown_object")
        if source == actor:
            return self._fail("take", actor, object_id=object_id, target=source, reason="already_has_object")

        object_location = self.fact(object_id, "location")
        actor_location = self.fact(actor, "location")
        source_location = self.fact(source, "location") if source else object_location
        effective_location = source_location or object_location
        if actor_location is not None and effective_location is not None and actor_location != effective_location:
            return self._fail("take", actor, object_id=object_id, target=source, reason="not_co_located")

        event = Event.build(
            self.clock + 1,
            "take",
            actor,
            target=source,
            object_id=object_id,
            location=actor_location,
            data={"before_possessor": source or "none", "after_possessor": actor},
        )
        self._record(event)
        return event

    def give(self, actor: str, recipient: str, object_id: str) -> Event:
        actor, recipient, object_id = atom(actor), atom(recipient), atom(object_id)
        if not self.exists(object_id):
            return self._fail("give", actor, target=recipient, object_id=object_id, reason="unknown_object")
        if self.fact(object_id, "possessor") != actor:
            return self._fail("give", actor, target=recipient, object_id=object_id, reason="not_possessor")
        if not self.exists(recipient):
            return self._fail("give", actor, target=recipient, object_id=object_id, reason="unknown_recipient")
        if self.fact(actor, "location") != self.fact(recipient, "location"):
            return self._fail("give", actor, target=recipient, object_id=object_id, reason="not_co_located")
        event = Event.build(
            self.clock + 1,
            "give",
            actor,
            target=recipient,
            object_id=object_id,
            location=self.fact(actor, "location"),
            data={"before_possessor": actor, "after_possessor": recipient},
        )
        self._record(event)
        return event

    def set_fact(self, actor: str, subject: str, dimension: str, value: str) -> Event:
        subject, dimension, value = atom(subject), atom(dimension), atom(value)
        if not self.exists(subject):
            return self._fail("set_fact", actor, object_id=subject, reason="unknown_subject")
        before = self.fact(subject, dimension)
        event = Event.build(
            self.clock + 1,
            "set_fact",
            actor,
            object_id=subject,
            data={"dimension": dimension, "before": before or "unknown", "after": value},
        )
        self._record(event)
        return event

    def _fail(
        self,
        kind: str,
        actor: str,
        *,
        target: str | None = None,
        object_id: str | None = None,
        location: str | None = None,
        reason: str,
    ) -> Event:
        event = Event.build(
            self.clock + 1,
            kind,
            actor,
            target=target,
            object_id=object_id,
            location=location,
            succeeded=False,
            reason=reason,
        )
        self._record(event)
        return event

    def _record(self, event: Event) -> None:
        self.events.append(event)
        if not event.succeeded:
            return
        if event.kind == "establish":
            subject = event.object_id
            dimension, value = event.datum("dimension"), event.datum("value")
            assert subject and dimension and value
            self.facts[(subject, atom(dimension))] = atom(value)
            if dimension == "type":
                self.entities.add(subject)
            return
        if event.kind == "move":
            assert event.location
            self.facts[(event.actor, "location")] = event.location
            # Carried objects move with their possessor.
            for (subject, dimension), value in list(self.facts.items()):
                if dimension == "possessor" and value == event.actor:
                    self.facts[(subject, "location")] = event.location
            return
        if event.kind in {"take", "give"}:
            assert event.object_id
            new_possessor = event.datum("after_possessor")
            assert new_possessor
            self.facts[(event.object_id, "possessor")] = atom(new_possessor)
            if event.location:
                self.facts[(event.object_id, "location")] = event.location
            return
        if event.kind == "set_fact":
            assert event.object_id
            dimension, value = event.datum("dimension"), event.datum("after")
            assert dimension and value
            self.facts[(event.object_id, atom(dimension))] = atom(value)
