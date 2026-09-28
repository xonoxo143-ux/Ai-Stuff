import torch

from agent_language.data import (
    ByteBatchStream,
    make_micro_english,
)
from agent_language.models import (
    build_model,
    parameter_count,
)


def test_micro_corpus_is_deterministic_and_seed_sensitive():
    assert (
        make_micro_english(1, 10)
        == make_micro_english(1, 10)
    )
    assert (
        make_micro_english(1, 10)
        != make_micro_english(2, 10)
    )


def test_all_models_match_byte_logits_contract():
    x = torch.randint(
        0,
        256,
        (2, 16),
    )
    condition = torch.randn(2, 16)
    for name in (
        "gru",
        "transformer",
        "patch_rnn",
    ):
        model = build_model(name)
        logits = model(
            x,
            condition,
        )
        assert logits.shape == (
            2,
            16,
            256,
        )
        assert (
            100_000
            <= parameter_count(model)
            <= 200_000
        )


def test_external_conditioning_changes_output():
    x = torch.randint(
        0,
        256,
        (2, 16),
    )
    for name in (
        "gru",
        "transformer",
        "patch_rnn",
    ):
        model = build_model(name)
        with torch.no_grad():
            a = model(
                x,
                torch.zeros(2, 16),
            )
            b = model(
                x,
                torch.ones(2, 16),
            )
        assert float(
            (a - b).abs().mean()
        ) > 0.0


def test_batch_stream_is_reproducible():
    data = make_micro_english(
        3,
        30,
    )
    a = ByteBatchStream(
        data,
        seed=7,
    )
    b = ByteBatchStream(
        data,
        seed=7,
    )
    ax, ay = a.batch(3, 16)
    bx, by = b.batch(3, 16)
    assert torch.equal(ax, bx)
    assert torch.equal(ay, by)
