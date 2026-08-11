from __future__ import annotations

from dataclasses import dataclass
import json
import re

from compiler_corpus import CompilerExample, generate_examples


SLOT_SYSTEM_PROMPT = """Compile the statement into SemVM JSON using ONLY the supplied entity slots.
Return only one JSON object with an instructions list.
K0(subject, relation, value) sets a value.
K1(subject, relation, before, after) changes a value.
K2(subject, relation, value) requires a value before acting.
K3(subject, relation) clears a value.
A gift changes owner and possessor from giver to recipient.
A loan keeps owner unchanged, changes possessor lender to borrower, and activates a return obligation.
A sale exchanges owner and possessor of the goods seller to buyer and of the payment buyer to seller.
Moving changes only location.
Never reproduce names, objects, payments, or locations. Refer to them by E0, E1, E2, etc. exactly as listed."""


@dataclass(frozen=True, slots=True)
class SlotExample:
    text: str
    target: str
    family: str
    slots: tuple[tuple[str, str], ...]


def _word_position(text: str, atom: str) -> int | None:
    match = re.search(rf"(?<![A-Za-z0-9_]){re.escape(atom)}(?![A-Za-z0-9_])", text, re.I)
    return match.start() if match else None


def _candidate_atoms(example: CompilerExample) -> tuple[str, ...]:
    data = json.loads(example.target)
    found: set[str] = set()
    for ins in data["instructions"]:
        for arg in ins["args"]:
            pieces = arg.split(":")
            for piece in pieces:
                if _word_position(example.text, piece) is not None:
                    found.add(piece.casefold())
    return tuple(
        sorted(
            found,
            key=lambda atom: (_word_position(example.text, atom) or 10**9, atom),
        )
    )


def slotize(example: CompilerExample) -> SlotExample:
    atoms = _candidate_atoms(example)
    mapping = {atom: f"E{i}" for i, atom in enumerate(atoms)}
    data = json.loads(example.target)
    for ins in data["instructions"]:
        new_args = []
        for arg in ins["args"]:
            parts = arg.split(":")
            parts = [mapping.get(part.casefold(), part) for part in parts]
            new_args.append(":".join(parts))
        ins["args"] = new_args
    table = "; ".join(f"{slot}={atom}" for atom, slot in mapping.items())
    prompt = f"Entities: {table}\nStatement: {example.text}"
    return SlotExample(
        prompt,
        json.dumps(data, separators=(",", ":")),
        example.family,
        tuple((slot, atom) for atom, slot in mapping.items()),
    )


def generate_slot_examples(count: int, *, split: str, seed: int = 0) -> tuple[SlotExample, ...]:
    return tuple(slotize(x) for x in generate_examples(count, split=split, seed=seed))


def resolve_slots(payload: str, slots: tuple[tuple[str, str], ...]) -> str:
    mapping = dict(slots)
    data = json.loads(payload)
    for ins in data.get("instructions", []):
        args = ins.get("args", [])
        resolved = []
        for arg in args:
            parts = str(arg).split(":")
            parts = [mapping.get(part, part) for part in parts]
            resolved.append(":".join(parts))
        ins["args"] = resolved
    return json.dumps(data, separators=(",", ":"))


if __name__ == "__main__":
    for x in generate_slot_examples(8, split="eval", seed=3):
        print(x.family, x.text)
        print(x.target)
        print(x.slots)
