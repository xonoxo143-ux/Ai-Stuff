from __future__ import annotations

import re

from .model import SemanticGraph


class UnsupportedMeaningError(ValueError):
    """Raised when the seed parser cannot safely canonicalize an input."""


class SemZipCodec:
    """Dependency-free v0.1 semantic codec.

    The seed grammar intentionally supports only a tiny transfer domain. The
    architecture is the experiment; broad language coverage comes later via adapters
    and learned parsers.
    """

    _ACTIVE = re.compile(
        r"^(?P<agent>[A-Za-z][\w'-]*)\s+"
        r"(?P<neg>did\s+not\s+give|didn't\s+give|gave)\s+"
        r"(?P<recipient>[A-Za-z][\w'-]*)\s+"
        r"(?:the|a|an)\s+(?P<theme>.+?)$",
        re.IGNORECASE,
    )
    _RECEIVE = re.compile(
        r"^(?P<recipient>[A-Za-z][\w'-]*)\s+"
        r"(?P<neg>did\s+not\s+receive|didn't\s+receive|received)\s+"
        r"(?:the|a|an)\s+(?P<theme>.+?)\s+from\s+"
        r"(?P<agent>[A-Za-z][\w'-]*)$",
        re.IGNORECASE,
    )
    _PASSIVE = re.compile(
        r"^(?:the|a|an)\s+(?P<theme>.+?)\s+"
        r"(?P<neg>was\s+not\s+given|wasn't\s+given|was\s+given)\s+to\s+"
        r"(?P<recipient>[A-Za-z][\w'-]*)\s+by\s+"
        r"(?P<agent>[A-Za-z][\w'-]*)$",
        re.IGNORECASE,
    )

    def encode(self, text: str) -> SemanticGraph:
        text = self._normalize_surface(text)

        for pattern in (self._ACTIVE, self._RECEIVE, self._PASSIVE):
            match = pattern.fullmatch(text)
            if match:
                fields = match.groupdict()
                polarity = "not" not in fields["neg"].casefold() and "n't" not in fields["neg"].casefold()
                return SemanticGraph.build(
                    "TRANSFER",
                    {
                        "agent": fields["agent"],
                        "recipient": fields["recipient"],
                        "theme": self._normalize_theme(fields["theme"]),
                    },
                    polarity=polarity,
                )

        raise UnsupportedMeaningError(
            "v0.1 could not safely canonicalize this sentence; "
            "unsupported meaning is rejected rather than guessed"
        )

    def decode(self, graph: SemanticGraph) -> str:
        if graph.predicate != "TRANSFER":
            raise UnsupportedMeaningError(f"no generator for predicate {graph.predicate!r}")

        agent = graph.role("AGENT")
        recipient = graph.role("RECIPIENT")
        theme = graph.role("THEME")
        if not all((agent, recipient, theme)):
            raise UnsupportedMeaningError("TRANSFER graph is missing a required role")

        agent_s = self._display_name(agent)
        recipient_s = self._display_name(recipient)
        if graph.polarity:
            return f"{agent_s} gave {recipient_s} the {theme}."
        return f"{agent_s} did not give {recipient_s} the {theme}."

    def roundtrip(self, text: str) -> tuple[SemanticGraph, str, SemanticGraph]:
        first = self.encode(text)
        regenerated = self.decode(first)
        second = self.encode(regenerated)
        return first, regenerated, second

    @staticmethod
    def equivalent(left: SemanticGraph, right: SemanticGraph) -> bool:
        return left == right

    @staticmethod
    def _normalize_surface(text: str) -> str:
        text = " ".join(text.strip().split())
        text = re.sub(r"[.!?]+$", "", text)
        return text

    @staticmethod
    def _normalize_theme(theme: str) -> str:
        theme = " ".join(theme.strip().split()).casefold()
        # The seed keeps modifiers because dropping them would create false equivalence.
        return theme

    @staticmethod
    def _display_name(value: str) -> str:
        return value[:1].upper() + value[1:]
