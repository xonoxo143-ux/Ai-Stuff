from __future__ import annotations

import argparse
from copy import deepcopy
import json
import random
from statistics import mean
from time import perf_counter

import torch
from torch import nn
import torch.nn.functional as F

from .benchmark import (
    Example,
    FAMILY_NAMES,
    MAX_SLOTS,
    MEMORY,
    OP_MAP,
    OP_OLDER,
    OP_VALUE,
    QUERY,
    RELATION,
    RULE,
    Q_MAP,
    generate_example,
)
from .models import (
    ANSWER_VOCAB,
    FactorGraphCore,
    parameter_count,
)


FAMILY_COMPOSE = len(FAMILY_NAMES)


def _pack_compose(
    rows,
    answer: int,
    difficulty: int,
) -> Example:
    if len(rows) > MAX_SLOTS:
        raise ValueError("too many composition slots")
    slots = torch.zeros(
        MAX_SLOTS,
        6,
        dtype=torch.long,
    )
    mask = torch.zeros(
        MAX_SLOTS,
        dtype=torch.bool,
    )
    for index, row in enumerate(rows):
        slots[index] = torch.tensor(
            row,
            dtype=torch.long,
        )
        mask[index] = True
    return Example(
        slots,
        mask,
        int(answer),
        FAMILY_COMPOSE,
        int(difficulty),
    )


def compose_example(
    rng: random.Random,
    *,
    ood: bool,
) -> Example:
    """New family: relation traversal -> memory lookup -> rule transform."""

    chain_length = (
        rng.randint(3, 5)
        if ood
        else rng.randint(1, 2)
    )
    nodes = rng.sample(
        range(1, 14),
        chain_length + 1,
    )
    start = nodes[0]
    terminal = nodes[-1]

    rows = []
    relation_rows = [
        (
            RELATION,
            nodes[index],
            nodes[index + 1],
            0,
            OP_OLDER,
            index,
        )
        for index in range(chain_length)
    ]
    rng.shuffle(relation_rows)
    rows.extend(relation_rows)

    base_value = rng.randint(1, 8)
    rows.append(
        (
            MEMORY,
            terminal,
            base_value,
            0,
            OP_VALUE,
            len(rows),
        )
    )

    offset = rng.randint(1, 3)
    possible = [
        value
        for value in range(1, 9)
        if value != base_value
    ]
    rng.shuffle(possible)
    demo_count = 3 if ood else 2
    for value in possible[:demo_count]:
        mapped = (
            (value - 1 + offset) % 8
        ) + 1
        rows.append(
            (
                RULE,
                value,
                mapped,
                0,
                OP_MAP,
                len(rows),
            )
        )

    used_nodes = set(nodes)
    free_nodes = [
        value
        for value in range(1, 14)
        if value not in used_nodes
    ]
    if len(free_nodes) >= 2:
        a, b = rng.sample(
            free_nodes,
            2,
        )
        rows.append(
            (
                RELATION,
                a,
                b,
                0,
                OP_OLDER,
                len(rows),
            )
        )

    memory_key_choices = [
        value
        for value in free_nodes
        if value != terminal
    ]
    if memory_key_choices:
        rows.append(
            (
                MEMORY,
                rng.choice(
                    memory_key_choices
                ),
                rng.randint(1, 8),
                0,
                OP_VALUE,
                len(rows),
            )
        )

    rng.shuffle(rows)
    rows.append(
        (
            QUERY,
            start,
            0,
            0,
            Q_MAP,
            len(rows),
        )
    )

    answer = (
        (base_value - 1 + offset) % 8
    ) + 1
    return _pack_compose(
        rows,
        answer,
        chain_length,
    )


