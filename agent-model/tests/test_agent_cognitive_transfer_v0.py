import random

import torch

from agent_cognition.transfer import (
    FrozenHowAdapter,
    compose_example,
    compose_oracle,
    new_core,
    trainable_parameter_count,
)


def test_composition_oracle_iid_and_ood():
    for ood in (
        False,
        True,
    ):
        rng = random.Random(
            8001
            if ood
            else 8000
        )
        for _ in range(200):
            example = (
                compose_example(
                    rng,
                    ood=ood,
                )
            )
            assert (
                compose_oracle(
                    example
                )
                == example.answer
            )


def test_composition_uses_shared_contract():
    example = compose_example(
        random.Random(3),
        ood=False,
    )
    assert example.slots.shape == (
        24,
        6,
    )
    assert example.mask.shape == (
        24,
    )
    assert (
        1
        <= example.answer
        <= 8
    )


def test_frozen_how_adapter_is_tiny():
    base = new_core()
    adapter = FrozenHowAdapter(
        base
    )

    assert (
        trainable_parameter_count(
            adapter
        )
        < 2_000
    )
    assert all(
        not parameter.requires_grad
        for parameter
        in adapter.base.parameters()
    )


def test_transfer_models_share_output_contract():
    rng = random.Random(4)
    examples = [
        compose_example(
            rng,
            ood=False,
        )
        for _ in range(3)
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

    base = new_core()
    adapter = FrozenHowAdapter(
        new_core()
    )

    for model in (
        base,
        adapter,
    ):
        logits = model(
            slots,
            mask,
        )
        assert logits.shape == (
            3,
            32,
        )
