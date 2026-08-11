from __future__ import annotations

from dataclasses import dataclass
import random


TRAIN_NAMES = (
    "alice", "bob", "carol", "dave", "emma", "frank", "grace", "henry",
    "maya chen", "noah reed",
)
EVAL_NAMES = (
    "quinn", "zara", "omar", "priya", "yuki", "mateo", "lena park", "theo james",
)
TRAIN_ITEMS = (
    "book", "brass key", "blue cup", "old bicycle", "silver ring",
    "sealed parcel", "desk lamp", "film camera",
)
EVAL_ITEMS = (
    "violin", "paper lantern", "drawing tablet", "bike helmet",
    "spiral notebook", "wrist watch", "antique telescope", "wooden box",
)
TRAIN_ROOMS = (
    "kitchen", "back garage", "main office", "rose garden", "dusty attic", "front hall",
)
EVAL_ROOMS = (
    "wine cellar", "art studio", "front porch", "repair workshop", "town library", "guest bedroom",
)
TRAIN_PAYMENTS = ("coin", "blue token", "paper voucher", "train ticket")
EVAL_PAYMENTS = ("store credit", "red coupon", "bank note", "small gem")


TEMPLATES = {
    "give": (
        "Yesterday {a} quietly gave {b} the {item} beside the window.",
        "Near the doorway, {b} received the {item} from {a} after lunch.",
        "Although the radio was playing, {a} handed the {item} to {b}.",
    ),
    "lend": (
        "During the afternoon, {a} lent {b} the {item} beside the table.",
        "After the rain stopped, {b} borrowed the {item} from {a} near the shelf.",
        "At the station, {a} let {b} borrow the {item} until tomorrow.",
    ),
    "move": (
        "Before dinner, {a} carried the {item} from the {src} to the {dst}.",
        "While the television played, the {item} went from the {src} to the {dst} when {a} moved it.",
        "After checking the clock, {a} relocated the {item} from the {src} into the {dst}.",
    ),
    "sell": (
        "At the crowded market, {a} sold {b} the {item} for the {payment}.",
        "During the morning, {b} bought the {item} from {a} with the {payment} near the fountain.",
        "Beside the empty cart, {b} paid {a} the {payment} and received the {item}.",
    ),
}


@dataclass(frozen=True, slots=True)
class MentionExample:
    text: str
    spans: tuple[tuple[int, int], ...]
    mentions: tuple[str, ...]
    family: str


def _render(template: str, values: dict[str, str], semantic_keys: tuple[str, ...]) -> MentionExample:
    # Render with unique sentinels first so exact semantic spans can be recovered even
    # when ordinary distractor nouns appear elsewhere in the sentence.
    marked = template
    sentinels = {}
    for index, key in enumerate(values):
        sentinel = f"__ARG{index}__"
        sentinels[key] = sentinel
        marked = marked.replace("{" + key + "}", sentinel)

    text = marked
    for key, sentinel in sentinels.items():
        text = text.replace(sentinel, values[key])

    spans = []
    mentions = []
    cursor_by_value: dict[str, int] = {}
    for key in semantic_keys:
        value = values[key]
        # Semantic values in each generated example are sampled to be distinct.
        start = text.find(value, cursor_by_value.get(value, 0))
        if start < 0:
            raise RuntimeError(f"could not recover semantic span for {value!r}")
        end = start + len(value)
        cursor_by_value[value] = end
        spans.append((start, end))
        mentions.append(value)

    order = sorted(range(len(spans)), key=lambda i: spans[i])
    return MentionExample(
        text=text,
        spans=tuple(spans[i] for i in order),
        mentions=tuple(mentions[i] for i in order),
        family="",
    )


def generate_mention_examples(count: int, *, split: str, seed: int = 0):
    if split not in {"train", "eval"}:
        raise ValueError("split must be train or eval")
    rng = random.Random(seed)
    if split == "train":
        names, items, rooms, payments = TRAIN_NAMES, TRAIN_ITEMS, TRAIN_ROOMS, TRAIN_PAYMENTS
    else:
        names, items, rooms, payments = EVAL_NAMES, EVAL_ITEMS, EVAL_ROOMS, EVAL_PAYMENTS

    families = ("give", "lend", "move", "sell")
    out = []
    for index in range(count):
        family = families[index % len(families)]
        a, b = rng.sample(names, 2)
        item = rng.choice(items)
        src, dst = rng.sample(rooms, 2)
        payment = rng.choice(payments)
        values = {"a": a, "b": b, "item": item, "src": src, "dst": dst, "payment": payment}
        template = rng.choice(TEMPLATES[family])
        if family in {"give", "lend"}:
            keys = ("a", "b", "item")
        elif family == "move":
            keys = ("a", "item", "src", "dst")
        else:
            keys = ("a", "b", "item", "payment")
        rendered = _render(template, values, keys)
        out.append(MentionExample(rendered.text, rendered.spans, rendered.mentions, family))
    return tuple(out)


if __name__ == "__main__":
    for example in generate_mention_examples(8, split="eval", seed=3):
        print(example.family, example.text)
        print(list(zip(example.spans, example.mentions)))