def compose_oracle(
    example: Example,
) -> int:
    rows = (
        example.slots[
            example.mask
        ]
        .tolist()
    )
    query = next(
        row
        for row in rows
        if row[0] == QUERY
    )
    start = query[1]

    adjacency = {}
    memories = {}
    rules = []

    for (
        kind,
        a,
        b,
        _c,
        op,
        _pos,
    ) in rows:
        if (
            kind == RELATION
            and op == OP_OLDER
        ):
            adjacency.setdefault(
                a,
                [],
            ).append(b)
        elif (
            kind == MEMORY
            and op == OP_VALUE
        ):
            memories[a] = b
        elif (
            kind == RULE
            and op == OP_MAP
        ):
            rules.append(
                (a, b)
            )

    frontier = [start]
    seen = {start}
    base_value = None
    while frontier:
        node = frontier.pop(0)
        if node in memories:
            base_value = memories[node]
            break
        for nxt in adjacency.get(
            node,
            [],
        ):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)

    if base_value is None:
        raise ValueError(
            "no reachable memory value"
        )
    if not rules:
        raise ValueError(
            "no transformation rule"
        )

    x, y = rules[0]
    offset = (y - x) % 8
    return (
        (base_value - 1 + offset) % 8
    ) + 1


def compose_batch(
    rng: random.Random,
    size: int,
    *,
    ood: bool,
):
    examples = [
        compose_example(
            rng,
            ood=ood,
        )
        for _ in range(size)
    ]
    return (
        torch.stack(
            [
                example.slots
                for example
                in examples
            ]
        ),
        torch.stack(
            [
                example.mask
                for example
                in examples
            ]
        ),
        torch.tensor(
            [
                example.answer
                for example
                in examples
            ],
            dtype=torch.long,
        ),
    )


def base_batch(
    rng: random.Random,
    size: int,
):
    examples = [
        generate_example(rng)
        for _ in range(size)
    ]
    return (
        torch.stack(
            [
                example.slots
                for example
                in examples
            ]
        ),
        torch.stack(
            [
                example.mask
                for example
                in examples
            ]
        ),
        torch.tensor(
            [
                example.answer
                for example
                in examples
            ],
            dtype=torch.long,
        ),
    )


def new_core() -> FactorGraphCore:
    return FactorGraphCore(
        steps=6,
        reinject=False,
    )


