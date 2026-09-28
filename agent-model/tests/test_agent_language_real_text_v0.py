import torch

from agent_language.models import (
    build_model,
    parameter_count,
)


def test_small_real_text_models_are_comparable_scale():
    gru = build_model(
        "gru",
        scale="small",
    )
    transformer = build_model(
        "transformer",
        scale="small",
    )
    assert (
        700_000
        <= parameter_count(gru)
        <= 900_000
    )
    assert (
        850_000
        <= parameter_count(
            transformer
        )
        <= 1_000_000
    )


def test_small_models_keep_conditioning_contract():
    tokens = torch.randint(
        0,
        256,
        (2, 32),
    )
    condition = torch.randn(
        2,
        16,
    )
    for name in (
        "gru",
        "transformer",
    ):
        model = build_model(
            name,
            scale="small",
        )
        logits = model(
            tokens,
            condition,
        )
        assert logits.shape == (
            2,
            32,
            256,
        )
