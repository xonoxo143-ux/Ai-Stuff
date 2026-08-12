from __future__ import annotations

from dataclasses import dataclass
import random

from compiler_delta_corpus import DeltaExample, DeltaFrame, NONE_SLOT
from compiler_mention_corpus import (
    EVAL_ITEMS,
    EVAL_NAMES,
    EVAL_PAYMENTS,
    EVAL_ROOMS,
    TRAIN_ITEMS,
    TRAIN_NAMES,
    TRAIN_PAYMENTS,
    TRAIN_ROOMS,
    TEMPLATES,
)
from semzip.vm_mentions import slotize_mentions


@dataclass(frozen=True, slots=True)
class RawSemanticExample:
    raw_text: str
    spans: tuple[tuple[int, int], ...]
    mentions: tuple[str, ...]
    family: str
    slotted: DeltaExample


def _render(template: str, values: dict[str, str]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Render placeholders while preserving exact character span for every argument."""

    # Build the result by parsing known placeholders, avoiding fragile substring search
    # when one value happens to occur inside another.
    text_parts: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    i = 0
    while i < len(template):
        if template[i] == "{":
            end = template.index("}", i)
            key = template[i + 1 : end]
            value = values[key]
            text_parts.append(value)
            spans[key] = (cursor, cursor + len(value))
            cursor += len(value)
            i = end + 1
        else:
            text_parts.append(template[i])
            cursor += 1
            i += 1
    return "".join(text_parts), spans


def _make_example(family: str, template: str, values: dict[str, str]) -> RawSemanticExample:
    raw_text, by_key = _render(template, values)

    if family in {"give", "lend"}:
        semantic_keys = ("a", "b", "item")
    elif family == "move":
        # The mover is intentionally kept as a detected entity even though the current
        # world-delta target changes only the object's location.
        semantic_keys = ("a", "item", "src", "dst")
    elif family == "sell":
        semantic_keys = ("a", "b", "item", "payment")
    else:
        raise ValueError(family)

    ordered_keys = tuple(sorted(semantic_keys, key=lambda key: by_key[key]))
    spans = tuple(by_key[key] for key in ordered_keys)
    mentions = tuple(values[key] for key in ordered_keys)
    pointer = {key: ordered_keys.index(key) for key in ordered_keys}

    slotted_text = slotize_mentions(raw_text, spans).text
    slots = tuple((f"E{i}", mention) for i, mention in enumerate(mentions))

    if family == "give":
        frame = DeltaFrame(
            primary_subject=pointer["item"],
            primary_source=pointer["a"],
            primary_destination=pointer["b"],
            primary_relations=(1, 1, 0),
        )
    elif family == "lend":
        frame = DeltaFrame(
            primary_subject=pointer["item"],
            primary_source=pointer["a"],
            primary_destination=pointer["b"],
            primary_relations=(0, 1, 0),
            return_obligation=1,
        )
    elif family == "move":
        frame = DeltaFrame(
            primary_subject=pointer["item"],
            primary_source=pointer["src"],
            primary_destination=pointer["dst"],
            primary_relations=(0, 0, 1),
        )
    else:  # sell
        frame = DeltaFrame(
            primary_subject=pointer["item"],
            primary_source=pointer["a"],
            primary_destination=pointer["b"],
            primary_relations=(1, 1, 0),
            secondary_present=1,
            secondary_subject=pointer["payment"],
            secondary_source=pointer["b"],
            secondary_destination=pointer["a"],
            secondary_relations=(1, 1, 0),
        )

    return RawSemanticExample(
        raw_text=raw_text,
        spans=spans,
        mentions=mentions,
        family=family,
        slotted=DeltaExample(slotted_text, frame, family, slots),
    )


def generate_raw_semantic_examples(count: int, *, split: str, seed: int = 0):
    if split not in {"train", "eval"}:
        raise ValueError("split must be train or eval")
    rng = random.Random(seed)
    if split == "train":
        names, items, rooms, payments = TRAIN_NAMES, TRAIN_ITEMS, TRAIN_ROOMS, TRAIN_PAYMENTS
    else:
        names, items, rooms, payments = EVAL_NAMES, EVAL_ITEMS, EVAL_ROOMS, EVAL_PAYMENTS

    families = ("give", "lend", "move", "sell")
    result = []
    for index in range(count):
        family = families[index % len(families)]
        a, b = rng.sample(names, 2)
        src, dst = rng.sample(rooms, 2)
        values = {
            "a": a,
            "b": b,
            "item": rng.choice(items),
            "src": src,
            "dst": dst,
            "payment": rng.choice(payments),
        }
        template = rng.choice(TEMPLATES[family])
        result.append(_make_example(family, template, values))
    return tuple(result)


def generate_slotted_semantic_examples(count: int, *, split: str, seed: int = 0):
    return tuple(
        example.slotted
        for example in generate_raw_semantic_examples(count, split=split, seed=seed)
    )


if __name__ == "__main__":
    for example in generate_raw_semantic_examples(8, split="eval", seed=9):
        print(example.family)
        print(" RAW   ", example.raw_text)
        print(" SPANS ", list(zip(example.spans, example.mentions)))
        print(" SLOTTED", example.slotted.text)
        print(" FRAME  ", example.slotted.frame)
