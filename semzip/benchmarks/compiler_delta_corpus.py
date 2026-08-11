from __future__ import annotations

from dataclasses import dataclass
import random
import re

from compiler_corpus import (
    EVAL_ITEMS,
    EVAL_NAMES,
    EVAL_PAYMENTS,
    EVAL_ROOMS,
    TRAIN_ITEMS,
    TRAIN_NAMES,
    TRAIN_PAYMENTS,
    TRAIN_ROOMS,
)


MAX_SLOTS = 4
NONE_SLOT = 4
# Relation order is grounded in world-state dimensions, not lexical action names.
RELATIONS = ("owner", "possessor", "location")


TRAIN_TEMPLATES = {
    "give": (
        "{a} gave {b} the {item}.",
        "{b} received the {item} from {a}.",
        "The {item} was given to {b} by {a}.",
        "{a} handed the {item} to {b}.",
        "{a} passed the {item} to {b}.",
        "{b} was given the {item} by {a}.",
    ),
    "lend": (
        "{a} lent {b} the {item}.",
        "{b} borrowed the {item} from {a}.",
        "The {item} was lent to {b} by {a}.",
        "{a} loaned the {item} to {b}.",
        "{a} let {b} borrow the {item}.",
        "{b} took the {item} on loan from {a}.",
    ),
    "move": (
        "{a} moved the {item} from the {src} to the {dst}.",
        "{a} carried the {item} from the {src} to the {dst}.",
        "{a} relocated the {item} from the {src} to the {dst}.",
        "The {item} went from the {src} to the {dst} when {a} moved it.",
        "{a} took the {item} from the {src} to the {dst}.",
        "The {item} was moved from the {src} to the {dst} by {a}.",
    ),
    "sell": (
        "{a} sold {b} the {item} for the {payment}.",
        "{b} bought the {item} from {a} with the {payment}.",
        "{b} paid {a} the {payment} and received the {item}.",
        "The {item} was sold by {a} to {b} for the {payment}.",
        "{a} sold the {item} to {b} in exchange for the {payment}.",
        "{b} purchased the {item} from {a} using the {payment}.",
    ),
}

EVAL_TEMPLATES = {
    "give": (
        "{a} transferred the {item} to {b}.",
        "{a} handed {b} the {item}.",
        "The {item} changed hands from {a} to {b}.",
    ),
    "lend": (
        "The {item} was loaned by {a} to {b}.",
        "{a} temporarily lent the {item} out to {b}.",
        "{b} received the {item} from {a} as a loan.",
    ),
    "move": (
        "{a} brought the {item} from the {src} into the {dst}.",
        "The {item} changed location from the {src} to the {dst} because of {a}.",
        "{a} shifted the {item} out of the {src} and into the {dst}.",
    ),
    "sell": (
        "{b} acquired the {item} from {a} by paying the {payment}.",
        "{a} transferred the {item} to {b} in return for the {payment}.",
        "{b} gave {a} the {payment} in exchange for the {item}.",
    ),
}


@dataclass(frozen=True, slots=True)
class DeltaFrame:
    primary_subject: int
    primary_source: int
    primary_destination: int
    primary_relations: tuple[int, int, int]
    secondary_present: int
    secondary_subject: int
    secondary_source: int
    secondary_destination: int
    secondary_relations: tuple[int, int, int]
    return_obligation: int


@dataclass(frozen=True, slots=True)
class DeltaExample:
    text: str
    frame: DeltaFrame
    family: str
    slots: tuple[tuple[str, str], ...]


def _word_position(text: str, atom: str) -> int | None:
    match = re.search(rf"(?<![A-Za-z0-9_]){re.escape(atom)}(?![A-Za-z0-9_])", text, re.I)
    return match.start() if match else None


