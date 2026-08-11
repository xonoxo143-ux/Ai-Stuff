from __future__ import annotations

import json

from semzip.meaning import Meaning
from semzip.schema import validate_meaning
from semzip.story import MiniWorldInterpreter, UnsupportedStorySentence


def change(
    subject: str,
    dimension: str,
    after: str,
    *,
    actor: str | None = None,
) -> Meaning:
    roles = {"subject": subject, "dimension": dimension, "after": after}
    if actor is not None:
        roles["actor"] = actor
    return Meaning.build("CHANGE", roles)


CASES = [
    (
        "John might open the door.",
        Meaning.build(
            "POSSIBLE",
            {"content": change("door", "open", "true", actor="john")},
        ),
    ),
    (
        "Mary believes Bob might own the key.",
        Meaning.build(
            "BELIEVE",
            {
                "holder": "mary",
                "content": Meaning.build(
                    "POSSIBLE",
                    {
                        "content": Meaning.build(
                            "STATE",
                            {"subject": "key", "dimension": "owner", "value": "bob"},
                        )
                    },
                ),
            },
        ),
    ),
    (
        "If John opens the door, Mary will leave.",
        Meaning.build(
            "CONDITIONAL",
            {
                "if": change("door", "open", "true", actor="john"),
                "then": change("mary", "location", "outside", actor="mary"),
            },
        ),
    ),
]


def main() -> None:
    parser = MiniWorldInterpreter()
    rows = []
    for surface, intended in CASES:
        validate_meaning(intended)
        try:
            parser.parse(parser._normalize(surface))
            parsed = True
        except UnsupportedStorySentence:
            parsed = False
        rows.append(
            {
                "surface": surface,
                "representable_by_current_ir": True,
                "parsed_by_current_surface_grammar": parsed,
                "intended_operator": intended.operator,
            }
        )
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
