from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_bucket(text: str, buckets: int = 10) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % buckets


def tagged(kind: str, text: str) -> bytes:
    clean = text.strip()
    return f"<|{kind}|>\n{clean}\n<|end|>\n".encode("utf-8")


def load_oasst(path: Path) -> tuple[list[bytes], list[bytes]]:
    messages: dict[str, dict] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("lang") != "en" or row.get("deleted"):
                continue
            if row.get("review_result") is False:
                continue
            messages[row["message_id"]] = row

    train: list[bytes] = []
    valid: list[bytes] = []
    seen: set[str] = set()

    for row in messages.values():
        if row.get("role") != "assistant":
            continue
        if row.get("rank") not in (None, 0):
            continue
        chain = []
        current = row
        ok = True
        while current is not None:
            if current.get("lang") != "en":
                ok = False
                break
            chain.append(current)
            parent_id = current.get("parent_id")
            current = messages.get(parent_id) if parent_id else None
        if not ok:
            continue
        chain.reverse()
        if len(chain) < 2:
            continue
        parts = []
        for item in chain:
            role = "User" if item["role"] == "prompter" else "Assistant"
            parts.append(f"{role}: {item['text'].strip()}")
        text = "\n\n".join(parts)
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        tree_id = str(row.get("message_tree_id") or chain[0]["message_id"])
        target = valid if stable_bucket(tree_id) == 0 else train
        target.append(tagged("dialogue", text))
    return train, valid


def reasoning_records(seed: int, count: int) -> list[bytes]:
    rng = random.Random(seed)
    starts = ["Al", "Bel", "Cor", "Den", "El", "Far", "Gal", "Har", "Ira", "Jon", "Kel", "Lin"]
    ends = ["a", "en", "is", "or", "um", "el", "ar", "on"]
    names = [a + b for a in starts for b in ends]
    objects = ["crates", "tokens", "books", "keys", "cells", "samples"]
    records: list[bytes] = []
    for _ in range(count):
        kind = rng.randrange(4)
        a, b, c = rng.sample(names, 3)
        if kind == 0:
            start = rng.randint(8, 90)
            add = rng.randint(3, 40)
            take = rng.randint(1, min(start + add - 1, 35))
            obj = rng.choice(objects)
            answer = start + add - take

            text = (
                f"Problem: {a} has {start} {obj}, receives {add}, then uses {take}. "
                f"How many remain?\n"
                f"Reasoning: Start with {start}; adding {add} gives {start + add}; "
                f"subtracting {take} gives {answer}.\nAnswer: {answer}."
            )
        elif kind == 1:
            text = (
                f"Facts: {a} is before {b}. {b} is before {c}.\n"
                f"Question: What relation must hold between {a} and {c}?\n"
                f"Reasoning: 'before' is transitive across these facts.\n"
                f"Answer: {a} is before {c}."
            )
        elif kind == 2:
            x = rng.randint(2, 12)
            y = rng.randint(2, 12)
            text = (
                f"Facts: Every {a}-unit contains {x} parts. There are {y} {a}-units.\n"
                f"Question: How many parts are there in total?\n"
                f"Reasoning: Multiply units by parts per unit: {y} x {x} = {x*y}.\n"
                f"Answer: {x*y}."
            )
        else:
            text = (
                f"Evidence A: source one says {a} caused the change.\n"
                f"Evidence B: source two only shows {a} occurred before the change.\n"
                "Question: Is causation established?\n"
                "Reasoning: Temporal order alone does not establish causation, and the sources disagree "
                "about the strength of the claim.\n"
                "Answer: No. Treat causation as uncertain and seek stronger evidence."
            )
        records.append(tagged("reasoning", text))
    return records


def planner_records(seed: int, count: int) -> list[bytes]:
    rng = random.Random(seed)
    nouns = ["storm", "build", "battery", "test", "shipment", "server"]
    modifiers = ["alpha", "beta", "north", "backup", "field", "night", "primary", "trial"]

    actions = [
        "keep a backup ready",
        "run one more verification",
        "avoid making the irreversible change yet",
        "proceed with the reversible step",
    ]
    records: list[bytes] = []
    for _ in range(count):
        subject = f"the {rng.choice(modifiers)} {rng.choice(nouns)}"
        ev = rng.choice([
            f"the latest measurement shifted by {rng.randint(1, 99)} percent",
            f"{rng.randint(2, 9)} independent checks agree",
            f"run {rng.randint(10, 999)} reproduced the result",
            f"only {rng.randint(1, 5)} of {rng.randint(6, 12)} checks are complete",
        ])
        action = rng.choice(actions)
        certainty = rng.choice(["low", "moderate", "high"])
        claim = rng.choice([
            f"{subject} is likely to change soon",
            f"{subject} appears stable for now",
            f"{subject} needs another check before a firm conclusion",
        ])
        plan = (
            "<|plan|>\n"
            f"CLAIM: {claim}\n"
            f"EVIDENCE: {ev}\n"
            f"UNCERTAINTY: {certainty}\n"
            f"ACTION: {action}\n"
            "<|response|>\n"
        )
        variants = [
            f"{claim.capitalize()}. The main evidence is that {ev}. "
            f"My uncertainty is {certainty}, so I would {action}.",
            f"{claim.capitalize()}; {ev}. With {certainty} uncertainty, the practical next step is to {action}.",
            f"Based on the evidence that {ev}, {claim}. Because uncertainty is {certainty}, I would {action}.",
        ]
        records.append(tagged("planner", plan + rng.choice(variants)))
    return records


