from __future__ import annotations

import random

from compiler_delta_corpus import DeltaExample, DeltaFrame, NONE_SLOT


SINGLE_TEMPLATES = {
    "owner": (
        "Ownership of E0 changed from E1 to E2.",
        "E0's owner changed from E1 to E2.",
        "The ownership relation for E0 moved from E1 to E2.",
        "E1 stopped owning E0 and E2 became its owner.",
    ),
    "possessor": (
        "Possession of E0 changed from E1 to E2.",
        "E0's possessor changed from E1 to E2.",
        "The possession relation for E0 moved from E1 to E2.",
        "E1 stopped possessing E0 and E2 became its possessor.",
    ),
}

RECIPROCAL_TEMPLATES = {
    "owner": (
        "Ownership of E0 moved from E1 to E2 while ownership of E3 moved from E2 to E1.",
        "E1 transferred ownership of E0 to E2, and E2 transferred ownership of E3 to E1.",
        "E0 changed owner from E1 to E2 as E3 changed owner from E2 to E1.",
    ),
    "possessor": (
        "Possession of E0 moved from E1 to E2 while possession of E3 moved from E2 to E1.",
        "E1 transferred possession of E0 to E2, and E2 transferred possession of E3 to E1.",
        "E0 changed possessor from E1 to E2 as E3 changed possessor from E2 to E1.",
    ),
}

EVAL_SINGLE = (
    "Ownership and possession of E0 both changed from E1 to E2.",
    "E1 stopped owning and possessing E0; E2 became both owner and possessor.",
    "Both ownership and possession of E0 moved from E1 to E2.",
    "E0 changed from E1 to E2 in both owner and possessor relations.",
)

EVAL_RECIPROCAL = (
    "Ownership and possession of E0 moved from E1 to E2 while both relations for E3 moved from E2 to E1.",
    "E1 transferred both ownership and possession of E0 to E2, while E2 did the same with E3 to E1.",
    "E0 changed owner and possessor from E1 to E2 as E3 changed owner and possessor from E2 to E1.",
    "E1 gave up ownership and possession of E0 to E2; E2 gave up ownership and possession of E3 to E1.",
)

SLOTS3 = (("E0", "object"), ("E1", "source"), ("E2", "destination"))
SLOTS4 = SLOTS3 + (("E3", "other_object"),)


def _frame(relation: str, reciprocal: bool, combined: bool = False) -> DeltaFrame:
    if combined:
        bits = (1, 1, 0)
    elif relation == "owner":
        bits = (1, 0, 0)
    elif relation == "possessor":
        bits = (0, 1, 0)
    else:
        raise ValueError(relation)
    return DeltaFrame(
        primary_subject=0,
        primary_source=1,
        primary_destination=2,
        primary_relations=bits,
        secondary_present=int(reciprocal),
        secondary_subject=3 if reciprocal else NONE_SLOT,
        secondary_source=2 if reciprocal else NONE_SLOT,
        secondary_destination=1 if reciprocal else NONE_SLOT,
        secondary_relations=bits if reciprocal else (0, 0, 0),
        return_obligation=0,
    )


def generate_composition_examples(count: int, *, split: str, seed: int = 0):
    rng = random.Random(seed)
    out = []
    if split == "train":
        kinds = (
            ("owner", False),
            ("possessor", False),
            ("owner", True),
            ("possessor", True),
        )
        for i in range(count):
            relation, reciprocal = kinds[i % len(kinds)]
            templates = RECIPROCAL_TEMPLATES[relation] if reciprocal else SINGLE_TEMPLATES[relation]
            text = rng.choice(templates)
            family = f"train_{relation}_{'reciprocal' if reciprocal else 'single'}"
            out.append(DeltaExample(text, _frame(relation, reciprocal), family, SLOTS4 if reciprocal else SLOTS3))
    elif split == "eval":
        for i in range(count):
            reciprocal = bool(i % 2)
            templates = EVAL_RECIPROCAL if reciprocal else EVAL_SINGLE
            text = rng.choice(templates)
            family = "heldout_owner_possessor_reciprocal" if reciprocal else "heldout_owner_possessor_single"
            out.append(DeltaExample(text, _frame("owner", reciprocal, combined=True), family, SLOTS4 if reciprocal else SLOTS3))
    else:
        raise ValueError("split must be train or eval")
    return tuple(out)


if __name__ == "__main__":
    print("TRAIN: no owner+possessor examples")
    for x in generate_composition_examples(8, split="train", seed=1):
        print(x.family, x.text, x.frame)
    print("\nEVAL: owner+possessor is an unseen semantic conjunction")
    for x in generate_composition_examples(4, split="eval", seed=2):
        print(x.family, x.text, x.frame)
