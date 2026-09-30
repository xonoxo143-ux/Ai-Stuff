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
