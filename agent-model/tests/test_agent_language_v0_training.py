from __future__ import annotations

import torch

from agent_language.build_v0_corpus import (
    planner_records,
    reasoning_records,
    stable_bucket,
)
from agent_language.v0_model import BytePatchHybridV0


def test_v0_hybrid_forward_and_cached_stream() -> None:
    torch.manual_seed(7)
    model = BytePatchHybridV0(
        embedding_dim=16,
        local_hidden_dim=24,
        global_hidden_dim=32,
        patch_size=4,
        attention_heads=4,
        attention_patches=8,
        condition_dim=4,
    )
    tokens = torch.randint(0, 256, (2, 16))
    logits = model(tokens)
    assert logits.shape == (2, 16, 256)
    assert torch.isfinite(logits).all()

    generated = model.generate("abc", max_new_bytes=9)
    assert generated.startswith(b"abc")
    assert len(generated) == 12


def test_v0_generated_data_is_seeded_and_varied() -> None:
    a = reasoning_records(100, 80)
    b = reasoning_records(101, 80)
    p = planner_records(200, 80)
    assert a == reasoning_records(100, 80)
    assert a != b
    assert len(set(a)) > 60
    assert len(set(p)) > 60


def test_stable_bucket_is_reproducible() -> None:
    assert stable_bucket("tree-123") == stable_bucket("tree-123")
    assert 0 <= stable_bucket("tree-456") < 10


def test_v0_control_is_parameter_matched() -> None:
    from agent_language.train_v0 import build_model
    from agent_language.v0_model import parameter_count

    hybrid = parameter_count(build_model("hybrid"))
    control = parameter_count(build_model("transformer"))
    assert abs(hybrid - control) / hybrid < 0.02


def test_curriculum_batch_counts_are_exact() -> None:
    from agent_language.curriculum import allocate_counts

    assert allocate_counts(
        {"prose": 0.75, "dialogue": 0.25},
        64,
    ) == {"prose": 48, "dialogue": 16}
    assert allocate_counts(
        {
            "prose": 0.45,
            "dialogue": 0.40,
            "reasoning": 0.10,
            "planner": 0.05,
        },
        64,
    ) == {
        "prose": 29,
        "dialogue": 26,
        "reasoning": 6,
        "planner": 3,
    }


def test_throughput_equivalent_token_rate() -> None:
    from agent_language.train_v0 import throughput

    got = throughput(4000, 2.0)
    assert got["train_bytes_per_sec"] == 2000.0
    assert got["train_equiv_tokens_per_sec"] == 500.0


def test_byte_stream_keeps_corpus_compact() -> None:
    from agent_language.data import ByteBatchStream

    stream = ByteBatchStream(bytes(range(256)) * 20, seed=1)
    assert stream.data.dtype == torch.uint8
    x, y = stream.batch(3, 32)
    assert x.dtype == torch.long
    assert y.dtype == torch.long
    assert x.shape == (3, 32)
    assert y.shape == (3, 32)


def test_v0_vectorized_forward_matches_reference_exactly() -> None:
    torch.manual_seed(17)
    model = BytePatchHybridV0(
        embedding_dim=16,
        local_hidden_dim=24,
        global_hidden_dim=32,
        patch_size=4,
        attention_heads=4,
        attention_patches=8,
        condition_dim=4,
    )
    tokens = torch.randint(0, 256, (3, 16))
    condition = torch.randn(3, 4)

    model.set_vectorized_forward(False)
    reference = model(tokens, condition)
    model.set_vectorized_forward(True)
    vectorized = model(tokens, condition)

    assert torch.equal(reference, vectorized)


def test_v0_batch_forward_matches_stream_after_each_byte() -> None:
    torch.manual_seed(23)
    model = BytePatchHybridV0(
        embedding_dim=16,
        local_hidden_dim=24,
        global_hidden_dim=32,
        patch_size=4,
        attention_heads=4,
        attention_patches=8,
        condition_dim=4,
    ).eval()
    tokens = torch.randint(0, 256, (1, 16))
    condition = torch.randn(1, 4)

    with torch.no_grad():
        batch_logits = model(tokens, condition)
        state = model.begin_stream(condition)
        stream_logits = []
        for value in tokens[0].tolist():
            model.accept_byte(state, value)
            stream_logits.append(state.next_logits.clone())
        stream_logits = torch.stack(stream_logits, dim=1)

    assert torch.allclose(batch_logits, stream_logits, atol=1e-6, rtol=1e-5)
