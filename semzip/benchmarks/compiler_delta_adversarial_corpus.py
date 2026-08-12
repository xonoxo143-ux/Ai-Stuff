from __future__ import annotations

import compiler_delta_corpus as base
from compiler_delta_contrast_corpus import CONTRAST_TEMPLATES


ADVERSARIAL_EVAL_TEMPLATES = {
    "give": (
        "By the end of the exchange, the {item} belonged to {b}, not {a}.",
        "{b} ended up owning and holding the {item} after {a} transferred it outright.",
        "Without expecting it back, {a} placed the {item} in {b}'s hands and made it {b}'s property.",
        "The {item}, formerly {a}'s, became {b}'s to keep.",
        "Ownership as well as possession of the {item} passed from {a} over to {b}.",
        "{a} relinquished the {item} in favor of {b}, who became both owner and holder.",
        "What had been {a}'s {item} was now owned and possessed by {b}.",
        "{b} took permanent ownership of the {item} from {a} and kept physical possession too.",
        "The transfer left {a} with neither ownership nor possession of the {item}; both went to {b}.",
        "After receiving the {item} from {a}, {b} was free to keep it as their own.",
        "Title to the {item} and physical possession both moved away from {a} and onto {b}.",
        "{a}'s permanent transfer made {b} the new owner and possessor of the {item}.",
        "The {item} changed hands for good: {a} gave it up and {b} became its owner.",
        "There was no return expected when {a} transferred the {item} permanently to {b}.",
        "From that point onward, {b}, rather than {a}, owned and possessed the {item}.",
        "{a} conveyed the {item} outright to {b}; possession and ownership followed together.",
    ),
    "lend": (
        "Although {b} now held the {item}, it still belonged to {a} and had to be returned.",
        "{a} remained the owner while {b} became only the temporary possessor of the {item}.",
        "The {item} stayed {a}'s property even as {b} took temporary custody of it.",
        "{b}'s possession of the {item} was temporary; ownership never left {a}.",
        "{a} let {b} have physical control of the {item} for a while but retained title.",
        "Possession passed to {b}, not ownership, and {b} owed the {item} back to {a}.",
        "{b} was entrusted with {a}'s {item} on the condition that it later return to {a}.",
        "The arrangement made {b} the holder of the {item} while leaving {a} as its owner.",
        "{a} temporarily surrendered possession of the {item} to {b} without surrendering ownership.",
        "Until it was returned, {b} possessed the {item}; throughout, {a} still owned it.",
        "{b} acquired temporary custody of the {item} from {a}, together with an obligation to give it back.",
        "No ownership transfer occurred when {a} put the {item} in {b}'s temporary possession.",
        "The {item} was on loan from {a} to {b}: {b} held it, {a} owned it.",
        "{b} could use the {item} for now, but it remained {a}'s and was due back.",
        "{a} retained title to the {item} while allowing {b} to possess it temporarily.",
        "Temporary possession moved from {a} to {b}; ownership stayed put and return was required.",
    ),
    "move": (
        "The {item} ended up at the {dst} instead of the {src} after {a} relocated it.",
        "{a}'s move left the {item} in the {dst}, having taken it out of the {src}.",
        "Where the {item} had been in the {src}, it was now in the {dst} because of {a}.",
        "{a} changed the {item}'s location from the {src} over to the {dst}.",
        "The {item}'s former location was the {src}; its new location was the {dst} after {a} moved it.",
        "From the {src}, {a} conveyed the {item} into the {dst}.",
        "{a} removed the {item} from the {src} and deposited it in the {dst}.",
        "The relocation performed by {a} took the {item} out of the {src} and into the {dst}.",
        "Once {a} was done, the {item} was at the {dst} rather than the {src}.",
        "{a} shifted the {item}'s whereabouts: {src} before, {dst} afterward.",
        "The {item} traveled from the {src} to the {dst} under {a}'s action.",
        "{a} transferred the {item} spatially, starting at the {src} and finishing at the {dst}.",
        "A relocation by {a} changed only where the {item} was: from {src} to {dst}.",
        "{a} took the {item} away from the {src}; it came to rest in the {dst}.",
        "The {dst} became the {item}'s location after {a} moved it from the {src}.",
        "After leaving the {src} with {a}, the {item} arrived in the {dst}.",
    ),
    "sell": (
        "{b} became owner and possessor of the {item}; in return, {a} became owner and possessor of the {payment}.",
        "The bargain swapped the {item} from {a} to {b} and the {payment} from {b} to {a}.",
        "{b} acquired the {item} outright from {a}, compensating {a} with the {payment}.",
        "After the transaction, {b} owned and held the {item}, while {a} owned and held the {payment}.",
        "{a} transferred the {item} permanently to {b} against {b}'s transfer of the {payment} to {a}.",
        "Two reciprocal transfers completed the deal: {item} from {a} to {b}, {payment} from {b} to {a}.",
        "The {item} changed hands to {b} as the {payment} changed hands to {a}.",
        "In exchange for the {payment}, {a} gave up ownership and possession of the {item} to {b}.",
        "{b}'s purchase left {b} with the {item} and {a} with the {payment}, each as owner and possessor.",
        "The completed sale moved title and possession of the {item} to {b} and of the {payment} to {a}.",
        "{a} disposed of the {item} to {b}; consideration flowed back as the {payment}.",
        "{b} obtained the {item} from {a} permanently, and {a} obtained the {payment} from {b} permanently.",
        "Ownership and possession crossed in opposite directions: {item} toward {b}, {payment} toward {a}.",
        "The deal made {b} the new holder-owner of the {item} and {a} the new holder-owner of the {payment}.",
        "{a} and {b} exchanged assets, with the {item} going to {b} and the {payment} going to {a}.",
        "Payment and goods moved reciprocally: {b} surrendered the {payment}, while {a} surrendered the {item}.",
    ),
}


def generate_adversarial_examples(count: int, *, split: str, seed: int = 0):
    if split == "train":
        previous = base.TRAIN_TEMPLATES
        try:
            base.TRAIN_TEMPLATES = CONTRAST_TEMPLATES
            return base.generate_delta_examples(count, split="train", seed=seed)
        finally:
            base.TRAIN_TEMPLATES = previous

    previous = base.EVAL_TEMPLATES
    try:
        base.EVAL_TEMPLATES = ADVERSARIAL_EVAL_TEMPLATES
        return base.generate_delta_examples(count, split="eval", seed=seed)
    finally:
        base.EVAL_TEMPLATES = previous


if __name__ == "__main__":
    for example in generate_adversarial_examples(16, split="eval", seed=7):
        print(example.family, example.text)
