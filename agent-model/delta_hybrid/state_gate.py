"""Kaggle-CPU gate for DeltaHybrid V1 segmented persistent state."""
from __future__ import annotations

import argparse
import copy
import io
import json
import platform
from pathlib import Path

import torch

from .model_v1 import DeltaHybridV1
from .persistent_state import (
    StatefulDeltaHybridV1,
    state_from_payload,
    state_size_bytes,
    state_to_payload,
)

FORWARD_TOL = 1e-8
GRAD_TOL = 1e-7


def maxerr(a, b):
    return float((a - b).abs().max().item()) if a.numel() else 0.0
def run_segments(runner, x, sizes):
    state = None
    outputs = []
    start = 0
    for size in sizes:
        stop = start + size
        out, state = runner.forward_segment(x[:, start:stop], state)
        outputs.append(out)
        start = stop
    if start != x.shape[1]:
        raise ValueError("segment sizes do not cover sequence")
    return torch.cat(outputs, 1), state


def forward_case(seed, length, sizes):
    torch.manual_seed(seed)
    model = DeltaHybridV1().double().eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, length))
    with torch.no_grad():
        expected = model(x)
        one, one_state = runner.forward_segment(x)
        segmented, seg_state = run_segments(runner, x, sizes)
        tokenwise, token_state = run_segments(runner, x, [1] * length)
    return {
        "one_shot_error": maxerr(expected, one),
        "segmented_error": maxerr(expected, segmented),
        "tokenwise_error": maxerr(expected, tokenwise),
        "final_delta_state_error": max(
            maxerr(a.memory, b.memory)
            for a, b in zip(one_state.delta_states, seg_state.delta_states)
        ),
        "attention_history_error": maxerr(
            one_state.attention.hidden,
            seg_state.attention.hidden,
        ),
        "state_bytes": state_size_bytes(seg_state),
        "finite": bool(
            torch.isfinite(segmented).all()
            and torch.isfinite(tokenwise).all()
        ),
        "token_state_bytes": state_size_bytes(token_state),
    }


def resume_case(seed):
    torch.manual_seed(seed)
    model = DeltaHybridV1().double().eval()
    runner = StatefulDeltaHybridV1(model)
    x = torch.randint(0, 256, (2, 43))
    with torch.no_grad():
        expected = model(x)
        first, state = runner.forward_segment(x[:, :19])
        buffer = io.BytesIO()
        torch.save(state_to_payload(state), buffer)
        buffer.seek(0)
        restored = state_from_payload(
            torch.load(buffer, weights_only=True)
        )
        second, _ = runner.forward_segment(x[:, 19:], restored)
    return maxerr(expected, torch.cat([first, second], 1))


def reset_case(seed):
    torch.manual_seed(seed)
    model = DeltaHybridV1().double().eval()
    runner = StatefulDeltaHybridV1(model)
    prefix = torch.randint(0, 256, (2, 17))
    suffix = torch.randint(0, 256, (2, 11))
    with torch.no_grad():
        _, state = runner.forward_segment(prefix)
        got, state = runner.forward_segment(
            suffix,
            state,
            reset_mask=torch.tensor([True, False]),
        )
        row0 = model(suffix[0:1])
        row1 = model(
            torch.cat([prefix[1:2], suffix[1:2]], dim=1)
        )[:, -suffix.shape[1]:]

    invalid_old = not bool(
        state.attention.valid[0, :prefix.shape[1]].any()
    )
    retained_old = bool(
        state.attention.valid[1, :prefix.shape[1]].all()
    )
    return {
        "row0_error": maxerr(got[0:1], row0),
        "row1_error": maxerr(got[1:2], row1),
        "invalidated_reset_history": invalid_old,
        "retained_other_history": retained_old,
    }


def gradient_case(seed):
    torch.manual_seed(seed)
    base = DeltaHybridV1().double().train()
    other = copy.deepcopy(base)
    x = torch.randint(0, 256, (1, 19))
    expected = base(x)
    loss = expected.square().mean()
    grads0 = torch.autograd.grad(
        loss, tuple(base.parameters()), allow_unused=False
    )

    runner = StatefulDeltaHybridV1(other)
    state = None
    parts = []
    for start, stop in ((0, 4), (4, 12), (12, 19)):
        out, state = runner.forward_segment(x[:, start:stop], state)
        parts.append(out)
    got = torch.cat(parts, 1)
    loss2 = got.square().mean()
    grads1 = torch.autograd.grad(
        loss2, tuple(other.parameters()), allow_unused=False
    )

    grad_error = max(maxerr(a, b) for a, b in zip(grads0, grads1))
    return {
        "output_error": maxerr(expected, got),
        "gradient_error": grad_error,
        "finite": all(torch.isfinite(g).all() for g in grads1),
    }
def run_gate():
    cases = []
    specs = [
        (31, [3, 7, 1, 9, 11]),
        (47, [13, 2, 16, 5, 11]),
        (65, [1, 8, 17, 4, 20, 15]),
    ]
    for seed in (101, 202, 303):
        for length, sizes in specs:
            cases.append(forward_case(seed + length, length, sizes))

    resumes = [resume_case(seed) for seed in (401, 402, 403)]
    resets = [reset_case(seed) for seed in (501, 502, 503)]
    gradients = [gradient_case(seed) for seed in (601, 602)]

    maxima = {
        "one_shot": max(x["one_shot_error"] for x in cases),
        "segmented": max(x["segmented_error"] for x in cases),
        "tokenwise": max(x["tokenwise_error"] for x in cases),
        "delta_state": max(x["final_delta_state_error"] for x in cases),
        "attention_history": max(x["attention_history_error"] for x in cases),
        "resume": max(resumes),
        "reset": max(max(x["row0_error"], x["row1_error"]) for x in resets),
        "gradient_output": max(x["output_error"] for x in gradients),
        "gradient": max(x["gradient_error"] for x in gradients),
    }
    passed = (
        all(x["finite"] for x in cases)
        and all(x["finite"] for x in gradients)
        and all(x["invalidated_reset_history"] for x in resets)
        and all(x["retained_other_history"] for x in resets)
        and all(
            maxima[k] <= FORWARD_TOL
            for k in (
                "one_shot",
                "segmented",
                "tokenwise",
                "delta_state",
                "attention_history",
                "resume",
                "reset",
                "gradient_output",
            )
        )
        and maxima["gradient"] <= GRAD_TOL
    )

    return {
        "experiment_id": "delta-v1-persistent-state-cpu-gate",
        "passed": passed,
        "forward_cases": len(cases),
        "resume_cases": len(resumes),
        "reset_cases": len(resets),
        "gradient_cases": len(gradients),
        "forward_tolerance": FORWARD_TOL,
        "gradient_tolerance": GRAD_TOL,
        "max_errors": maxima,
        "max_state_bytes": max(x["state_bytes"] for x in cases),
        "max_token_state_bytes": max(
            x["token_state_bytes"] for x in cases
        ),
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "device": "cpu",
        "state_contract": (
            "three Delta matrices + exact-attention hidden history/validity"
        ),
        "reset_contract": "per-batch-row reset at segment boundary",
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
