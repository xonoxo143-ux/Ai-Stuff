"""CPU preflight for bounded exact-attention history in persistent Delta."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import torch

from .model_v1 import DeltaHybridV1
from .persistent_state import StatefulDeltaHybridV1, state_size_bytes


def run_stream(runner, tokens, segment_size):
    state = None
    outputs_finite = True
    sizes = []
    for start in range(0, tokens.shape[1], segment_size):
        stop = min(tokens.shape[1], start + segment_size)
        out, state = runner.forward_segment(tokens[:, start:stop], state)
        outputs_finite = outputs_finite and bool(torch.isfinite(out).all())
        sizes.append(state_size_bytes(state))
    return state, sizes, outputs_finite


def run_gate():
    torch.manual_seed(20261002)
    model = DeltaHybridV1().eval()
    batch = 2
    segment = 128
    short = torch.randint(0, 256, (batch, 512))
    long = torch.randint(0, 256, (batch, 2048))

    bounded = StatefulDeltaHybridV1(model, max_attention_history=128)
    short_state, short_sizes, short_finite = run_stream(
        bounded, short, segment
    )
    long_state, long_sizes, long_finite = run_stream(
        bounded, long, segment
    )

    recurrent_only = StatefulDeltaHybridV1(model, max_attention_history=0)
    zero_state, zero_sizes, zero_finite = run_stream(
        recurrent_only, long, segment
    )

    unlimited = StatefulDeltaHybridV1(model)
    unlimited_state, unlimited_sizes, unlimited_finite = run_stream(
        unlimited, short, segment
    )

    bounded_len = short_state.attention.hidden.shape[1]
    bounded_long_len = long_state.attention.hidden.shape[1]
    zero_len = zero_state.attention.hidden.shape[1]
    unlimited_len = unlimited_state.attention.hidden.shape[1]
    plateau = (
        short_sizes[-1] == long_sizes[-1]
        and all(size == short_sizes[-1] for size in long_sizes[1:])
    )
    bounded_ok = bounded_len == 128 and bounded_long_len == 128
    zero_ok = zero_len == 0
    unlimited_grows = unlimited_len == 512 and unlimited_sizes[-1] > unlimited_sizes[0]

    finite = short_finite and long_finite and zero_finite and unlimited_finite
    passed = plateau and bounded_ok and zero_ok and unlimited_grows and finite

    return {
        "experiment_id": "delta-v1-bounded-attention-history-cpu-gate",
        "passed": passed,
        "batch": batch,
        "segment_size": segment,
        "attention_history_limit": 128,
        "bounded_history_length_512": bounded_len,
        "bounded_history_length_2048": bounded_long_len,
        "recurrent_only_history_length": zero_len,
        "unlimited_history_length_512": unlimited_len,
        "bounded_state_bytes_512": short_sizes[-1],
        "bounded_state_bytes_2048": long_sizes[-1],
        "recurrent_only_state_bytes_2048": zero_sizes[-1],
        "unlimited_state_bytes_512": unlimited_sizes[-1],
        "bounded_plateau": plateau,
        "finite": finite,
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
