from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import tempfile

from agent_language.developmental_construction_gate_v1 import (
    DevConstructionGrammar,
    make_training,
    vocab,
)
from .runtime import AgentRuntime
from .sqlite_memory import SQLiteAgentMemory
from .whole_agent_closure_gate_v0 import (
    ConstructionStateCapability,
    PointerComposer,
    train_producer,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def score_checks(text: str, checks: list[dict]) -> bool | None:
    if not checks:
        return None
    results = []
    for check in checks:
        typ = check.get("type")
        if typ == "regex":
            results.append(bool(re.search(str(check["pattern"]), text)))
        elif typ == "contains_all":
            vals = [str(x).casefold() for x in check.get("values", [])]
            low = text.casefold()
            results.append(all(v in low for v in vals))
        else:
            raise ValueError(f"unknown check {typ}")
    return all(results)


def load_benchmark() -> dict:
    root = Path(__file__).resolve().parents[2]
    with open(root / "workspace" / "benchmarks" / "chatbot-v0.json", encoding="utf-8") as f:
        return json.load(f)


def build_runtime(seed: int, db_path: Path):
    v = vocab(seed + 9000)
    grammar = DevConstructionGrammar().fit(make_training(seed + 1, v))
    producer, train_meta = train_producer(seed + 200, 500)
    memory = SQLiteAgentMemory(db_path)
    runtime = AgentRuntime(
        composer=PointerComposer(producer),
        contributors=(ConstructionStateCapability(grammar),),
        memory=memory,
    )
    return runtime, memory, train_meta


def run_seed(seed: int, bench: dict) -> dict:
    rows = []
    producer_meta = None
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        runtimes = {}
        memories = {}

        for turn in bench["turns"]:
            thread = str(turn["thread"])
            # Switching and repeated-structure threads retain context internally.
            # Every isolated thread gets its own durable store.
            if thread not in runtimes:
                rt, mem, meta = build_runtime(seed, tdir / f"{thread}.sqlite")
                runtimes[thread] = rt
                memories[thread] = mem
                producer_meta = producer_meta or meta

            rt = runtimes[thread]
            mem = memories[thread]
            before_semantic = dict(mem.semantic)
            response, trace = rt.turn(str(turn["prompt"]))
            after_semantic = dict(mem.semantic)

            response_kind = str(trace.response_metadata.get("response_kind", ""))
            parse_success = response_kind != "fail"
            checks = list(turn.get("checks", []))
            automatic = score_checks(response, checks)

            rows.append({
                "id": turn["id"],
                "thread": thread,
                "category": turn["category"],
                "prompt": turn["prompt"],
                "response": response,
                "response_kind": response_kind,
                "perception_success": parse_success,
                "semantic_updates": sorted(set(after_semantic) - set(before_semantic)),
                "automatic_pass": automatic,
                "manual_criteria_count": len(turn.get("criteria", [])),
                "trace": trace.to_dict(),
            })

        for mem in memories.values():
            mem.close()

    auto = [r for r in rows if r["automatic_pass"] is not None]
    return {
        "seed": seed,
        "producer": producer_meta,
        "turns": rows,
        "perception_successes": sum(r["perception_success"] for r in rows),
        "turns_total": len(rows),
        "automatic_passes": sum(bool(r["automatic_pass"]) for r in auto),
        "automatic_total": len(auto),
        "fail_response_count": sum(r["response_kind"] == "fail" for r in rows),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--out", default="whole_agent_chatbot_v0.json")
    args = ap.parse_args()

    bench = load_benchmark()
    runs = [run_seed(int(s), bench) for s in args.seeds.split(",")]
    out = {
        "benchmark": bench["id"],
        "description": bench["description"],
        "runs": runs,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    print(json.dumps({
        "benchmark": bench["id"],
        "summaries": [{
            "seed": r["seed"],
            "perception": f"{r['perception_successes']}/{r['turns_total']}",
            "automatic": f"{r['automatic_passes']}/{r['automatic_total']}",
            "fail_responses": r["fail_response_count"],
        } for r in runs],
        "sample_responses": [{
            "id": x["id"],
            "kind": x["response_kind"],
            "response": x["response"],
        } for x in runs[0]["turns"]],
    }, indent=2))
