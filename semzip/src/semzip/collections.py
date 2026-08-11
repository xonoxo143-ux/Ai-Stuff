from __future__ import annotations

from collections.abc import Iterable

from .meaning import Meaning


def ambiguity(options: Iterable[Meaning]) -> Meaning:
    """Canonical unresolved alternatives.

    Alternative order is not meaningful, so duplicate meanings are removed and
    remaining options are sorted by semantic hash before serialization/hashing.
    """
    unique = {item.semantic_hash(): item for item in options}
    ordered = tuple(unique[key] for key in sorted(unique))
    if not ordered:
        raise ValueError("ambiguity requires at least one option")
    return Meaning.build("AMBIGUITY", {"options": ordered})


def bundle(items: Iterable[Meaning]) -> Meaning:
    """Canonical conjunction of semantic expressions."""
    unique = {item.semantic_hash(): item for item in items}
    ordered = tuple(unique[key] for key in sorted(unique))
    if not ordered:
        raise ValueError("bundle requires at least one item")
    return Meaning.build("BUNDLE", {"items": ordered})


def semantic_set(members: Iterable[str]) -> Meaning:
    """Canonical unordered set of atom identifiers."""
    ordered = tuple(
        sorted(
            {
                member.strip().casefold().replace(" ", "_")
                for member in members
                if member.strip()
            }
        )
    )
    return Meaning.build("SET", {"members": ordered})