def _slotize_text(text: str, atoms: tuple[str, ...]) -> tuple[str, tuple[tuple[str, str], ...]]:
    unique = {atom.casefold(): atom.casefold() for atom in atoms}
    ordered = sorted(unique.values(), key=lambda atom: (_word_position(text, atom) or 10**9, atom))
    if len(ordered) > MAX_SLOTS:
        raise ValueError(f"need {len(ordered)} entity slots but max is {MAX_SLOTS}")
    slots = tuple((f"E{i}", atom) for i, atom in enumerate(ordered))
    normalized = text
    for slot, atom in sorted(slots, key=lambda pair: len(pair[1]), reverse=True):
        normalized = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(atom)}(?![A-Za-z0-9_])",
            slot,
            normalized,
            flags=re.I,
        )
    return normalized, slots


def _idx(atom: str, slots: tuple[tuple[str, str], ...]) -> int:
    lookup = {value.casefold(): int(slot[1:]) for slot, value in slots}
    return lookup[atom.casefold()]


def _frame(family: str, *, a: str, b: str, item: str, src: str, dst: str, payment: str,
           slots: tuple[tuple[str, str], ...]) -> DeltaFrame:
    if family == "give":
        return DeltaFrame(
            _idx(item, slots), _idx(a, slots), _idx(b, slots), (1, 1, 0),
            0, NONE_SLOT, NONE_SLOT, NONE_SLOT, (0, 0, 0), 0,
        )
    if family == "lend":
        return DeltaFrame(
            _idx(item, slots), _idx(a, slots), _idx(b, slots), (0, 1, 0),
            0, NONE_SLOT, NONE_SLOT, NONE_SLOT, (0, 0, 0), 1,
        )
    if family == "move":
        return DeltaFrame(
            _idx(item, slots), _idx(src, slots), _idx(dst, slots), (0, 0, 1),
            0, NONE_SLOT, NONE_SLOT, NONE_SLOT, (0, 0, 0), 0,
        )
    if family == "sell":
        return DeltaFrame(
            _idx(item, slots), _idx(a, slots), _idx(b, slots), (1, 1, 0),
            1, _idx(payment, slots), _idx(b, slots), _idx(a, slots), (1, 1, 0), 0,
        )
    raise ValueError(f"unknown family {family}")


def generate_delta_examples(count: int, *, split: str, seed: int = 0) -> tuple[DeltaExample, ...]:
    if split not in {"train", "eval"}:
        raise ValueError("split must be train or eval")
    rng = random.Random(seed)
    if split == "train":
        names, items, rooms, payments, templates = (
            TRAIN_NAMES, TRAIN_ITEMS, TRAIN_ROOMS, TRAIN_PAYMENTS, TRAIN_TEMPLATES
        )
    else:
        names, items, rooms, payments, templates = (
            EVAL_NAMES, EVAL_ITEMS, EVAL_ROOMS, EVAL_PAYMENTS, EVAL_TEMPLATES
        )

    families = ("give", "lend", "move", "sell")
    out: list[DeltaExample] = []
    for index in range(count):
        family = families[index % len(families)]
        a, b = rng.sample(names, 2)
        item = rng.choice(items)
        src, dst = rng.sample(rooms, 2)
        payment = rng.choice(payments)
        rendered = rng.choice(templates[family]).format(
            a=a.title(), b=b.title(), item=item, src=src, dst=dst, payment=payment
        )
        if family in {"give", "lend"}:
            atoms = (a, b, item)
        elif family == "move":
            atoms = (a, item, src, dst)
        else:
            atoms = (a, b, item, payment)
        normalized, slots = _slotize_text(rendered, atoms)
        out.append(
            DeltaExample(
                normalized,
                _frame(family, a=a, b=b, item=item, src=src, dst=dst, payment=payment, slots=slots),
                family,
                slots,
            )
        )
    return tuple(out)


if __name__ == "__main__":
    for x in generate_delta_examples(12, split="eval", seed=9):
        print(x.family, x.text)
        print(x.frame)
        print(x.slots)
