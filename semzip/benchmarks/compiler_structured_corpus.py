from __future__ import annotations

from dataclasses import dataclass
import json
import re

from compiler_corpus import CompilerExample, generate_examples
from compiler_slot_corpus import slotize


OPERATION_IDS = {"give": 0, "lend": 1, "move": 2, "sell": 3}
OPERATION_NAMES = ("M0", "M1", "M2", "M3")
NONE_SLOT = 4
MAX_SLOTS = 4


@dataclass(frozen=True, slots=True)
class StructuredExample:
    text: str
    operation: int
    args: tuple[int, int, int, int]
    family: str
    slots: tuple[tuple[str, str], ...]


def _replace_atom(text: str, atom: str, slot: str) -> str:
    return re.sub(
        rf"(?<![A-Za-z0-9_]){re.escape(atom)}(?![A-Za-z0-9_])",
        slot,
        text,
        flags=re.I,
    )


def _normalized_text(example: CompilerExample, slots: tuple[tuple[str, str], ...]) -> str:
    text = example.text
    # Longest first avoids a shorter atom accidentally eating part of a longer one.
    for slot, atom in sorted(slots, key=lambda pair: len(pair[1]), reverse=True):
        text = _replace_atom(text, atom, slot)
    return text


def _slot_index(atom: str, slots: tuple[tuple[str, str], ...]) -> int:
    lookup = {value.casefold(): int(slot[1:]) for slot, value in slots}
    try:
        return lookup[atom.casefold()]
    except KeyError as exc:
        raise ValueError(f"atom {atom!r} is not represented by an entity slot") from exc


def _shift_rows(example: CompilerExample) -> list[tuple[str, str, str, str]]:
    data = json.loads(example.target)
    rows: list[tuple[str, str, str, str]] = []
    for ins in data["instructions"]:
        if ins["opcode"] != "K1":
            continue
        subject, relation, before, after = ins["args"]
        rows.append((subject, relation, before, after))
    return rows


def _canonical_args(example: CompilerExample, slots: tuple[tuple[str, str], ...]) -> tuple[int, int, int, int]:
    rows = _shift_rows(example)
    if example.family == "give":
        subject, _, giver, recipient = next(row for row in rows if row[1] == "owner")
        raw = (giver, recipient, subject)
    elif example.family == "lend":
        subject, _, lender, borrower = next(row for row in rows if row[1] == "possessor")
        raw = (lender, borrower, subject)
    elif example.family == "move":
        subject, _, source, destination = next(row for row in rows if row[1] == "location")
        raw = (subject, source, destination)
    elif example.family == "sell":
        owner_rows = [row for row in rows if row[1] == "owner"]
        goods, _, seller, buyer = owner_rows[0]
        payment, _, payment_owner, payment_recipient = owner_rows[1]
        if payment_owner != buyer or payment_recipient != seller:
            raise ValueError("sale payment direction does not match goods direction")
        raw = (seller, buyer, goods, payment)
    else:
        raise ValueError(f"unknown family {example.family}")

    indices = tuple(_slot_index(atom, slots) for atom in raw)
    padded = indices + (NONE_SLOT,) * (4 - len(indices))
    return padded  # type: ignore[return-value]


def structure(example: CompilerExample) -> StructuredExample:
    slotted = slotize(example)
    if len(slotted.slots) > MAX_SLOTS:
        raise ValueError(f"example has {len(slotted.slots)} slots; max is {MAX_SLOTS}")
    normalized = _normalized_text(example, slotted.slots)
    return StructuredExample(
        text=normalized,
        operation=OPERATION_IDS[example.family],
        args=_canonical_args(example, slotted.slots),
        family=example.family,
        slots=slotted.slots,
    )


def generate_structured_examples(count: int, *, split: str, seed: int = 0) -> tuple[StructuredExample, ...]:
    return tuple(structure(x) for x in generate_examples(count, split=split, seed=seed))


if __name__ == "__main__":
    for x in generate_structured_examples(8, split="eval", seed=4):
        print(x.family, x.text, OPERATION_NAMES[x.operation], x.args, x.slots)
