from __future__ import annotations

import compiler_delta_corpus as base
from compiler_delta_rich_corpus import RICH_TRAIN_TEMPLATES


CONTRAST_TEMPLATES = dict(RICH_TRAIN_TEMPLATES)

CONTRAST_TEMPLATES["give"] = (
    "{a} gave {b} the {item} permanently.",
    "{b} received the {item} from {a}, and it became {b}'s property.",
    "{a} transferred ownership and possession of the {item} to {b}.",
    "After {a} handed over the {item}, {b} owned it and possessed it.",
    "{a} gave up both ownership and possession of the {item} to {b}.",
    "The {item} stopped belonging to {a} and became {b}'s to keep.",
    "{b} received the {item} from {a} to keep, with ownership transferred.",
    "{a} made the {item} {b}'s and handed it over for good.",
    "The {item} passed from {a} to {b}; {b} was now its owner and holder.",
    "{a} permanently transferred the {item} into {b}'s ownership and possession.",
    "{b} took ownership and possession of the {item} from {a}.",
    "{a} handed {b} the {item} and no return was expected because it now belonged to {b}.",
) + RICH_TRAIN_TEMPLATES["give"]

CONTRAST_TEMPLATES["lend"] = (
    "{b} received the {item} from {a} temporarily and had to give it back.",
    "{a} kept ownership of the {item}; {b} only possessed it temporarily.",
    "{b} received the {item} from {a}, but ownership stayed with {a} and return was expected.",
    "The {item} remained {a}'s property while {b} possessed it for a while.",
    "{a} let {b} hold the {item} temporarily without transferring ownership.",
    "{b} took temporary possession of {a}'s {item} and owed it back to {a}.",
    "Ownership of the {item} stayed with {a}; possession moved to {b} until return.",
    "{a} handed the {item} to {b} only for temporary possession, not ownership.",
    "{b} held the {item} for {a} and was expected to return it.",
    "The {item} was still owned by {a} even though {b} temporarily possessed it.",
    "{b} received temporary custody of the {item} from {a}; it still belonged to {a}.",
    "{a} retained ownership while letting {b} possess the {item} until it was returned.",
) + RICH_TRAIN_TEMPLATES["lend"]


def generate_contrast_examples(count: int, *, split: str, seed: int = 0):
    if split == "eval":
        # Keep the established held-out benchmark unchanged.
        return base.generate_delta_examples(count, split="eval", seed=seed)

    previous = base.TRAIN_TEMPLATES
    try:
        base.TRAIN_TEMPLATES = CONTRAST_TEMPLATES
        return base.generate_delta_examples(count, split="train", seed=seed)
    finally:
        base.TRAIN_TEMPLATES = previous


if __name__ == "__main__":
    for example in generate_contrast_examples(16, split="train", seed=7):
        print(example.family, example.text, example.frame)
