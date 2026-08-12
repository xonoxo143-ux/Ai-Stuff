from __future__ import annotations

from .model import CharacterMind, Event, atom
from .world import World


def can_perceive(witness: str, event: Event, world: World) -> bool:
    witness = atom(witness)
    if witness == event.actor or witness == event.target:
        return True
    witness_location = world.fact(witness, "location")
    if witness_location is None:
        return False
    if event.kind == "move":
        # A witness can perceive somebody leaving its room or arriving in it.
        before = event.datum("before")
        after = event.datum("after")
        return witness_location in {before, after}
    if event.location is None:
        return False
    return witness_location == event.location


def observe_event(mind: CharacterMind, event: Event, world: World) -> None:
    """Update only what this mind could infer from a perceived event."""
    name = atom(mind.name)
    if not can_perceive(name, event, world):
        return

    if not event.succeeded:
        if event.actor == "user" and event.reason == "unknown_object":
            mind.remember(event, f"user tried to take nonexistent {event.object_id}", salience=0.35)
        return

    if event.kind in {"take", "give"} and event.object_id:
        possessor = event.datum("after_possessor")
        if possessor:
            mind.believe(event.object_id, "possessor", possessor, source_event=event.seq)
            if event.location:
                mind.believe(event.object_id, "location", event.location, source_event=event.seq)
        if event.kind == "take" and event.target == name and event.actor != name:
            mind.adjust_relation(event.actor, "trust", -0.25)
            mind.remember(event, f"{event.actor} took {event.object_id} from me", salience=0.9)
        else:
            mind.remember(event, f"{event.actor} {event.kind} {event.object_id}", salience=0.6)
        return

    if event.kind == "move":
        mind.believe(event.actor, "location", event.location, source_event=event.seq)
        # If the mind already believes an object is carried by the mover, it can
        # propagate the location consequence without separately perceiving the object.
        for belief in tuple(mind.beliefs.values()):
            if belief.dimension == "possessor" and atom(belief.value or "") == event.actor:
                mind.believe(belief.subject, "location", event.location, source_event=event.seq)
        mind.remember(event, f"{event.actor} moved to {event.location}", salience=0.35)
        return

    if event.kind == "set_fact" and event.object_id:
        dimension = event.datum("dimension")
        value = event.datum("after")
        if dimension and value:
            mind.believe(event.object_id, dimension, value, source_event=event.seq)
        return


def sync_initial_observation(mind: CharacterMind, world: World) -> None:
    """Seed beliefs for facts that are directly observable at the character's location."""
    name = atom(mind.name)
    loc = world.fact(name, "location")
    if loc:
        mind.believe(name, "location", loc)
    for (subject, dimension), value in world.facts.items():
        if subject == name:
            mind.believe(subject, dimension, value)
            continue
        subject_loc = world.fact(subject, "location")
        possessor = world.fact(subject, "possessor")
        if subject_loc == loc or possessor == name:
            if dimension in {"type", "location", "possessor", "owner", "condition"}:
                mind.believe(subject, dimension, value)