class FrozenHowAdapter(nn.Module):
    """Tiny task-context/readout adapter around a frozen pretrained core."""

    def __init__(
        self,
        base: FactorGraphCore,
        rank: int = 8,
    ) -> None:
        super().__init__()
        self.base = base
        for parameter in (
            self.base.parameters()
        ):
            parameter.requires_grad = False

        dim = (
            self.base.query_proj
            .in_features
        )
        self.task_context = (
            nn.Parameter(
                torch.zeros(dim)
            )
        )
        self.down = nn.Linear(
            dim,
            rank,
            bias=False,
        )
        self.up = nn.Linear(
            rank,
            dim,
            bias=False,
        )
        nn.init.zeros_(
            self.up.weight
        )

        self.to_symbol_log_scale = (
            nn.Parameter(
                torch.zeros(3)
            )
        )
        self.from_symbol_log_scale = (
            nn.Parameter(
                torch.zeros(3)
            )
        )
        self.global_log_scale = (
            nn.Parameter(
                torch.zeros(())
            )
        )

    def forward(
        self,
        slots: torch.Tensor,
        mask: torch.Tensor,
        *,
        steps: int | None = None,
    ) -> torch.Tensor:
        base = self.base
        slot_init = (
            base.encoder(slots)
            * mask.unsqueeze(-1)
        )

        query_mask = (
            slots[..., 0]
            .eq(QUERY)
        )
        slot_init = (
            slot_init
            + query_mask
            .unsqueeze(-1)
            .to(slot_init.dtype)
            * self.task_context
        )
        slot_state = slot_init

        batch, slot_count, dim = (
            slot_state.shape
        )
        vocab = ANSWER_VOCAB

        symbol_init = (
            base.encoder.symbol
            .weight[:vocab][None]
            .expand(
                batch,
                -1,
                -1,
            )
        )
        symbol_state = symbol_init
        role_ids = [
            slots[..., 1],
            slots[..., 2],
            slots[..., 3],
        ]

        thought_steps = (
            base.steps
            if steps is None
            else int(steps)
        )

        for _ in range(
            thought_steps
        ):
            total = torch.zeros_like(
                symbol_state
            )
            counts = torch.zeros(
                batch,
                vocab,
                1,
                device=slot_state.device,
                dtype=slot_state.dtype,
            )

            for role, ids in enumerate(
                role_ids
            ):
                valid = (
                    mask
                    & ids.ne(0)
                )
                messages = (
                    base.to_symbol[role](
                        slot_state
                    )
                    * self
                    .to_symbol_log_scale[
                        role
                    ]
                    .exp()
                )
                part, part_count = (
                    base._scatter_role(
                        messages,
                        ids,
                        valid,
                        vocab,
                    )
                )
                total = total + part
                counts = (
                    counts
                    + part_count
                )

            symbol_message = (
                total
                / counts.clamp_min(
                    1.0
                )
            )
            symbol_state = (
                base.symbol_update(
                    symbol_message.reshape(
                        batch * vocab,
                        dim,
                    ),
                    symbol_state.reshape(
                        batch * vocab,
                        dim,
                    ),
                )
                .view(
                    batch,
                    vocab,
                    dim,
                )
            )
            symbol_state = (
                base.symbol_norm(
                    symbol_state
                )
            )

            incoming = torch.zeros_like(
                slot_state
            )
            for role, ids in enumerate(
                role_ids
            ):
                gathered = (
                    base._gather_symbols(
                        symbol_state,
                        ids,
                    )
                )
                incoming = (
                    incoming
                    + base.from_symbol[
                        role
                    ](
                        gathered
                    )
                    * ids.ne(0)
                    .unsqueeze(-1)
                    * self
                    .from_symbol_log_scale[
                        role
                    ]
                    .exp()
                )

            valid_slots = (
                mask.unsqueeze(-1)
                .to(
                    slot_state.dtype
                )
            )
            global_context = (
                (
                    base.slot_global(
                        slot_state
                    )
                    * valid_slots
                )
                .sum(1)
                / valid_slots
                .sum(1)
                .clamp_min(1.0)
            )
            incoming = (
                incoming
                + global_context[
                    :,
                    None,
                    :
                ]
                * self
                .global_log_scale
                .exp()
            )

            slot_state = (
                base.slot_update(
                    incoming.reshape(
                        batch
                        * slot_count,
                        dim,
                    ),
                    slot_state.reshape(
                        batch
                        * slot_count,
                        dim,
                    ),
                )
                .view(
                    batch,
                    slot_count,
                    dim,
                )
            )
            slot_state = (
                base.slot_norm(
                    slot_state
                )
                * valid_slots
            )

        query_index = (
            query_mask.float()
            .argmax(1)
        )
        query = slot_state[
            torch.arange(
                batch,
                device=slots.device,
            ),
            query_index,
        ]
        query = (
            query
            + self.up(
                torch.tanh(
                    self.down(
                        query
                    )
                )
            )
        )

        query_key = (
            base.query_proj(
                query
            )
        )
        answer_keys = (
            base.answer_proj(
                symbol_state
            )
        )
        logits = torch.einsum(
            "bd,bvd->bv",
            query_key,
            answer_keys,
        ) / (dim ** 0.5)
        logits = (
            logits
            + base.output_bias
        )
        logits[:, 0] = -1e9
        return logits


def trainable_parameter_count(
    model: nn.Module,
) -> int:
    return sum(
        parameter.numel()
        for parameter
        in model.parameters()
        if parameter.requires_grad
    )


def pretrain_shared(
    seed: int,
    steps: int,
    batch_size: int,
):
    torch.manual_seed(seed)
    rng = random.Random(
        seed * 101 + 7
    )
    model = new_core()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )
    model.train()

    for _ in range(steps):
        slots, mask, answer = (
            base_batch(
                rng,
                batch_size,
            )
        )
        optimizer.zero_grad(
            set_to_none=True
        )
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

    return model


