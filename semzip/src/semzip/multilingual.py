from __future__ import annotations

import re
from typing import Protocol

from .meaning import Meaning
from .molecules import transfer_possession


class SemanticTextAdapter(Protocol):
    def encode(self, text: str) -> Meaning:
        ...


class UnsupportedAdapterText(ValueError):
    pass


class MiniTransferAdapter:
    """Tiny bilingual edge adapter used only to test cross-language convergence.

    It is not intended as a general English/Spanish parser. The semantic substrate
    remains language-neutral; this module demonstrates that separate surface
    grammars can compile into the same transfer molecule.
    """

    _EN_GIVE = re.compile(
        r"^(?P<source>[A-Za-z][\w'-]*) gave "
        r"(?P<destination>[A-Za-z][\w'-]*) the (?P<item>[A-Za-z][\w'-]*)$",
        re.I,
    )
    _EN_RECEIVE = re.compile(
        r"^(?P<destination>[A-Za-z][\w'-]*) received the "
        r"(?P<item>[A-Za-z][\w'-]*) from (?P<source>[A-Za-z][\w'-]*)$",
        re.I,
    )
    _ES_GIVE = re.compile(
        r"^(?P<source>[A-Za-z][\w'-]*) le dio (?:el|la) "
        r"(?P<item>[A-Za-záéíóúñ][\wáéíóúñ'-]*) a "
        r"(?P<destination>[A-Za-z][\w'-]*)$",
        re.I,
    )
    _ES_RECEIVE = re.compile(
        r"^(?P<destination>[A-Za-z][\w'-]*) recibió (?:el|la) "
        r"(?P<item>[A-Za-záéíóúñ][\wáéíóúñ'-]*) de "
        r"(?P<source>[A-Za-z][\w'-]*)$",
        re.I,
    )

    _CONCEPTS = {
        "book": "book",
        "libro": "book",
        "key": "key",
        "llave": "key",
    }

    def encode(self, text: str) -> Meaning:
        surface = self._normalize(text)
        for pattern in (
            self._EN_GIVE,
            self._EN_RECEIVE,
            self._ES_GIVE,
            self._ES_RECEIVE,
        ):
            match = pattern.fullmatch(surface)
            if match:
                fields = match.groupdict()
                item = self._concept(fields["item"])
                return transfer_possession(
                    item,
                    fields["source"],
                    fields["destination"],
                )
        raise UnsupportedAdapterText(
            f"mini bilingual adapter cannot safely represent: {surface!r}"
        )

    @classmethod
    def _concept(cls, surface: str) -> str:
        concept = cls._CONCEPTS.get(surface.casefold())
        if concept is None:
            raise UnsupportedAdapterText(
                f"no language-neutral concept mapping for {surface!r}"
            )
        return concept

    @staticmethod
    def _normalize(text: str) -> str:
        text = " ".join(text.strip().split())
        return re.sub(r"[.!?]+$", "", text)
