from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import tempfile
from time import perf_counter

import torch
import torch.nn as nn

from agent_language.developmental_construction_gate_v1 import (
    DevConstructionGrammar,
    make_training,
    vocab,
)
from .contracts import (
    CapabilityContext,
    CapabilityOffer,
    CapabilityResult,
    CapabilityRole,
    PublicMessage,
)
from .runtime import AgentRuntime
from .sqlite_memory import SQLiteAgentMemory


COPY_NAME = 256
COPY_ATTR = 257
COPY_VALUE = 258
EOS = 259
BOS = 260
OUTPUT_VOCAB = 260
INPUT_VOCAB = 261

KINDS = ("ack", "answer", "unknown", "fail")
KIND_ID = {k: i for i, k in enumerate(KINDS)}

SCAFFOLDS = {
    "ack": [
        *b"Okay, I will remember that ",
        COPY_NAME,
        *b"'s ",
        COPY_ATTR,
        *b" is ",
        COPY_VALUE,
        ord("."),
        EOS,
    ],
    "answer": [
        COPY_NAME,
        *b"'s ",
        COPY_ATTR,
        *b" is ",
        COPY_VALUE,
        ord("."),
        EOS,
    ],
    "unknown": [
        *b"I don't know ",
        COPY_NAME,
        *b"'s ",
        COPY_ATTR,
        *b" yet.",
        EOS,
    ],
    "fail": [
        *b"I didn't understand that.",
        EOS,
    ],
}


class PointerProducer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.token_emb = nn.Embedding(INPUT_VOCAB, 32)
        self.kind_emb = nn.Embedding(len(KINDS), 48)
        self.kind_to_hidden = nn.Linear(48, 64)
        self.gru = nn.GRU(32, 64, batch_first=True)
        self.out = nn.Linear(64, OUTPUT_VOCAB)

    def forward(self, kind_ids: torch.Tensor, prev: torch.Tensor) -> torch.Tensor:
        h0 = torch.tanh(self.kind_to_hidden(self.kind_emb(kind_ids))).unsqueeze(0)
        h, _ = self.gru(self.token_emb(prev), h0)
        return self.out(h)


def scaffold_batch() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    rows = []
    targets = []
    kinds = []
    max_len = max(len(v) for v in SCAFFOLDS.values())
    for kind in KINDS:
        tgt = list(SCAFFOLDS[kind])
        inp = [BOS] + tgt[:-1]
        pad = max_len - len(tgt)
        rows.append(inp + [BOS] * pad)
        targets.append(tgt + [-100] * pad)
        kinds.append(KIND_ID[kind])
    return (
        torch.tensor(kinds, dtype=torch.long),
        torch.tensor(rows, dtype=torch.long),
        torch.tensor(targets, dtype=torch.long),
    )


def train_producer(seed: int, steps: int = 500) -> tuple[PointerProducer, dict]:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    model = PointerProducer()
    opt = torch.optim.AdamW(model.parameters(), lr=8e-3, weight_decay=1e-5)
    kind_ids, prev, target = scaffold_batch()
    started = perf_counter()
    final_loss = None
    for _ in range(steps):
        opt.zero_grad()
        logits = model(kind_ids, prev)
        loss = nn.functional.cross_entropy(
            logits.reshape(-1, OUTPUT_VOCAB),
            target.reshape(-1),
            ignore_index=-100,
        )
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        final_loss = float(loss.detach())
    return model.eval(), {
        "params": sum(p.numel() for p in model.parameters()),
        "steps": steps,
        "train_seconds": perf_counter() - started,
        "final_loss": final_loss,
    }


@torch.no_grad()
def generate_tokens(model: PointerProducer, kind: str, max_steps: int = 96) -> list[int]:
    kid = torch.tensor([KIND_ID[kind]], dtype=torch.long)
    hidden = torch.tanh(model.kind_to_hidden(model.kind_emb(kid))).unsqueeze(0)
    token = torch.tensor([[BOS]], dtype=torch.long)
    out = []
    for _ in range(max_steps):
        h, hidden = model.gru(model.token_emb(token), hidden)
        logits = model.out(h[:, -1])
        nxt = int(logits.argmax(-1).item())
        out.append(nxt)
        if nxt == EOS:
            break
        token = torch.tensor([[nxt]], dtype=torch.long)
    return out


def render(tokens: list[int], slots: dict[str, str]) -> str:
    buf = bytearray()
    for tok in tokens:
        if 0 <= tok <= 255:
            buf.append(tok)
        elif tok == COPY_NAME:
            buf.extend(slots.get("name", "").encode())
        elif tok == COPY_ATTR:
            buf.extend(slots.get("attr", "").encode())
        elif tok == COPY_VALUE:
            buf.extend(slots.get("value", "").encode())
        elif tok == EOS:
            break
        else:
            raise ValueError(f"invalid producer token {tok}")
    return buf.decode("utf-8")


