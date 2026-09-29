from __future__ import annotations

import argparse
import json
import random
from statistics import mean
from time import perf_counter

import torch
from torch import nn
import torch.nn.functional as F

from .benchmark import MEMORY, QUERY, RELATION, RULE
from .models import ANSWER_VOCAB, FactorGraphCore, SlotEncoder, parameter_count
from .transfer import compose_batch


class OperatorStep(nn.Module):
    """One learned computation phase over the shared factor state."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.to_symbol = nn.ModuleList(
            [nn.Linear(dim, dim, bias=False) for _ in range(3)]
        )
        self.from_symbol = nn.ModuleList(
            [nn.Linear(dim, dim, bias=False) for _ in range(3)]
        )
        self.slot_global = nn.Linear(dim, dim, bias=False)
        self.symbol_update = nn.GRUCell(dim, dim)
        self.slot_update = nn.GRUCell(dim, dim)
        self.symbol_norm = nn.LayerNorm(dim)
        self.slot_norm = nn.LayerNorm(dim)

    def forward(
        self,
        slot_state: torch.Tensor,
        symbol_state: torch.Tensor,
        slots: torch.Tensor,
        active: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        batch, slot_count, dim = slot_state.shape
        role_ids = [slots[..., 1], slots[..., 2], slots[..., 3]]

        total = torch.zeros_like(symbol_state)
        counts = torch.zeros(
            batch,
            ANSWER_VOCAB,
            1,
            device=slot_state.device,
            dtype=slot_state.dtype,
        )

        for role, ids in enumerate(role_ids):
            valid = active & ids.ne(0)
            part, part_count = FactorGraphCore._scatter_role(
                self.to_symbol[role](slot_state),
                ids,
                valid,
                ANSWER_VOCAB,
            )
            total = total + part
            counts = counts + part_count

        symbol_message = total / counts.clamp_min(1.0)
        updated_symbol = self.symbol_update(
            symbol_message.reshape(batch * ANSWER_VOCAB, dim),
            symbol_state.reshape(batch * ANSWER_VOCAB, dim),
        ).view(batch, ANSWER_VOCAB, dim)
        updated_symbol = self.symbol_norm(updated_symbol)

        affected_symbol = counts.gt(0).to(slot_state.dtype)
        symbol_state = (
            updated_symbol * affected_symbol
            + symbol_state * (1.0 - affected_symbol)
        )

        incoming = torch.zeros_like(slot_state)
        for role, ids in enumerate(role_ids):
            gathered = FactorGraphCore._gather_symbols(symbol_state, ids)
            incoming = incoming + (
                self.from_symbol[role](gathered)
                * ids.ne(0).unsqueeze(-1)
            )

        active_float = active.unsqueeze(-1).to(slot_state.dtype)
        global_context = (
            self.slot_global(slot_state) * active_float
        ).sum(1) / active_float.sum(1).clamp_min(1.0)
        incoming = incoming + global_context[:, None, :]

        updated_slot = self.slot_update(
            incoming.reshape(batch * slot_count, dim),
            slot_state.reshape(batch * slot_count, dim),
        ).view(batch, slot_count, dim)
        updated_slot = self.slot_norm(updated_slot)

        slot_state = (
            updated_slot * active_float
            + slot_state * (1.0 - active_float)
        )
        return slot_state, symbol_state


class OracleOperatorCore(nn.Module):
    """Upper bound: semantic operator phases and route are supplied."""

    def __init__(
        self,
        dim: int = 40,
        relation_steps: int = 5,
        memory_steps: int = 2,
        rule_steps: int = 1,
    ) -> None:
        super().__init__()
        self.encoder = SlotEncoder(dim)
        self.operators = nn.ModuleList(
            [OperatorStep(dim) for _ in range(3)]
        )
        self.route = (
            [0] * int(relation_steps)
            + [1] * int(memory_steps)
            + [2] * int(rule_steps)
        )
        self.query_proj = nn.Linear(dim, dim, bias=False)
        self.answer_proj = nn.Linear(dim, dim, bias=False)
        self.output_bias = nn.Parameter(torch.zeros(ANSWER_VOCAB))

    def forward(
        self,
        slots: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        slot_state = self.encoder(slots) * mask.unsqueeze(-1)
        batch, _slot_count, dim = slot_state.shape
        symbol_state = self.encoder.symbol.weight[:ANSWER_VOCAB][None].expand(
            batch,
            -1,
            -1,
        )

        kinds = slots[..., 0]
        phase_masks = (
            mask & (kinds.eq(RELATION) | kinds.eq(QUERY)),
            mask & (kinds.eq(MEMORY) | kinds.eq(QUERY)),
            mask & (kinds.eq(RULE) | kinds.eq(QUERY)),
        )

        for operator_id in self.route:
            slot_state, symbol_state = self.operators[operator_id](
                slot_state,
                symbol_state,
                slots,
                phase_masks[operator_id],
            )

        query_mask = kinds.eq(QUERY)
        query_index = query_mask.float().argmax(1)
        query = slot_state[
            torch.arange(batch, device=slots.device),
            query_index,
        ]

        logits = torch.einsum(
            "bd,bvd->bv",
            self.query_proj(query),
            self.answer_proj(symbol_state),
        ) / (dim ** 0.5)
        logits = logits + self.output_bias
        logits[:, 0] = -1e9
        return logits


def build_baseline() -> FactorGraphCore:
    return FactorGraphCore(
        dim=64,
        steps=8,
        reinject=False,
    )


def build_oracle() -> OracleOperatorCore:
    return OracleOperatorCore(
        dim=40,
        relation_steps=5,
        memory_steps=2,
        rule_steps=1,
    )


def evaluate(
    model: nn.Module,
    seed: int,
    *,
    ood: bool,
    count: int,
) -> float:
    model.eval()
    rng = random.Random(seed + (100_000 if ood else 0))
    correct = 0

    with torch.no_grad():
        for start in range(0, count, 64):
            size = min(64, count - start)
            slots, mask, answer = compose_batch(
                rng,
                size,
                ood=ood,
            )
            prediction = model(slots, mask).argmax(-1)
            correct += int((prediction == answer).sum().item())

    return correct / count


def learning_curve(
    model: nn.Module,
    seed: int,
    *,
    checkpoints: list[int],
    batch_size: int,
    eval_count: int,
) -> list[dict]:
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )
    rng = random.Random(seed * 1009 + 17)
    rows = []
    last_step = 0

    for checkpoint in checkpoints:
        if checkpoint < last_step:
            raise ValueError("checkpoints must increase")

        model.train()
        for _ in range(last_step, checkpoint):
            slots, mask, answer = compose_batch(
                rng,
                batch_size,
                ood=False,
            )
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(
                model(slots, mask),
                answer,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )
            optimizer.step()

        rows.append(
            {
                "step": checkpoint,
                "iid": evaluate(
                    model,
                    seed + 5000,
                    ood=False,
                    count=eval_count,
                ),
                "ood": evaluate(
                    model,
                    seed + 6000,
                    ood=True,
                    count=eval_count,
                ),
            }
        )
        last_step = checkpoint

    return rows


def run_seed(
    seed: int,
    *,
    checkpoints: list[int],
    batch_size: int,
    eval_count: int,
) -> dict:
    started = perf_counter()

    torch.manual_seed(seed + 100_000)
    baseline = build_baseline()
    torch.manual_seed(seed + 200_000)
    oracle = build_oracle()

    baseline_curve = learning_curve(
        baseline,
        seed,
        checkpoints=checkpoints,
        batch_size=batch_size,
        eval_count=eval_count,
    )
    oracle_curve = learning_curve(
        oracle,
        seed,
        checkpoints=checkpoints,
        batch_size=batch_size,
        eval_count=eval_count,
    )

    return {
        "seed": seed,
        "parameters": {
            "baseline": parameter_count(baseline),
            "oracle_operator": parameter_count(oracle),
        },
        "baseline": baseline_curve,
        "oracle_operator": oracle_curve,
        "final_ood_delta": (
            oracle_curve[-1]["ood"]
            - baseline_curve[-1]["ood"]
        ),
        "wall_seconds": perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="11,22,33")
    parser.add_argument(
        "--checkpoints",
        default="0,128,256,512,768,1024",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--eval-count", type=int, default=200)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    seeds = [
        int(item.strip())
        for item in args.seeds.split(",")
        if item.strip()
    ]
    checkpoints = [
        int(item.strip())
        for item in args.checkpoints.split(",")
        if item.strip()
    ]

    rows = [
        run_seed(
            seed,
            checkpoints=checkpoints,
            batch_size=args.batch_size,
            eval_count=args.eval_count,
        )
        for seed in seeds
    ]

    mean_delta = mean(
        row["final_ood_delta"]
        for row in rows
    )

    payload = {
        "question": (
            "Does explicit oracle-routed operator decomposition "
            "produce a large compositional-OOD gain over a "
            "parameter-matched shared factor processor?"
        ),
        "parameter_counts": rows[0]["parameters"],
        "mean_final_iid": {
            "baseline": mean(
                row["baseline"][-1]["iid"]
                for row in rows
            ),
            "oracle_operator": mean(
                row["oracle_operator"][-1]["iid"]
                for row in rows
            ),
        },
        "mean_final_ood": {
            "baseline": mean(
                row["baseline"][-1]["ood"]
                for row in rows
            ),
            "oracle_operator": mean(
                row["oracle_operator"][-1]["ood"]
                for row in rows
            ),
        },
        "mean_final_ood_delta": mean_delta,
        "gate_threshold_ood_delta": 0.20,
        "gate_pass": mean_delta >= 0.20,
        "rows": rows,
    }

    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