def fill_budget(records: list[bytes], budget: int, seed: int) -> bytes:
    if not records:
        return b""
    rng = random.Random(seed)
    order = list(range(len(records)))
    out = bytearray()
    while len(out) < budget:
        rng.shuffle(order)
        for index in order:
            out.extend(records[index])
            if len(out) >= budget:
                return bytes(out[:budget])
    return bytes(out[:budget])


def build_split(
    *,
    wiki: bytes,
    dialogue: list[bytes],
    reasoning: list[bytes],
    planner: list[bytes],
    budgets: dict[str, int],
    seed: int,
) -> bytes:
    pieces = [
        tagged("prose", wiki[: budgets["prose"]].decode("utf-8", errors="ignore")),
        fill_budget(dialogue, budgets["dialogue"], seed + 11),
        fill_budget(reasoning, budgets["reasoning"], seed + 22),
        fill_budget(planner, budgets["planner"], seed + 33),
    ]
    return b"".join(pieces)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out-dir", default="data/v0")
    ap.add_argument("--train-mb", type=float, default=16.0)
    ap.add_argument("--valid-mb", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=20260930)
    args = ap.parse_args()

    raw = Path(args.raw_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wiki_train_path = raw / "wikitext-2-raw" / "wiki.train.raw"
    wiki_valid_path = raw / "wikitext-2-raw" / "wiki.valid.raw"
    oasst_path = raw / "oasst1-ready.jsonl.gz"

    dialogue_train, dialogue_valid = load_oasst(oasst_path)
    reason_train = reasoning_records(args.seed + 100, 12000)
    reason_valid = reasoning_records(args.seed + 200, 1200)
    plan_train = planner_records(args.seed + 300, 12000)
    plan_valid = planner_records(args.seed + 400, 1200)

    reason_train_hashes = {hashlib.sha256(x).hexdigest() for x in reason_train}
    plan_train_hashes = {hashlib.sha256(x).hexdigest() for x in plan_train}
    reason_valid = [x for x in reason_valid if hashlib.sha256(x).hexdigest() not in reason_train_hashes]
    plan_valid = [x for x in plan_valid if hashlib.sha256(x).hexdigest() not in plan_train_hashes]

    train_total = int(args.train_mb * 1024 * 1024)
    valid_total = int(args.valid_mb * 1024 * 1024)
    weights = {"prose": 0.50, "dialogue": 0.25, "reasoning": 0.125, "planner": 0.125}

    train_budgets = {k: int(train_total * v) for k, v in weights.items()}
    valid_budgets = {k: int(valid_total * v) for k, v in weights.items()}

    train = build_split(
        wiki=wiki_train_path.read_bytes(),
        dialogue=dialogue_train,
        reasoning=reason_train,
        planner=plan_train,
        budgets=train_budgets,
        seed=args.seed,
    )
    valid = build_split(
        wiki=wiki_valid_path.read_bytes(),
        dialogue=dialogue_valid,
        reasoning=reason_valid,
        planner=plan_valid,
        budgets=valid_budgets,
        seed=args.seed + 1,
    )
    train_path = out / "train.bin"
    valid_path = out / "valid.bin"
    train_path.write_bytes(train)
    valid_path.write_bytes(valid)

    overlap = {
        hashlib.sha256(x).hexdigest() for x in reason_train + plan_train
    } & {
        hashlib.sha256(x).hexdigest() for x in reason_valid + plan_valid
    }
    if overlap:
        raise RuntimeError("generated train/valid record overlap detected")

    manifest = {
        "seed": args.seed,
        "weights": weights,
        "train_bytes": len(train),
        "valid_bytes": len(valid),
        "train_sha256": sha256_file(train_path),
        "valid_sha256": sha256_file(valid_path),
        "dialogue_train_records": len(dialogue_train),
        "dialogue_valid_records": len(dialogue_valid),
        "generated_overlap_records": len(overlap),
        "sources": {
            "wikitext_train_sha256": sha256_file(wiki_train_path),
            "wikitext_valid_sha256": sha256_file(wiki_valid_path),
            "oasst1_sha256": sha256_file(oasst_path),
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
