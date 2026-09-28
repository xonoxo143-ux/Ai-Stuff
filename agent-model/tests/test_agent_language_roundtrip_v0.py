import torch

from agent_language.roundtrip_probe import (
    predicted_conditions,
)


def test_predicted_conditions_are_bounded():
    logits = torch.randn(
        3,
        4,
        4,
    )
    hard, soft = (
        predicted_conditions(
            logits
        )
    )
    assert hard.shape == (
        3,
        16,
    )
    assert soft.shape == (
        3,
        16,
    )
    assert torch.allclose(
        hard.view(
            3,
            4,
            4,
        ).sum(-1),
        torch.ones(
            3,
            4,
        ),
    )
    assert torch.allclose(
        soft.view(
            3,
            4,
            4,
        ).sum(-1),
        torch.ones(
            3,
            4,
        ),
        atol=1e-6,
    )
