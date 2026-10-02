[Reading 139 lines from start (total: 139 lines, 0 remaining)]

import torch

from delta_hybrid.delta_reference import (
    DeltaState,
    deserialize_state,
    scan,
    serialize_state,
    step,
    zero_state,
)


def inputs(seed=7, batch=2, steps=7, d_key=4, d_value=5):
    g = torch.Generator().manual_seed(seed)
    args = [
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_value, generator=g, dtype=torch.float64),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
    ]
    return args
def test_hand_scalar():
    state = DeltaState(torch.zeros(1, 1, 1, dtype=torch.float64))
    y, state = step(
        torch.ones(1, 1, dtype=torch.float64),
        torch.ones(1, 1, dtype=torch.float64),
        torch.tensor([[2.0]], dtype=torch.float64),
        torch.tensor([0.5], dtype=torch.float64),
        torch.tensor([1.0], dtype=torch.float64),
        state,
    )
    assert torch.equal(state.memory, torch.tensor([[[1.0]]], dtype=torch.float64))
    assert torch.equal(y, torch.tensor([[1.0]], dtype=torch.float64))


def test_update_matches_expanded_paper_equation():
    q, k, v, beta, decay = inputs(11, batch=2, steps=1, d_key=3, d_value=5)
    state = DeltaState(torch.randn(2, 5, 3, dtype=torch.float64))
    y, got = step(q[:, 0], k[:, 0], v[:, 0], beta[:, 0], decay[:, 0], state)

    qn = torch.nn.functional.normalize(q[:, 0], dim=-1)
    kn = torch.nn.functional.normalize(k[:, 0], dim=-1)
    a = decay[:, 0].view(-1, 1, 1)
    b = beta[:, 0].view(-1, 1, 1)
    sk = torch.bmm(state.memory, kn.unsqueeze(-1)).squeeze(-1)
    expected = (
        a * state.memory
        - a * b * sk.unsqueeze(-1) * kn.unsqueeze(1)
        + b * v[:, 0].unsqueeze(-1) * kn.unsqueeze(1)
    )
    expected_y = torch.bmm(expected, qn.unsqueeze(-1)).squeeze(-1)

    assert torch.allclose(got.memory, expected, atol=1e-12, rtol=1e-12)
    assert torch.allclose(y, expected_y, atol=1e-12, rtol=1e-12)


def test_causal_prefix_ignores_future_inputs():
    xs = inputs(13, steps=9)
    y, _ = scan(*xs)
    changed = [x.clone() for x in xs]
    for x in changed:
        x[:, 5:] += 1000.0
    y2, _ = scan(*changed)
    assert torch.equal(y[:, :5], y2[:, :5])
def test_finite_gradients():
    xs = [x.requires_grad_() for x in inputs(17)]
    y, state = scan(*xs)
    (y.square().mean() + state.memory.square().mean()).backward()
    assert torch.isfinite(y).all()
    assert all(
        x.grad is not None and torch.isfinite(x.grad).all()
        for x in xs
    )


def test_streaming_matches_reference_scan():
    xs = inputs(19, batch=3, steps=11, d_key=3, d_value=6)
    y, state = scan(*xs)
    stream_state = zero_state(3, 6, 3, dtype=torch.float64)
    outputs = []
    for t in range(11):
        out, stream_state = step(
            xs[0][:, t], xs[1][:, t], xs[2][:, t],
            xs[3][:, t], xs[4][:, t], stream_state,
        )
        outputs.append(out)
    stream_y = torch.stack(outputs, dim=1)
    assert torch.allclose(y, stream_y, atol=1e-12, rtol=1e-12)
    assert torch.allclose(
        state.memory, stream_state.memory, atol=1e-12, rtol=1e-12
    )


def test_chunked_matches_unchunked():
    xs = inputs(23, steps=17, d_key=5, d_value=3)
    y, state = scan(*xs)
    chunk_state = None
    parts = []
    for start in range(0, 17, 4):
        stop = min(17, start + 4)
        out, chunk_state = scan(
            *(x[:, start:stop] for x in xs), state=chunk_state
        )
        parts.append(out)
    chunk_y = torch.cat(parts, dim=1)
    assert torch.allclose(y, chunk_y, atol=1e-12, rtol=1e-12)
    assert torch.allclose(
        state.memory, chunk_state.memory, atol=1e-12, rtol=1e-12
    )
def test_reset_matches_fresh_suffix():
    xs = inputs(29, batch=1, steps=8)
    reset = torch.zeros(1, 8, dtype=torch.bool)
    reset[:, 4] = True
    y, _ = scan(*xs, reset=reset)
    suffix, _ = scan(*(x[:, 4:] for x in xs))
    assert torch.allclose(y[:, 4:], suffix, atol=1e-12, rtol=1e-12)


def test_state_roundtrip_resume_and_no_aliasing():
    xs = inputs(31, steps=8)
    y, state = scan(*xs)
    first, partial = scan(*(x[:, :3] for x in xs))
    serialized = serialize_state(partial)
    restored = deserialize_state(serialized)
    assert restored.memory.data_ptr() != serialized.data_ptr()

    second, resumed = scan(*(x[:, 3:] for x in xs), state=restored)
    assert torch.allclose(y, torch.cat([first, second], 1), atol=1e-12, rtol=1e-12)
    assert torch.allclose(state.memory, resumed.memory, atol=1e-12, rtol=1e-12)


def test_seeded_determinism():
    a = inputs(seed=123)
    b = inputs(seed=123)
    ya, sa = scan(*a)
    yb, sb = scan(*b)
    assert torch.equal(ya, yb)
    assert torch.equal(sa.memory, sb.memory)

[executed on device: optiplex-ai (fbcbb933-7ca0-4279-8624-6a1cd3f388d1)]