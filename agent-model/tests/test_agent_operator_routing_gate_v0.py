import random

import torch

from agent_cognition.operator_gate import (
    OracleOperatorCore,
    build_baseline,
    build_oracle,
)
from agent_cognition.transfer import compose_example


def test_operator_gate_is_parameter_matched():
    baseline = build_baseline()
    oracle = build_oracle()

    baseline_count = sum(
        parameter.numel()
        for parameter in baseline.parameters()
    )
    oracle_count = sum(
        parameter.numel()
        for parameter in oracle.parameters()
    )

    assert abs(oracle_count - baseline_count) / baseline_count < 0.01


def test_oracle_route_has_same_eight_step_budget():
    oracle = build_oracle()
    assert oracle.route == [0, 0, 0, 0, 0, 1, 1, 2]
    assert len(oracle.route) == 8


def test_models_share_task6_output_contract():
    rng = random.Random(71)
    examples = [
        compose_example(rng, ood=False)
        for _ in range(3)
    ]
    slots = torch.stack(
        [example.slots for example in examples]
    )
    mask = torch.stack(
        [example.mask for example in examples]
    )

    for model in (
        build_baseline(),
        build_oracle(),
    ):
        logits = model(slots, mask)
        assert logits.shape == (3, 32)


def test_oracle_core_handles_ood_shape():
    rng = random.Random(72)
    examples = [
        compose_example(rng, ood=True)
        for _ in range(2)
    ]
    slots = torch.stack(
        [example.slots for example in examples]
    )
    mask = torch.stack(
        [example.mask for example in examples]
    )

    model = OracleOperatorCore()
    logits = model(slots, mask)
    assert logits.shape == (2, 32)