def evaluate_compose(
    model,
    seed: int,
    *,
    ood: bool,
    count: int,
) -> float:
    model.eval()
    rng = random.Random(
        seed
        + (
            100_000
            if ood
            else 0
        )
    )
    correct = 0

    with torch.no_grad():
        for start in range(
            0,
            count,
            64,
        ):
            size = min(
                64,
                count - start,
            )
            slots, mask, answer = (
                compose_batch(
                    rng,
                    size,
                    ood=ood,
                )
            )
            prediction = (
                model(
                    slots,
                    mask,
                )
                .argmax(-1)
            )
            correct += int(
                (
                    prediction
                    == answer
                )
                .sum()
                .item()
            )

    return correct / count


def evaluate_base(
    model,
    seed: int,
    *,
    count: int = 100,
) -> float:
    model.eval()
    scores = []

    with torch.no_grad():
        for family in range(
            len(FAMILY_NAMES)
        ):
            rng = random.Random(
                seed
                + family * 10007
            )
            correct = 0
            for start in range(
                0,
                count,
                50,
            ):
                size = min(
                    50,
                    count - start,
                )
                examples = [
                    generate_example(
                        rng,
                        family,
                        ood=True,
                    )
                    for _ in range(
                        size
                    )
                ]
                slots = torch.stack(
                    [
                        example.slots
                        for example
                        in examples
                    ]
                )
                mask = torch.stack(
                    [
                        example.mask
                        for example
                        in examples
                    ]
                )
                answer = torch.tensor(
                    [
                        example.answer
                        for example
                        in examples
                    ],
                    dtype=torch.long,
                )
                prediction = (
                    model(
                        slots,
                        mask,
                    )
                    .argmax(-1)
                )
                correct += int(
                    (
                        prediction
                        == answer
                    )
                    .sum()
                    .item()
                )
            scores.append(
                correct / count
            )

    return mean(scores)


def adaptation_curve(
    model,
    seed: int,
    *,
    checkpoints: list[int],
    batch_size: int,
    eval_count: int,
) -> list[dict]:
    parameters = [
        parameter
        for parameter
        in model.parameters()
        if parameter.requires_grad
    ]
    if not parameters:
        raise ValueError(
            "model has no trainable parameters"
        )

    optimizer = torch.optim.AdamW(
        parameters,
        lr=2e-3,
        weight_decay=0.01,
    )
    rng = random.Random(
        seed * 1009 + 17
    )
    rows = []
    last_step = 0

    for checkpoint in checkpoints:
        if checkpoint < last_step:
            raise ValueError(
                "checkpoints must increase"
            )

        model.train()
        for _ in range(
            last_step,
            checkpoint,
        ):
            slots, mask, answer = (
                compose_batch(
                    rng,
                    batch_size,
                    ood=False,
                )
            )
            optimizer.zero_grad(
                set_to_none=True
            )
            loss = F.cross_entropy(
                model(
                    slots,
                    mask,
                ),
                answer,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                parameters,
                1.0,
            )
            optimizer.step()

        rows.append(
            {
                "step": checkpoint,
                "iid":
                    evaluate_compose(
                        model,
                        seed + 5000,
                        ood=False,
                        count=eval_count,
                    ),
                "ood":
                    evaluate_compose(
                        model,
                        seed + 6000,
                        ood=True,
                        count=eval_count,
                    ),
            }
        )
        last_step = checkpoint

    return rows


def first_step_at(
    curve: list[dict],
    threshold: float,
) -> int | None:
    for row in curve:
        if (
            row["ood"]
            >= threshold
        ):
            return int(
                row["step"]
            )
    return None


