import copy
import io

import torch

from delta_hybrid.model_v1 import DeltaHybridV1
from delta_hybrid.persistent_state import (
    StatefulDeltaHybridV1,
    state_from_payload,
    state_size_bytes,
    state_to_payload,
)


def make_model(seed=1):
    torch.manual_seed(seed)
    return DeltaHybridV1().double()


def segmented(runner, tokens, sizes):
    state = None
    outputs = []
    start = 0
    for size in sizes:
        stop = start + size
        out, state = runner.forward_segment(tokens[:, start:stop], state)
        outputs.append(out)
        start = stop
    assert start == tokens.shape[1]
    return torch.cat(outputs, dim=1), state
def test_one_shot_stateful_matches_existing_forward():
    model = make_model(11).eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, 41))
    with torch.no_grad():
        expected = model(x)
        got, state = runner.forward_segment(x)
    assert torch.allclose(expected, got, atol=1e-12, rtol=1e-12)
    assert len(state.delta_states) == 3
    assert state.attention.hidden.shape == (2, 41, model.model_dim)


def test_irregular_and_tokenwise_match_one_shot():
    model = make_model(12).eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, 47))
    with torch.no_grad():
        expected = model(x)
        irregular, state = segmented(runner, x, [3, 11, 1, 17, 15])
        tokenwise, _ = segmented(runner, x, [1] * 47)
    assert torch.allclose(expected, irregular, atol=1e-9, rtol=1e-9)
    assert torch.allclose(expected, tokenwise, atol=1e-9, rtol=1e-9)
    assert state_size_bytes(state) > 0
def test_serialized_state_resumes_exactly():
    model = make_model(13).eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, 39))
    with torch.no_grad():
        expected = model(x)
        first, state = runner.forward_segment(x[:, :17])

        buffer = io.BytesIO()
        torch.save(state_to_payload(state), buffer)
        buffer.seek(0)
        restored = state_from_payload(torch.load(buffer, weights_only=True))

        second, _ = runner.forward_segment(x[:, 17:], restored)
        got = torch.cat([first, second], dim=1)

    assert torch.allclose(expected, got, atol=1e-9, rtol=1e-9)


def test_partial_boundary_reset_is_independent_per_batch_row():
    model = make_model(14).eval()
    runner = StatefulDeltaHybridV1(model)
    prefix = torch.randint(0, 256, (2, 13))
    suffix = torch.randint(0, 256, (2, 9))
    with torch.no_grad():
        _, state = runner.forward_segment(prefix)
        got, state = runner.forward_segment(
            suffix,
            state,
            reset_mask=torch.tensor([True, False]),
        )
        fresh_row0 = model(suffix[0:1])
        continued_row1 = model(
            torch.cat([prefix[1:2], suffix[1:2]], dim=1)
        )[:, -suffix.shape[1]:]

    assert torch.allclose(
        got[0:1], fresh_row0, atol=1e-9, rtol=1e-9
    )
    assert torch.allclose(
        got[1:2], continued_row1, atol=1e-9, rtol=1e-9
    )
    assert not bool(state.attention.valid[0, :prefix.shape[1]].any())
    assert bool(state.attention.valid[1, :prefix.shape[1]].all())


def test_segmented_gradient_matches_one_shot():
    base = make_model(15).train()
    segmented_model = copy.deepcopy(base)
    x = torch.randint(0, 256, (1, 17))
    full_logits = base(x)
    full_loss = full_logits.square().mean()
    full_grads = torch.autograd.grad(
        full_loss,
        tuple(base.parameters()),
        allow_unused=False,
    )

    runner = StatefulDeltaHybridV1(segmented_model)
    state = None
    parts = []
    for start, stop in ((0, 5), (5, 11), (11, 17)):
        out, state = runner.forward_segment(x[:, start:stop], state)
        parts.append(out)
    segmented_logits = torch.cat(parts, dim=1)
    segmented_loss = segmented_logits.square().mean()
    segmented_grads = torch.autograd.grad(
        segmented_loss,
        tuple(segmented_model.parameters()),
        allow_unused=False,
    )

    assert torch.allclose(
        full_logits, segmented_logits, atol=1e-9, rtol=1e-9
    )
    for expected, got in zip(full_grads, segmented_grads):
        assert torch.allclose(expected, got, atol=1e-8, rtol=1e-8)
