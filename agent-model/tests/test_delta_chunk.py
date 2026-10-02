import torch

from delta_hybrid.delta_chunk import chunk_parallel_scan, chunk_step_parallel
from delta_hybrid.delta_reference import DeltaState, scan


def make(seed=1, batch=2, steps=11, d_key=4, d_value=5):
    g = torch.Generator().manual_seed(seed)
    return [
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_value, generator=g, dtype=torch.float64),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
    ]


def initial(seed, batch, d_value, d_key):
    g = torch.Generator().manual_seed(seed)
    return DeltaState(
        torch.randn(batch, d_value, d_key, generator=g, dtype=torch.float64)
    )


def test_single_chunk_matches_oracle():
    xs = make(3, batch=3, steps=9, d_key=5, d_value=4)
    s0 = initial(4, 3, 4, 5)
    expected_y, expected_s = scan(*xs, state=s0)
    got_y, got_s = chunk_step_parallel(*xs, state=s0)
    assert torch.allclose(expected_y, got_y, atol=1e-10, rtol=1e-10)
    assert torch.allclose(
        expected_s.memory, got_s.memory, atol=1e-10, rtol=1e-10
    )


def test_multi_chunk_and_tail_match_oracle():
    xs = make(5, steps=37, d_key=3, d_value=6)
    s0 = initial(6, 2, 6, 3)
    expected_y, expected_s = scan(*xs, state=s0)
    got_y, got_s = chunk_parallel_scan(*xs, state=s0, chunk_size=8)
    assert torch.allclose(expected_y, got_y, atol=1e-10, rtol=1e-10)
    assert torch.allclose(
        expected_s.memory, got_s.memory, atol=1e-10, rtol=1e-10
    )


def test_reset_fallback_matches_oracle():
    xs = make(7, batch=3, steps=19)
    reset = torch.zeros(3, 19, dtype=torch.bool)
    reset[0, 3] = True
    reset[1, 8] = True
    reset[2, 13] = True
    expected_y, expected_s = scan(*xs, reset=reset)
    got_y, got_s = chunk_parallel_scan(
        *xs, chunk_size=6, reset=reset
    )
    assert torch.allclose(expected_y, got_y, atol=1e-10, rtol=1e-10)
    assert torch.allclose(
        expected_s.memory, got_s.memory, atol=1e-10, rtol=1e-10
    )


def _loss_and_grads(fn, xs, s0):
    vars_ = [x.detach().clone().requires_grad_() for x in xs]
    state_tensor = s0.memory.detach().clone().requires_grad_()
    y, state = fn(*vars_, state=DeltaState(state_tensor))
    loss = y.square().mean() + state.memory.square().mean()
    grads = torch.autograd.grad(loss, [*vars_, state_tensor])
    return y.detach(), state.memory.detach(), grads


def test_gradients_match_oracle():
    xs = make(11, batch=2, steps=13, d_key=4, d_value=3)
    s0 = initial(12, 2, 3, 4)

    ref = lambda *a, state: scan(*a, state=state)
    fast = lambda *a, state: chunk_parallel_scan(
        *a, state=state, chunk_size=5
    )
    y0, s0_out, g0 = _loss_and_grads(ref, xs, s0)
    y1, s1_out, g1 = _loss_and_grads(fast, xs, s0)
    assert torch.allclose(y0, y1, atol=1e-10, rtol=1e-10)
    assert torch.allclose(s0_out, s1_out, atol=1e-10, rtol=1e-10)
    for expected, got in zip(g0, g1):
        assert torch.allclose(expected, got, atol=1e-9, rtol=1e-9)