def run_seed(
    seed: int,
    *,
    pretrain_steps: int,
    checkpoints: list[int],
    batch_size: int,
    eval_count: int,
) -> dict:
    started = perf_counter()

    pretrained = pretrain_shared(
        seed,
        pretrain_steps,
        batch_size,
    )
    pretrain_base_ood = (
        evaluate_base(
            pretrained,
            seed + 7000,
        )
    )
    zero_shot = evaluate_compose(
        pretrained,
        seed + 7100,
        ood=True,
        count=eval_count,
    )

    torch.manual_seed(
        seed + 100_000
    )
    fresh = new_core()
    ordinary = deepcopy(
        pretrained
    )
    frozen_how = FrozenHowAdapter(
        deepcopy(pretrained)
    )

    arms = {
        "fresh": fresh,
        "ordinary_transfer":
            ordinary,
        "frozen_how":
            frozen_how,
    }

    curves = {}
    for index, (
        name,
        model,
    ) in enumerate(
        arms.items()
    ):
        curves[name] = (
            adaptation_curve(
                model,
                seed
                + index * 100_000,
                checkpoints=
                    checkpoints,
                batch_size=
                    batch_size,
                eval_count=
                    eval_count,
            )
        )

    post_transfer_base_ood = (
        evaluate_base(
            ordinary,
            seed + 7200,
        )
    )

    threshold_rows = {}
    for name, curve in (
        curves.items()
    ):
        threshold_rows[name] = {
            str(threshold):
                first_step_at(
                    curve,
                    threshold,
                )
            for threshold in (
                0.5,
                0.7,
                0.8,
            )
        }

    return {
        "seed": seed,
        "pretrain_steps":
            pretrain_steps,
        "pretrain_base_ood":
            pretrain_base_ood,
        "zero_shot_task6_ood":
            zero_shot,
        "ordinary_old_task_ood_after":
            post_transfer_base_ood,
        "ordinary_old_task_delta":
            (
                post_transfer_base_ood
                - pretrain_base_ood
            ),
        "parameters": {
            "fresh_total":
                parameter_count(
                    fresh
                ),
            "ordinary_total":
                parameter_count(
                    ordinary
                ),
            "frozen_how_total":
                parameter_count(
                    frozen_how
                ),
            "frozen_how_trainable":
                trainable_parameter_count(
                    frozen_how
                ),
        },
        "threshold_steps":
            threshold_rows,
        "curves": curves,
        "wall_seconds":
            perf_counter()
            - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        default="11,22,33",
    )
    parser.add_argument(
        "--pretrain-steps",
        type=int,
        default=400,
    )
    parser.add_argument(
        "--checkpoints",
        default=(
            "0,8,16,32,64,"
            "128,256,512,1024"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--eval-count",
        type=int,
        default=200,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--output",
    )
    args = parser.parse_args()

    torch.set_num_threads(
        args.threads
    )
    seeds = [
        int(value)
        for value in (
            item.strip()
            for item
            in args.seeds.split(",")
        )
        if value
    ]
    checkpoints = [
        int(value)
        for value in (
            item.strip()
            for item
            in args.checkpoints.split(",")
        )
        if value
    ]

    rows = [
        run_seed(
            seed,
            pretrain_steps=
                args.pretrain_steps,
            checkpoints=
                checkpoints,
            batch_size=
                args.batch_size,
            eval_count=
                args.eval_count,
        )
        for seed in seeds
    ]

    arms = (
        "fresh",
        "ordinary_transfer",
        "frozen_how",
    )
    summary = {}
    for arm in arms:
        summary[arm] = {
            "runs": len(rows),
            "mean_final_iid":
                mean(
                    row["curves"][
                        arm
                    ][-1]["iid"]
                    for row in rows
                ),
            "mean_final_ood":
                mean(
                    row["curves"][
                        arm
                    ][-1]["ood"]
                    for row in rows
                ),
            "mean_ood_by_step": {
                str(step):
                    mean(
                        next(
                            item["ood"]
                            for item
                            in row[
                                "curves"
                            ][arm]
                            if item[
                                "step"
                            ] == step
                        )
                        for row
                        in rows
                    )
                for step
                in checkpoints
            },
        }

    payload = {
        "task6": (
            "relation traversal"
            " -> memory lookup"
            " -> inferred rule"
        ),
        "summary": summary,
        "mean_zero_shot_task6_ood":
            mean(
                row[
                    "zero_shot_task6_ood"
                ]
                for row in rows
            ),
        "mean_pretrain_base_ood":
            mean(
                row[
                    "pretrain_base_ood"
                ]
                for row in rows
            ),
        "mean_old_task_delta_after_ordinary":
            mean(
                row[
                    "ordinary_old_task_delta"
                ]
                for row in rows
            ),
        "rows": rows,
    }

    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    print(text)

    if args.output:
        with open(
            args.output,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                text + "\n"
            )


if __name__ == "__main__":
    main()