class ConstructionStateCapability:
    name = "homegrown-construction-state"
    role = CapabilityRole.CONTRIBUTOR
    contract_version = "0.1"

    def __init__(self, grammar: DevConstructionGrammar) -> None:
        self.grammar = grammar

    def offer(self, context: CapabilityContext) -> CapabilityOffer:
        return CapabilityOffer(
            capability=self.name,
            relevance=1.0,
            estimated_cost=0.01,
            confidence=1.0,
            tags=("homegrown", "construction", "state"),
        )

    @staticmethod
    def fact_key(attr: str, name: str) -> str:
        return f"fact::{attr}::{name}"

    def run(self, context: CapabilityContext) -> CapabilityResult:
        started = perf_counter()
        parsed = self.grammar.parse(context.user_text)
        if parsed is None:
            state = {"kind": "fail", "name": "", "attr": "", "value": ""}
            return CapabilityResult(
                messages=(PublicMessage(
                    kind="response_state",
                    content=state,
                    source=self.name,
                    confidence=1.0,
                ),),
                active_state_updates={"last_parse": "fail"},
                measured_cost=perf_counter() - started,
            )

        mode = str(parsed["mode"])
        attr = str(parsed["attr"])
        name = str(parsed["name"])
        key = self.fact_key(attr, name)

        if mode == "set":
            value = str(parsed["value"])
            state = {
                "kind": "ack",
                "name": name,
                "attr": attr,
                "value": value,
            }
            return CapabilityResult(
                messages=(PublicMessage(
                    kind="response_state",
                    content=state,
                    source=self.name,
                    confidence=1.0,
                    metadata={"wrappers": int(parsed.get("_wrappers", 0))},
                ),),
                semantic_updates={
                    key: {
                        "name": name,
                        "attr": attr,
                        "value": value,
                    }
                },
                active_state_updates={
                    "last_entity": name,
                    "last_attribute": attr,
                    "last_operation": "set",
                },
                measured_cost=perf_counter() - started,
            )

        stored = context.semantic_memory.get(key)
        if isinstance(stored, dict) and "value" in stored:
            state = {
                "kind": "answer",
                "name": name,
                "attr": attr,
                "value": str(stored["value"]),
            }
        else:
            state = {
                "kind": "unknown",
                "name": name,
                "attr": attr,
                "value": "",
            }
        return CapabilityResult(
            messages=(PublicMessage(
                kind="response_state",
                content=state,
                source=self.name,
                confidence=1.0,
                metadata={"wrappers": int(parsed.get("_wrappers", 0))},
            ),),
            active_state_updates={
                "last_entity": name,
                "last_attribute": attr,
                "last_operation": "ask",
            },
            measured_cost=perf_counter() - started,
        )


class PointerComposer:
    name = "homegrown-pointer-composer"
    role = CapabilityRole.COMPOSER
    contract_version = "0.1"

    def __init__(self, model: PointerProducer) -> None:
        self.model = model

    def offer(self, context: CapabilityContext):
        return None

    def run(self, context: CapabilityContext) -> CapabilityResult:
        started = perf_counter()
        states = [
            msg.content
            for msg in context.contributions
            if msg.kind == "response_state" and isinstance(msg.content, dict)
        ]
        state = states[-1] if states else {
            "kind": "fail", "name": "", "attr": "", "value": ""
        }
        kind = str(state.get("kind", "fail"))
        if kind not in KIND_ID:
            kind = "fail"
        tokens = generate_tokens(self.model, kind)
        text = render(tokens, {
            "name": str(state.get("name", "")),
            "attr": str(state.get("attr", "")),
            "value": str(state.get("value", "")),
        })
        return CapabilityResult(
            messages=(PublicMessage(
                kind="assistant_text",
                content=text,
                source=self.name,
                confidence=1.0,
                metadata={
                    "backend": "homegrown-pointer-gru",
                    "response_kind": kind,
                    "generated_tokens": len(tokens),
                },
            ),),
            active_state_updates={"last_response_kind": kind},
            measured_cost=perf_counter() - started,
        )


def canonical(kind: str, name: str = "", attr: str = "", value: str = "") -> str:
    return render(list(SCAFFOLDS[kind]), {
        "name": name,
        "attr": attr,
        "value": value,
    })


