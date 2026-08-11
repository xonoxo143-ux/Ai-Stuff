from __future__ import annotations

from dataclasses import dataclass
import json
import random

from semzip.vm_compile import give, lend, move, sell
from semzip.vm_kernel import Program


SYSTEM_PROMPT = """Compile the user's English statement into SemVM JSON. Return only one JSON object with an instructions list.
K0(subject, relation, value) sets a value.
K1(subject, relation, before, after) changes a value.
K2(subject, relation, value) requires a value before acting.
K3(subject, relation) clears a value.
A gift changes both owner and possessor from giver to recipient.
A loan keeps ownership with the lender, changes possession to the borrower, and sets obligation:return:<item>:<borrower>:<lender> status active.
A sale changes owner and possessor of the goods seller to buyer and changes owner and possessor of the payment buyer to seller.
Moving changes only location. Use lowercase atoms from the sentence."""


@dataclass(frozen=True, slots=True)
class CompilerExample:
    text: str
    target: str
    family: str


def program_json(program: Program) -> str:
    return json.dumps(
        {
            "instructions": [
                {"opcode": ins.opcode, "args": list(ins.args)}
                for ins in program.instructions
            ]
        },
        separators=(",", ":"),
    )


TRAIN_NAMES = ("alice", "bob", "carol", "dave", "emma", "frank", "grace", "henry")
EVAL_NAMES = ("quinn", "zara", "omar", "priya", "yuki", "mateo")
TRAIN_ITEMS = ("book", "key", "cup", "bike", "ring", "parcel", "lamp", "camera")
EVAL_ITEMS = ("violin", "lantern", "tablet", "helmet", "notebook", "watch")
TRAIN_ROOMS = ("kitchen", "garage", "office", "garden", "attic", "hall")
EVAL_ROOMS = ("cellar", "studio", "porch", "workshop", "library", "bedroom")
TRAIN_PAYMENTS = ("coin", "token", "voucher", "ticket")
EVAL_PAYMENTS = ("credit", "coupon", "note", "gem")

TRAIN_TEMPLATES = {
    "give": (
        "{a} gave {b} the {item}.",
        "{a} gave the {item} to {b}.",
        "{a} gifted {b} the {item}.",
        "{b} got the {item} as a gift from {a}.",
    ),
    "lend": (
        "{a} lent {b} the {item}.",
        "{a} loaned the {item} to {b}.",
        "{a} let {b} borrow the {item}.",
    ),
    "move": (
        "{a} moved the {item} from the {src} to the {dst}.",
        "{a} carried the {item} from the {src} to the {dst}.",
        "{a} relocated the {item} from the {src} to the {dst}.",
    ),
    "sell": (
        "{a} sold {b} the {item} for the {payment}.",
        "{a} sold the {item} to {b} for the {payment}.",
        "{a} sold the {item} to {b} in exchange for the {payment}.",
    ),
}

EVAL_TEMPLATES = {
    "give": (
        "{b} received the {item} from {a}.",
        "The {item} was given to {b} by {a}.",
    ),
    "lend": (
        "{b} borrowed the {item} from {a}.",
        "The {item} was lent to {b} by {a}.",
    ),
    "move": (
        "{a} took the {item} from the {src} to the {dst}.",
        "The {item} went from the {src} to the {dst} when {a} moved it.",
    ),
    "sell": (
        "{b} bought the {item} from {a} with the {payment}.",
        "{b} paid {a} the {payment} and received the {item}.",
    ),
}


def generate_examples(count: int, *, split: str, seed: int = 0) -> tuple[CompilerExample, ...]:
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
    out: list[CompilerExample] = []
    for index in range(count):
        family = families[index % len(families)]
        a, b = rng.sample(names, 2)
        item = rng.choice(items)
        src, dst = rng.sample(rooms, 2)
        payment_choices = tuple(x for x in payments if x != item)
        payment = rng.choice(payment_choices)
        text = rng.choice(templates[family]).format(
            a=a.title(), b=b.title(), item=item, src=src, dst=dst, payment=payment
        )
        if family == "give":
            program = give(a, b, item)
        elif family == "lend":
            program = lend(a, b, item)
        elif family == "move":
            program = move(a, item, src, dst)
        else:
            program = sell(a, b, item, payment)
        out.append(CompilerExample(text, program_json(program), family))
    return tuple(out)


if __name__ == "__main__":
    for example in generate_examples(8, split="eval", seed=1):
        print(example.family, example.text)
        print(example.target)
