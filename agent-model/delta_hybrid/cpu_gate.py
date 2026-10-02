[Reading 191 lines from start (total: 191 lines, 0 remaining)]

"""Kaggle-CPU correctness gate for the DeltaHybrid V1 reference recurrence."""
import argparse
import json
import platform
from pathlib import Path

import torch

from .delta_reference import (
    DeltaState,
    deserialize_state,
    scan,
    serialize_state,
    step,
    zero_state,
)

ATOL = 1e-10
RTOL = 1e-10


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
def maxerr(a, b):
    return float((a - b).abs().max().item())


def run_case(seed, batch, steps, d_key, d_value):
    xs = make_inputs(seed, batch, steps, d_key, d_value)
    reference_y, reference_state = scan(*xs)

    stream_state = zero_state(batch, d_value, d_key, dtype=torch.float64)
    stream_outputs = []
    for t in range(steps):
        out, stream_state = step(
            xs[0][:, t], xs[1][:, t], xs[2][:, t],
            xs[3][:, t], xs[4][:, t], stream_state,
        )
        stream_outputs.append(out)
    stream_y = torch.stack(stream_outputs, 1)

    chunk_state = None
    chunk_outputs = []
    chunk = max(1, steps // 3)
    for start in range(0, steps, chunk):
        stop = min(steps, start + chunk)
        out, chunk_state = scan(
            *(x[:, start:stop] for x in xs), state=chunk_state
        )
        chunk_outputs.append(out)
    chunk_y = torch.cat(chunk_outputs, 1)

    output_error = max(maxerr(reference_y, stream_y), maxerr(reference_y, chunk_y))
    state_error = max(
        maxerr(reference_state.memory, stream_state.memory),
        maxerr(reference_state.memory, chunk_state.memory),
    )

    if steps > 1:
        cut = max(1, steps // 2)
        changed = [x.clone() for x in xs]
        for x in changed:
            x[:, cut:] += 777.0
        changed_y, _ = scan(*changed)
        causal_error = maxerr(reference_y[:, :cut], changed_y[:, :cut])
    else:
        causal_error = 0.0

    reset_error = 0.0
    resume_error = 0.0
    if steps > 1:
        cut = max(1, steps // 2)
        reset = torch.zeros(batch, steps, dtype=torch.bool)
        reset[:, cut] = True
        reset_y, _ = scan(*xs, reset=reset)
        suffix_y, _ = scan(*(x[:, cut:] for x in xs))
        reset_error = maxerr(reset_y[:, cut:], suffix_y)
        first_y, partial = scan(*(x[:, :cut] for x in xs))
        restored = deserialize_state(serialize_state(partial))
        second_y, resumed = scan(*(x[:, cut:] for x in xs), state=restored)
        resume_error = max(
            maxerr(reference_y, torch.cat([first_y, second_y], 1)),
            maxerr(reference_state.memory, resumed.memory),
        )

    return {
        "output_error": output_error,
        "state_error": state_error,
        "causal_error": causal_error,
        "reset_error": reset_error,
        "resume_error": resume_error,
        "finite": bool(
            torch.isfinite(reference_y).all()
            and torch.isfinite(reference_state.memory).all()
        ),
    }


def expanded_equation_error(seed):
    q, k, v, beta, decay = make_inputs(seed, 3, 1, 5, 4)
    state = DeltaState(torch.randn(3, 4, 5, dtype=torch.float64))
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
    return max(maxerr(got.memory, expected), maxerr(y, expected_y))


def gradient_ok(seed):
    xs = make_inputs(seed, 2, 13, 4, 6, grad=True)
    y, state = scan(*xs)
    loss = y.square().mean() + state.memory.square().mean()
    loss.backward()
    return bool(
        torch.isfinite(loss)
        and all(x.grad is not None and torch.isfinite(x.grad).all() for x in xs)
    )


def run_gate():
    results = []
    for seed in range(8):
        for batch in (1, 3):
            for steps in (1, 2, 7, 31):
                for d_key, d_value in ((3, 5), (4, 4)):
                    results.append(run_case(seed, batch, steps, d_key, d_value))
    maxima = {
        key: max(r[key] for r in results)
        for key in (
            "output_error", "state_error", "causal_error",
            "reset_error", "resume_error",
        )
    }
    equation_error = max(expanded_equation_error(seed) for seed in range(8))
    gradients = all(gradient_ok(seed) for seed in range(8))

    passed = (
        all(r["finite"] for r in results)
        and gradients
        and equation_error <= ATOL
        and all(value <= ATOL for value in maxima.values())
    )
    return {
        "experiment_id": "delta-v1-reference-cpu-gate",
        "passed": passed,
        "reference_cases": len(results),
        "gradient_cases": 8,
        "equation_cases": 8,
        "atol": ATOL,
        "rtol": RTOL,
        "max_errors": maxima,
        "expanded_equation_max_error": equation_error,
        "finite_gradients": gradients,
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "device": "cpu",
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
