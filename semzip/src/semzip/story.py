from __future__ import annotations

import re
from typing import Callable

from .collections import ambiguity, bundle
from .meaning import Meaning
from .world import WorldModel


class UnsupportedStorySentence(ValueError):
    pass


class AmbiguousReferenceError(UnsupportedStorySentence):
    """Raised only when a caller explicitly demands one referent."""


Reference = str | tuple[str, ...]


class MiniWorldInterpreter:
    """Dependency-free parser for the small world-model gates.

    Entity identity is separate from lexical type. When a definite reference has
    several candidates, parse() preserves the alternatives in AMBIGUITY rather
    than guessing. feed() refuses to mutate reality until ambiguity is resolved.
    """

    _OWNED = re.compile(
        r"^(?P<owner>[A-Za-z][A-Za-z0-9_'-]*) owned (?P<article>a|an|the) "
        r"(?:(?P<modifier>[A-Za-z]+) )?(?P<object>[A-Za-z][A-Za-z0-9_'-]*)$",
        re.I,
    )
    _GAVE = re.compile(
        r"^(?P<agent>[A-Za-z][A-Za-z0-9_'-]*) gave (?:the )?"
        r"(?P<object>[A-Za-z][A-Za-z0-9_'-]*) to "
        r"(?P<recipient>[A-Za-z][A-Za-z0-9_'-]*)$",
        re.I,
    )
    _PUT = re.compile(
        r"^(?P<actor>[A-Za-z][A-Za-z0-9_'-]*) put "
        r"(?P<object>it|the [A-Za-z][A-Za-z0-9_'-]*) in "
        r"(?:the )?(?P<location>[A-Za-z][A-Za-z0-9_'-]*)$",
        re.I,
    )
    _BELIEF = re.compile(
        r"^(?P<holder>[A-Za-z][A-Za-z0-9_'-]*) believes (?:that )?the "
        r"(?P<object>[A-Za-z][A-Za-z0-9_'-]*) is (?:still )?with "
        r"(?P<owner>[A-Za-z][A-Za-z0-9_'-]*)$",
        re.I,
    )
    _MOVED = re.compile(
        r"^(?:later, )?(?P<actor>[A-Za-z][A-Za-z0-9_'-]*) moved (?:the )?"
        r"(?P<object>[A-Za-z][A-Za-z0-9_'-]*) to (?:the )?"
        r"(?P<location>[A-Za-z][A-Za-z0-9_'-]*)$",
        re.I,
    )
    _DOES_NOT_KNOW = re.compile(
        r"^(?P<holder>[A-Za-z][A-Za-z0-9_'-]*) does not know where (?:the )?"
        r"(?P<object>[A-Za-z][A-Za-z0-9_'-]*) is$",
        re.I,
    )

    def __init__(self) -> None:
        self.world = WorldModel()
        self._last_object: str | None = None
        self._entities_by_type: dict[str, list[str]] = {}

    def feed(self, sentence: str) -> tuple[Meaning, ...]:
        meanings = self.parse(self._normalize(sentence))
        if any(meaning.operator == "AMBIGUITY" for meaning in meanings):
            return meanings
        self.world.apply_many(meanings)
        return meanings

    def parse(self, text: str) -> tuple[Meaning, ...]:
        if match := self._OWNED.fullmatch(text):
            d = match.groupdict()
            noun = d["object"].casefold()
            article = d["article"].casefold()
            if article in {"a", "an"}:
                obj = self._new_entity(noun)
                return self._owned_meanings(obj, noun, d["owner"], d.get("modifier"))

            ref = self._resolve_reference(noun)
            return self._branch_many(
                ref,
                lambda obj: self._owned_meanings(
                    obj, noun, d["owner"], d.get("modifier")
                ),
            )

        if match := self._GAVE.fullmatch(text):
            d = match.groupdict()
            ref = self._resolve_reference(d["object"])
            return self._branch_one(
                ref,
                lambda obj: Meaning.build(
                    "CHANGE",
                    {
                        "subject": obj,
                        "dimension": "owner",
                        "before": d["agent"],
                        "after": d["recipient"],
                        "actor": d["agent"],
                    },
                ),
            )

        if match := self._PUT.fullmatch(text):
            d = match.groupdict()
            ref = self._resolve_object(d["object"])
            return self._branch_one(
                ref,
                lambda obj: Meaning.build(
                    "CHANGE",
                    {
                        "subject": obj,
                        "dimension": "location",
                        "after": d["location"],
                        "actor": d["actor"],
                    },
                ),
            )

        if match := self._BELIEF.fullmatch(text):
            d = match.groupdict()
            ref = self._resolve_reference(d["object"])
            return self._branch_one(
                ref,
                lambda obj: Meaning.build(
                    "BELIEVE",
                    {
                        "holder": d["holder"],
                        "content": Meaning.build(
                            "STATE",
                            {
                                "subject": obj,
                                "dimension": "owner",
                                "value": d["owner"],
                            },
                        ),
                    },
                ),
            )

        if match := self._MOVED.fullmatch(text):
            d = match.groupdict()
            ref = self._resolve_reference(d["object"])
            return self._branch_one(
                ref,
                lambda obj: Meaning.build(
                    "CHANGE",
                    {
                        "subject": obj,
                        "dimension": "location",
                        "after": d["location"],
                        "actor": d["actor"],
                    },
                ),
            )

        if match := self._DOES_NOT_KNOW.fullmatch(text):
            d = match.groupdict()
            ref = self._resolve_reference(d["object"])
            return self._branch_one(
                ref,
                lambda obj: Meaning.build(
                    "NOT",
                    {
                        "content": Meaning.build(
                            "KNOW_VALUE",
                            {
                                "holder": d["holder"],
                                "subject": obj,
                                "dimension": "location",
                            },
                        )
                    },
                ),
            )

        raise UnsupportedStorySentence(
            f"mini-world grammar cannot safely represent: {text!r}"
        )

    def _owned_meanings(
        self,
        obj: str,
        noun: str,
        owner: str,
        modifier: str | None,
    ) -> tuple[Meaning, ...]:
        self._last_object = obj
        meanings = [
            Meaning.build(
                "STATE",
                {"subject": obj, "dimension": "type", "value": noun},
            ),
            Meaning.build(
                "STATE",
                {"subject": obj, "dimension": "owner", "value": owner},
            ),
        ]
        if modifier:
            meanings.append(
                Meaning.build(
                    "STATE",
                    {"subject": obj, "dimension": "color", "value": modifier},
                )
            )
        return tuple(meanings)

    def _resolve_object(self, surface: str) -> Reference:
        if surface.casefold() == "it":
            if self._last_object is None:
                raise UnsupportedStorySentence("pronoun 'it' has no known referent")
            return self._last_object
        noun = re.sub(r"^the +", "", surface, flags=re.I).casefold()
        return self._resolve_reference(noun)

    def _new_entity(self, noun: str) -> str:
        noun = noun.casefold()
        bucket = self._entities_by_type.setdefault(noun, [])
        entity_id = noun if not bucket else f"{noun}#{len(bucket) + 1}"
        bucket.append(entity_id)
        return entity_id

    def _resolve_reference(self, noun: str) -> Reference:
        noun = noun.casefold()
        candidates = tuple(self._entities_by_type.get(noun, ()))
        if not candidates:
            raise UnsupportedStorySentence(f"no known referent for {noun!r}")
        if len(candidates) == 1:
            return candidates[0]
        return candidates

    def resolve_unique(self, noun: str) -> str:
        ref = self._resolve_reference(noun)
        if isinstance(ref, tuple):
            raise AmbiguousReferenceError(
                f"reference {noun!r} matches multiple entities: {list(ref)}"
            )
        return ref

    def _branch_one(
        self,
        ref: Reference,
        builder: Callable[[str], Meaning],
    ) -> tuple[Meaning, ...]:
        if isinstance(ref, str):
            self._last_object = ref
            return (builder(ref),)
        options = tuple(builder(candidate) for candidate in ref)
        return (ambiguity(options),)

    def _branch_many(
        self,
        ref: Reference,
        builder: Callable[[str], tuple[Meaning, ...]],
    ) -> tuple[Meaning, ...]:
        if isinstance(ref, str):
            self._last_object = ref
            return builder(ref)
        options = tuple(bundle(builder(candidate)) for candidate in ref)
        return (ambiguity(options),)

    @staticmethod
    def _normalize(text: str) -> str:
        text = " ".join(text.strip().split())
        return re.sub(r"[.!?]+$", "", text)
