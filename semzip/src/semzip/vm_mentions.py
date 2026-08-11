from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MentionSpan:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class SlottedText:
    text: str
    entities: tuple[str, ...]
    mentions: tuple[MentionSpan, ...]


def slotize_mentions(text: str, spans, *, prefix: str = "E") -> SlottedText:
    """Replace trusted/detected mention spans with deterministic entity pointers.

    Mention detection is allowed to be fuzzy/neural; assigning stable pointer IDs is
    not. IDs are always left-to-right span order, so the compiler never has to spell
    entity strings or invent identifier names.
    """

    raw = str(text)
    normalized: list[tuple[int, int]] = []
    for span in spans:
        if len(span) != 2:
            raise ValueError("each mention span must be a (start, end) pair")
        start, end = span
        if isinstance(start, bool) or isinstance(end, bool):
            raise ValueError("mention offsets must be integers")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("mention offsets must be integers")
        if not 0 <= start < end <= len(raw):
            raise ValueError(f"invalid mention span {(start, end)} for text length {len(raw)}")
        normalized.append((start, end))

    ordered = sorted(set(normalized))
    previous_end = -1
    for start, end in ordered:
        if start < previous_end:
            raise ValueError("mention spans may not overlap")
        previous_end = end

    parts: list[str] = []
    entities: list[str] = []
    mentions: list[MentionSpan] = []
    cursor = 0
    for index, (start, end) in enumerate(ordered):
        parts.append(raw[cursor:start])
        parts.append(f"{prefix}{index}")
        surface = raw[start:end]
        entities.append(surface)
        mentions.append(MentionSpan(start, end, surface))
        cursor = end
    parts.append(raw[cursor:])
    return SlottedText("".join(parts), tuple(entities), tuple(mentions))
