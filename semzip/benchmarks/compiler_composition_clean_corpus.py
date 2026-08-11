from __future__ import annotations

import random

from compiler_delta_corpus import DeltaExample, DeltaFrame, NONE_SLOT


SINGLE = {
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

RECIPROCAL = {
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

SLOTS3 = (("E0", "object"), ("E1", "source"), ("E2", "destination"))
SLOTS4 = SLOTS3 + (("E3", "other_object"),)


def _frame(relation: str, reciprocal: bool, *, combined: bool = False) -> DeltaFrame:
    bits = (1, 1, 0) if combined else ((1, 0, 0) if relation == "owner" else (0, 1, 0))
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


def generate_clean_composition_examples(count: int, *, split: str, seed: int = 0):
    """Hold out semantic conjunction without holding out its atomic language.

    Training examples contain exactly one relation family at a time. Evaluation
    concatenates two already-seen atomic clause forms with the same arguments.
    Therefore the only novel requirement is to UNION their semantics.
    """

    rng = random.Random(seed)
    out = []
    if split == "train":
        kinds = (("owner", False), ("possessor", False), ("owner", True), ("possessor", True))
        for i in range(count):
            relation, reciprocal = kinds[i % len(kinds)]
            templates = RECIPROCAL[relation] if reciprocal else SINGLE[relation]
            text = rng.choice(templates)
            family = f"atomic_{relation}_{'reciprocal' if reciprocal else 'single'}"
            out.append(DeltaExample(text, _frame(relation, reciprocal), family, SLOTS4 if reciprocal else SLOTS3))
    elif split == "eval":
        for i in range(count):
            reciprocal = bool(i % 2)
            owner_templates = RECIPROCAL["owner"] if reciprocal else SINGLE["owner"]
            possessor_templates = RECIPROCAL["possessor"] if reciprocal else SINGLE["possessor"]
            # Both clauses are individually drawn from exact training template sets.
            owner_clause = rng.choice(owner_templates)
            possessor_clause = rng.choice(possessor_templates)
            text = owner_clause + " " + possessor_clause
            family = "clean_composed_reciprocal" if reciprocal else "clean_composed_single"
            out.append(DeltaExample(text, _frame("owner", reciprocal, combined=True), family, SLOTS4 if reciprocal else SLOTS3))
    else:
        raise ValueError("split must be train or eval")
    return tuple(out)


if __name__ == "__main__":
    print("TRAIN atoms:")
    for x in generate_clean_composition_examples(8, split="train", seed=1):
        print(x.family, x.text)
    print("\nEVAL unions of those same atom types:")
    for x in generate_clean_composition_examples(4, split="eval", seed=2):
        print(x.family, x.text)
