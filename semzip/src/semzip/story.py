from __future__ import annotations

import re

from .meaning import Meaning
from .world import WorldModel


class UnsupportedStorySentence(ValueError):
    pass


class AmbiguousReferenceError(UnsupportedStorySentence):
    pass


class MiniWorldInterpreter:
    """Dependency-free parser for the v0.2/v0.3 world-model gates.

    The grammar is intentionally small. Entity identity is separate from lexical
    type so multiple objects of the same kind can exist without being merged.
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
        self.world.apply_many(meanings)
        return meanings

    def parse(self, text: str) -> tuple[Meaning, ...]:
        if match := self._OWNED.fullmatch(text):
            d = match.groupdict()
            noun = d["object"].casefold()
            article = d["article"].casefold()
            obj = (
                self._new_entity(noun)
                if article in {"a", "an"}
                else self._resolve_type(noun)
            )
            self._last_object = obj
            meanings = [
                Meaning.build(
                    "STATE",
                    {"subject": obj, "dimension": "type", "value": noun},
                ),
                Meaning.build(
                    "STATE",
                    {"subject": obj, "dimension": "owner", "value": d["owner"]},
                ),
            ]
            if d.get("modifier"):
                meanings.append(
                    Meaning.build(
                        "STATE",
                        {
                            "subject": obj,
                            "dimension": "color",
                            "value": d["modifier"],
                        },
                    )
                )
            return tuple(meanings)

        if match := self._GAVE.fullmatch(text):
            d = match.groupdict()
            obj = self._resolve_type(d["object"])
            self._last_object = obj
            return (
                Meaning.build(
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
            obj = self._resolve_object(d["object"])
            self._last_object = obj
            return (
                Meaning.build(
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
            obj = self._resolve_type(d["object"])
            self._last_object = obj
            content = Meaning.build(
                "STATE",
                {
                    "subject": obj,
                    "dimension": "owner",
                    "value": d["owner"],
                },
            )
            return (
                Meaning.build(
                    "BELIEVE",
                    {"holder": d["holder"], "content": content},
                ),
            )

        if match := self._MOVED.fullmatch(text):
            d = match.groupdict()
            obj = self._resolve_type(d["object"])
            self._last_object = obj
            return (
                Meaning.build(
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
            obj = self._resolve_type(d["object"])
            self._last_object = obj
            query = Meaning.build(
                "KNOW_VALUE",
                {
                    "holder": d["holder"],
                    "subject": obj,
                    "dimension": "location",
                },
            )
            return (Meaning.build("NOT", {"content": query}),)

        raise UnsupportedStorySentence(
            f"mini-world grammar cannot safely represent: {text!r}"
        )

    def _resolve_object(self, surface: str) -> str:
        if surface.casefold() == "it":
            if self._last_object is None:
                raise UnsupportedStorySentence("pronoun 'it' has no known referent")
            return self._last_object
        noun = re.sub(r"^the +", "", surface, flags=re.I).casefold()
        return self._resolve_type(noun)

    def _new_entity(self, noun: str) -> str:
        noun = noun.casefold()
        bucket = self._entities_by_type.setdefault(noun, [])
        entity_id = noun if not bucket else f"{noun}#{len(bucket) + 1}"
        bucket.append(entity_id)
        return entity_id

    def _resolve_type(self, noun: str) -> str:
        noun = noun.casefold()
        candidates = self._entities_by_type.get(noun, [])
        if not candidates:
            raise UnsupportedStorySentence(f"no known referent for {noun!r}")
        if len(candidates) > 1:
            raise AmbiguousReferenceError(
                f"reference {noun!r} matches multiple entities: {candidates}"
            )
        return candidates[0]

    @staticmethod
    def _normalize(text: str) -> str:
        text = " ".join(text.strip().split())
        return re.sub(r"[.!?]+$", "", text)
