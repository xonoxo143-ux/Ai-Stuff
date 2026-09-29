import random

import torch

from agent_cognition.benchmark import (
    FAMILY_NAMES,
    generate_example,
    oracle_answer,
)
from agent_cognition.models import (
    build_model,
    parameter_count,
)


def test_all_families_generate_shared_shape():
    rng = random.Random(1)
    for family in range(
        len(FAMILY_NAMES)
    ):
        example = generate_example(
            rng,
            family,
        )
        assert example.slots.shape == (
            24,
            6,
        )
        assert example.mask.shape == (24,)
        assert 0 <= example.answer <= 31


def test_models_share_output_contract():
    rng = random.Random(2)
    examples = [
        generate_example(rng)
        for _ in range(4)
    ]
    slots = torch.stack(
        [x.slots for x in examples]
    )
    mask = torch.stack(
        [x.mask for x in examples]
    )

    for name in (
        "flat",
        "factor_onepass",
        "factor",
        "factor_no_reinject",
    ):
        model = build_model(name)
        logits = model(slots, mask)
        assert logits.shape == (4, 32)
        assert (
            parameter_count(model)
            < 1_000_000
        )


def test_recurrent_steps_are_runtime_variable():
    rng = random.Random(3)
    example = generate_example(rng)
    model = build_model("factor")
    one = model(
        example.slots[None],
        example.mask[None],
        steps=1,
    )
    four = model(
        example.slots[None],
        example.mask[None],
        steps=4,
    )
    assert one.shape == four.shape == (
        1,
        32,
    )
    assert not torch.allclose(
        one,
        four,
    )


def test_oracle_matches_generated_labels_iid_and_ood():
    for ood in (False, True):
        rng = random.Random(
            991 if ood else 990
        )
        for family in range(
            len(FAMILY_NAMES)
        ):
            for _ in range(100):
                example = generate_example(
                    rng,
                    family,
                    ood=ood,
                )
                assert (
                    oracle_answer(example)
                    == example.answer
                )
