"""Kaggle-CPU parity gate for the chunk-parallel Gated-Delta path."""
import argparse
import json
import platform
from pathlib import Path

import torch

from .delta_chunk import chunk_parallel_scan
from .delta_reference import DeltaState, scan

FORWARD_TOL = 1e-10
GRAD_TOL = 1e-9


def make_inputs(seed, batch, steps, d_key, d_value, grad=False):
    g = torch.Generator().manual_seed(seed)
    xs = [
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_key, generator=g, dtype=torch.float64),
        torch.randn(batch, steps, d_value, generator=g, dtype=torch.float64),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
        torch.sigmoid(torch.randn(batch, steps, generator=g, dtype=torch.float64)),
    ]
    if grad:
        xs = [x.requires_grad_() for x in xs]
    return xs


def make_state(seed, batch, d_value, d_key, grad=False):
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(
        batch, d_value, d_key, generator=g, dtype=torch.float64
    )
    if grad:
        x.requires_grad_()
    return x


def maxerr(a, b):
    return float((a - b).abs().max().item()) if a.numel() else 0.0


def forward_case(seed, batch, steps, d_key, d_value, chunk_size):
    xs = make_inputs(seed, batch, steps, d_key, d_value)
    state0 = make_state(seed + 1000, batch, d_value, d_key)
    ref_y, ref_s = scan(*xs, state=DeltaState(state0))
    got_y, got_s = chunk_parallel_scan(
        *xs, state=DeltaState(state0), chunk_size=chunk_size
    )
    return {
        "output_error": maxerr(ref_y, got_y),
        "state_error": maxerr(ref_s.memory, got_s.memory),
        "finite": bool(
            torch.isfinite(got_y).all()
            and torch.isfinite(got_s.memory).all()
        ),
    }


def reset_case(seed):
    batch, steps, d_key, d_value = 3, 23, 4, 5
    xs = make_inputs(seed, batch, steps, d_key, d_value)
    state0 = make_state(seed + 2000, batch, d_value, d_key)
    reset = torch.zeros(batch, steps, dtype=torch.bool)
    reset[0, 3] = True
    reset[1, 9] = True
    reset[2, 17] = True
    ref_y, ref_s = scan(*xs, state=DeltaState(state0), reset=reset)
    got_y, got_s = chunk_parallel_scan(
        *xs, state=DeltaState(state0), chunk_size=7, reset=reset
    )
    return max(maxerr(ref_y, got_y), maxerr(ref_s.memory, got_s.memory))


def loss_and_grads(kind, seed):
    batch, steps, d_key, d_value = 2, 17, 4, 6
    xs = make_inputs(seed, batch, steps, d_key, d_value, grad=True)
    state = make_state(seed + 3000, batch, d_value, d_key, grad=True)
    wrapped = DeltaState(state)
    if kind == "reference":
        y, out_state = scan(*xs, state=wrapped)
    else:
        y, out_state = chunk_parallel_scan(
            *xs, state=wrapped, chunk_size=5
        )
    loss = y.square().mean() + out_state.memory.square().mean()
    grads = torch.autograd.grad(loss, [*xs, state])
    return y.detach(), out_state.memory.detach(), grads
def gradient_case(seed):
    y0, s0, g0 = loss_and_grads("reference", seed)
    y1, s1, g1 = loss_and_grads("chunk", seed)
    return {
        "output_error": maxerr(y0, y1),
        "state_error": maxerr(s0, s1),
        "gradient_error": max(maxerr(a, b) for a, b in zip(g0, g1)),
        "finite": all(torch.isfinite(g).all() for g in g1),
    }


def run_gate():
    forward = []
    shapes = [
        (1, 1, 3, 5),
        (2, 2, 4, 4),
        (7, 3, 5, 3),
        (17, 4, 4, 6),
        (31, 8, 3, 5),
        (65, 16, 5, 4),
    ]
    for seed in range(6):
        for batch in (1, 3):
            for steps, chunk, d_key, d_value in shapes:
                forward.append(
                    forward_case(
                        seed, batch, steps, d_key, d_value, chunk
                    )
                )

    resets = [reset_case(seed) for seed in range(8)]
    gradients = [gradient_case(seed) for seed in range(8)]

    forward_output = max(x["output_error"] for x in forward)
    forward_state = max(x["state_error"] for x in forward)
    reset_error = max(resets)
    grad_output = max(x["output_error"] for x in gradients)
    grad_state = max(x["state_error"] for x in gradients)
    grad_error = max(x["gradient_error"] for x in gradients)

    passed = (
        all(x["finite"] for x in forward)
        and all(x["finite"] for x in gradients)
        and forward_output <= FORWARD_TOL
        and forward_state <= FORWARD_TOL
        and reset_error <= FORWARD_TOL
        and grad_output <= FORWARD_TOL
        and grad_state <= FORWARD_TOL
        and grad_error <= GRAD_TOL
    )

    return {
        "experiment_id": "delta-v1-chunk-equivalence-cpu-gate",
        "passed": passed,
        "forward_cases": len(forward),
        "reset_cases": len(resets),
        "gradient_cases": len(gradients),
        "forward_tolerance": FORWARD_TOL,
        "gradient_tolerance": GRAD_TOL,
        "max_forward_output_error": forward_output,
        "max_forward_state_error": forward_state,
        "max_reset_error": reset_error,
        "max_gradient_output_error": grad_output,
        "max_gradient_state_error": grad_state,
        "max_gradient_error": grad_error,
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "device": "cpu",
        "parallel_form": "WY/UT triangular solves + batched matmuls",
        "reset_policy": "serial oracle fallback only for reset-bearing chunks",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = run_gate()
    payload = json.dumps(summary, indent=2, sort_keys=True)
    print(payload, flush=True)
    if args.output:
        args.output.write_text(payload + "\n")
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
