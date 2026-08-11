from __future__ import annotations

import json

from semzip.meaning import Meaning
from semzip.metrics import analyze, repeated_structures
from semzip.molecules import borrow, buy, give, lend, receive, sell
from semzip.multilingual import MiniTransferAdapter
from semzip.query import WorldQueryEngine
from semzip.reference import quantify
from semzip.schema import validate_meaning
from semzip.story import MiniWorldInterpreter

STORY = [
    "John owned a red key.",
    "John gave the key to Mary.",
    "Mary put it in the kitchen.",
    "Bob believes the key is still with John.",
    "Later, Mary moved the key to the garage.",
    "John does not know where the key is.",
]


def main() -> None:
    interpreter = MiniWorldInterpreter()
    for sentence in STORY:
        interpreter.feed(sentence)
    query = WorldQueryEngine(interpreter.world)

    def ask(operator: str, **roles: str):
        return query.answer(Meaning.build(operator, roles)).value

    world_gate = {
        "owner": ask("QUERY_VALUE", subject="key", dimension="owner"),
        "location": ask("QUERY_VALUE", subject="key", dimension="location"),
        "previous_location": ask(
            "QUERY_PREVIOUS_VALUE", subject="key", dimension="location"
        ),
        "bob_believes_owner": ask(
            "QUERY_BELIEF", holder="bob", subject="key", dimension="owner"
        ),
        "bob_belief_true": ask(
            "QUERY_BELIEF_TRUE", holder="bob", subject="key", dimension="owner"
        ),
        "john_knows_location": ask(
            "QUERY_KNOWS_VALUE", holder="john", subject="key", dimension="location"
        ),
    }

    meanings = [
        give("john", "mary", "book"),
        receive("mary", "book", "john"),
        buy("mary", "book", "john", "cash"),
        sell("john", "mary", "book", "cash"),
        borrow("mary", "book", "john"),
        lend("john", "mary", "book"),
    ]
    compression = analyze(meanings).to_dict()
    recurring = repeated_structures(meanings)

    adapter = MiniTransferAdapter()
    en = adapter.encode("John gave Mary the book.")
    es = adapter.encode("John le dio el libro a Mary.")

    exact_three_keys = quantify("key", "EXACT", count=3)
    validate_meaning(exact_three_keys)

    result = {
        "world_gate": world_gate,
        "compression": compression,
        "top_repeated_operator": recurring[0].signature[0] if recurring else None,
        "cross_language_equal": en == es,
        "cross_language_hash": en.semantic_hash(),
        "quantity_example": exact_three_keys.to_dict(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