def run_seed(seed: int, producer_steps: int) -> dict:
    v = vocab(seed + 9000)
    grammar = DevConstructionGrammar().fit(make_training(seed + 1, v))
    producer, train_meta = train_producer(seed + 200, producer_steps)

    # Verify the learned producer itself before integrating it.
    producer_exact = {}
    for kind in KINDS:
        got = render(generate_tokens(producer, kind), {
            "name": "nevertrainedname",
            "attr": "color",
            "value": "nevertrainedvalue",
        })
        want = canonical(kind, "nevertrainedname", "color", "nevertrainedvalue")
        producer_exact[kind] = (got == want)

    name_a = v["name_test"][0]
    name_b = v["name_test"][1]
    name_c = v["name_test"][2]
    color_1 = v["color_test"][0]
    color_2 = v["color_test"][1]
    animal_1 = v["animal_test"][0]

    turns = [
        {
            "text": f"set the color for {name_a} to {color_1}.",
            "want": canonical("ack", name_a, "color", color_1),
            "tag": "set_oov",
        },
        {
            "text": f"please, for reference, set the pet for {name_b} to {animal_1}.",
            "want": canonical("ack", name_b, "pet", animal_1),
            "tag": "nested_wrapper_set",
        },
        {
            "text": f"what is the color for {name_a}?",
            "want": canonical("answer", name_a, "color", color_1),
            "tag": "retrieve_after_switch",
        },
        {
            "text": f"store {color_2} as the color for {name_a}.",
            "want": canonical("ack", name_a, "color", color_2),
            "tag": "overwrite",
        },
        {
            "text": f"tell me the pet for {name_b}.",
            "want": canonical("answer", name_b, "pet", animal_1),
            "tag": "retrieve_after_restart",
        },
        {
            "text": f"give me {name_a}'s color.",
            "want": canonical("answer", name_a, "color", color_2),
            "tag": "resume_updated_thread",
        },
        {
            "text": f"what is the place for {name_c}?",
            "want": canonical("unknown", name_c, "place", ""),
            "tag": "unknown_memory",
        },
    ]

    traces = []
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "agent.sqlite"

        memory = SQLiteAgentMemory(db_path)
        runtime = AgentRuntime(
            composer=PointerComposer(producer),
            contributors=(ConstructionStateCapability(grammar),),
            memory=memory,
        )
        for i, row in enumerate(turns[:4]):
            got, trace = runtime.turn(row["text"])
            traces.append({
                "tag": row["tag"],
                "text": row["text"],
                "got": got,
                "want": row["want"],
                "exact": got == row["want"],
                "trace": trace.to_dict(),
            })
        memory.close()

        # Hard restart: a fresh runtime and memory object, same durable SQLite file.
        memory2 = SQLiteAgentMemory(db_path)
        runtime2 = AgentRuntime(
            composer=PointerComposer(producer),
            contributors=(ConstructionStateCapability(grammar),),
            memory=memory2,
        )
        restart_turn_id = runtime2.turn_id
        for row in turns[4:]:
            got, trace = runtime2.turn(row["text"])
            traces.append({
                "tag": row["tag"],
                "text": row["text"],
                "got": got,
                "want": row["want"],
                "exact": got == row["want"],
                "trace": trace.to_dict(),
            })

        semantic = memory2.semantic
        episodes = memory2.episodes
        capability_stats = memory2.capability_stats
        memory2.close()

    return {
        "seed": seed,
        "producer": train_meta,
        "producer_scaffold_exact": producer_exact,
        "construction_count": len(grammar.patterns),
        "wrapper_count": len(grammar.wrappers),
        "restart_turn_id": restart_turn_id,
        "turns_exact": sum(int(x["exact"]) for x in traces),
        "turns_total": len(traces),
        "all_exact": all(x["exact"] for x in traces),
        "semantic_fact_count": len([k for k in semantic if k.startswith("fact::")]),
        "episodes": len(episodes),
        "capability_stats": capability_stats,
        "turns": traces,
        "no_external_language_backend": True,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--producer-steps", type=int, default=500)
    ap.add_argument("--out", default="whole_agent_closure_v0.json")
    args = ap.parse_args()
    runs = [run_seed(int(s), args.producer_steps) for s in args.seeds.split(",")]
    out = {
        "gate": "whole-agent-closure-v0",
        "runs": runs,
        "passed_all_seeds": all(r["all_exact"] for r in runs),
        "no_external_language_backend": all(r["no_external_language_backend"] for r in runs),
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({
        "passed_all_seeds": out["passed_all_seeds"],
        "no_external_language_backend": out["no_external_language_backend"],
        "summaries": [{
            "seed": r["seed"],
            "turns": f"{r['turns_exact']}/{r['turns_total']}",
            "producer_exact": r["producer_scaffold_exact"],
            "producer_params": r["producer"]["params"],
            "producer_train_seconds": r["producer"]["train_seconds"],
            "restart_turn_id": r["restart_turn_id"],
            "semantic_fact_count": r["semantic_fact_count"],
        } for r in runs],
    }, indent=2))
