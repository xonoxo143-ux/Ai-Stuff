import torch

from agent_language.perception_probe import (
    VALID_TEMPLATES,
    build_perceiver,
    encode_bytes,
    parameter_count,
    render,
    semantic_labels,
    semantic_split,
)


def test_semantic_split_holds_out_combinations():
    train, valid = semantic_split()
    assert len(train) == 192
    assert len(valid) == 64
    assert not (
        set(train)
        & set(valid)
    )


def test_perceiver_contracts_match():
    texts = [
        render(
            semantic_split()[0][0],
            VALID_TEMPLATES[0],
        ),
        render(
            semantic_split()[0][1],
            VALID_TEMPLATES[1],
        ),
    ]
    tokens, mask = encode_bytes(texts)
    for name in (
        "gru",
        "bigru",
        "transformer",
    ):
        model = build_perceiver(
            name
        )
        logits = model(
            tokens,
            mask,
        )
        assert logits.shape == (
            2,
            4,
            4,
        )
        assert (
            80_000
            <= parameter_count(model)
            <= 160_000
        )


def test_semantic_labels_are_bounded_slots():
    train, _ = semantic_split()
    target = semantic_labels(
        train[0]
    )
    assert target.shape == (4,)
    assert bool(
        ((target >= 0)
        & (target < 4)).all()
    )
