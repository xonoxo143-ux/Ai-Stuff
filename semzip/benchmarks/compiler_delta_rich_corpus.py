from __future__ import annotations

import compiler_delta_corpus as base


RICH_TRAIN_TEMPLATES = {
    "give": (
        "{a} gave {b} the {item}.",
        "{b} received the {item} from {a}.",
        "The {item} was given to {b} by {a}.",
        "{a} handed the {item} to {b}.",
        "{a} passed the {item} to {b}.",
        "{b} was given the {item} by {a}.",
        "{a} passed ownership of the {item} over to {b}.",
        "{b} became the owner and holder of the {item} after {a} handed it over.",
        "The {item} passed from {a}'s ownership and possession into {b}'s.",
        "{a} made the {item} {b}'s and handed it over.",
        "After {a} handed over the {item}, {b} owned and possessed it.",
        "{a} surrendered the {item} permanently to {b}.",
    ),
    "lend": (
        "{a} lent {b} the {item}.",
        "{b} borrowed the {item} from {a}.",
        "The {item} was lent to {b} by {a}.",
        "{a} loaned the {item} to {b}.",
        "{a} let {b} borrow the {item}.",
        "{b} took the {item} on loan from {a}.",
        "{a} kept ownership of the {item} but let {b} possess it temporarily.",
        "{b} temporarily took possession of {a}'s {item} and owed its return.",
        "The {item} remained {a}'s property while {b} held it on loan.",
        "{a} put the {item} in {b}'s possession only until it had to be returned.",
        "{b} held the {item} for a while, but {a} still owned it and expected it back.",
        "Ownership stayed with {a}; possession of the {item} moved to {b} until return.",
    ),
    "move": (
        "{a} moved the {item} from the {src} to the {dst}.",
        "{a} carried the {item} from the {src} to the {dst}.",
        "{a} relocated the {item} from the {src} to the {dst}.",
        "The {item} went from the {src} to the {dst} when {a} moved it.",
        "{a} took the {item} from the {src} to the {dst}.",
        "The {item} was moved from the {src} to the {dst} by {a}.",
        "{a} removed the {item} from the {src} and placed it in the {dst}.",
        "The {item}'s location changed from the {src} to the {dst} because {a} moved it.",
        "{a} carried the {item} out of the {src} and put it into the {dst}.",
        "The {item} ended up in the {dst} after {a} took it from the {src}.",
    ),
    "sell": (
        "{a} sold {b} the {item} for the {payment}.",
        "{b} bought the {item} from {a} with the {payment}.",
        "{b} paid {a} the {payment} and received the {item}.",
        "The {item} was sold by {a} to {b} for the {payment}.",
        "{a} sold the {item} to {b} in exchange for the {payment}.",
        "{b} purchased the {item} from {a} using the {payment}.",
        "{a} handed the {item} to {b}, while {b} handed the {payment} to {a}.",
        "The {item} passed from {a} to {b} as the {payment} passed from {b} to {a}.",
        "{b} became owner of the {item}; in return {a} became owner of the {payment}.",
        "{a} transferred the {item} to {b}, and {b} transferred the {payment} back to {a}.",
        "{b} paid {a} with the {payment}; {a} then made the {item} {b}'s.",
        "Two things changed hands: {a}'s {item} went to {b}, and {b}'s {payment} went to {a}.",
        "{a} and {b} exchanged the {item} and the {payment}, with {b} taking the {item}.",
        "In the deal, {b} received the {item} from {a} and {a} received the {payment} from {b}.",
    ),
}


def generate_rich_delta_examples(count: int, *, split: str, seed: int = 0):
    if split == "eval":
        # Keep the exact same held-out evaluation distribution as the baseline.
        return base.generate_delta_examples(count, split=split, seed=seed)

    previous = base.TRAIN_TEMPLATES
    try:
        base.TRAIN_TEMPLATES = RICH_TRAIN_TEMPLATES
        return base.generate_delta_examples(count, split=split, seed=seed)
    finally:
        base.TRAIN_TEMPLATES = previous


if __name__ == "__main__":
    for x in generate_rich_delta_examples(16, split="train", seed=23):
        print(x.family, x.text, x.frame)
