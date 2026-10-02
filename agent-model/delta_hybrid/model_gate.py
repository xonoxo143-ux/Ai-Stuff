"""Kaggle-CPU construction/smoke gate for DeltaHybrid V1."""
from __future__ import annotations

import argparse
import io
import json
import platform
from pathlib import Path

import torch
import torch.nn.functional as F

from agent_language.models import ByteTransformer
from .model_v1 import (
    CONTROL_PARAMETERS,
    DeltaHybridV1,
    parameter_count,
)

PARAM_TOLERANCE = 0.02
CAUSAL_TOLERANCE = 1e-6


def control_model() -> ByteTransformer:
    return ByteTransformer(
        model_dim=128,
        layers=5,
        heads=4,
        feedforward_dim=480,
        max_length=256,
        condition_dim=16,
    )
def random_tokens(seed: int, batch: int, length: int) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randint(0, 256, (batch, length), generator=g)


def maxerr(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a - b).abs().max().item()) if a.numel() else 0.0


def construction_checks(model: DeltaHybridV1) -> dict:
    shape_cases = {}
    finite = True
    for length in (1, 7, 64, 128, 131):
        x = random_tokens(100 + length, 2, length)
        y = model(x)
        shape_cases[str(length)] = list(y.shape)
        finite = finite and bool(torch.isfinite(y).all())

    x = random_tokens(333, 2, 31)
    zeros = torch.zeros(2, model.condition_dim)
    explicit_zero = model(x, zeros)
    implicit_zero = model(x)
    condition_zero_error = maxerr(explicit_zero, implicit_zero)
    nonzero = torch.ones(2, model.condition_dim)
    condition_effect = maxerr(model(x, nonzero), implicit_zero)

    return {
        "shape_cases": shape_cases,
        "finite_forward": finite,
        "condition_zero_error": condition_zero_error,
        "condition_effect": condition_effect,
    }


def causal_check(model: DeltaHybridV1) -> float:
    x = random_tokens(444, 2, 97)
    base = model(x)
    changed = x.clone()
    changed[:, 53:] = random_tokens(445, 2, 44)
    perturbed = model(changed)
    return maxerr(base[:, :53], perturbed[:, :53])


def gradient_check(model: DeltaHybridV1) -> dict:
    model.zero_grad(set_to_none=True)
    x = random_tokens(555, 2, 41)
    y = random_tokens(556, 2, 41)
    logits = model(x)
    loss = F.cross_entropy(logits.reshape(-1, 256), y.reshape(-1))
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.requires_grad]
    finite = all(
        g is not None and torch.isfinite(g).all()
        for g in grads
    )
    norm = torch.sqrt(
        sum((g.detach().float().square().sum() for g in grads))
    )
    return {
        "loss_nats": float(loss.detach()),
        "finite_gradients": bool(finite),
        "gradient_l2": float(norm),
    }


def checkpoint_check(model: DeltaHybridV1) -> float:
    x = random_tokens(666, 2, 37)
    with torch.no_grad():
        before = model(x)
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    buffer.seek(0)
    clone = DeltaHybridV1()
    clone.load_state_dict(torch.load(buffer, weights_only=True))
    clone.eval()
    with torch.no_grad():
        after = clone(x)
    return maxerr(before, after)
def run_gate() -> dict:
    torch.manual_seed(20261002)
    model = DeltaHybridV1()
    model.eval()

    control = control_model()
    delta_params = parameter_count(model)
    control_params = parameter_count(control)
    param_error = abs(delta_params - control_params) / control_params

    construction = construction_checks(model)
    causal_error = causal_check(model)
    checkpoint_error = checkpoint_check(model)

    model.train()
    gradients = gradient_check(model)

    recurrent_state_values = 3 * model.model_dim * model.model_dim
    recurrent_state_bytes_fp32 = recurrent_state_values * 4

    passed = (
        control_params == CONTROL_PARAMETERS
        and param_error <= PARAM_TOLERANCE
        and construction["finite_forward"]
        and construction["condition_zero_error"] <= CAUSAL_TOLERANCE
        and construction["condition_effect"] > 0.0
        and causal_error <= CAUSAL_TOLERANCE
        and checkpoint_error == 0.0
        and gradients["finite_gradients"]
    )
    return {
        "experiment_id": "delta-v1-model-construction-cpu-gate",
        "passed": passed,
        "delta_parameters": delta_params,
        "control_parameters": control_params,
        "parameter_fraction_error": param_error,
        "parameter_tolerance": PARAM_TOLERANCE,
        "model_dim": model.model_dim,
        "feedforward_dim": model.feedforward_dim,
        "delta_blocks": 3,
        "exact_attention_blocks": 1,
        "chunk_size": model.chunk_size,
        "causal_error": causal_error,
        "causal_tolerance": CAUSAL_TOLERANCE,
        "checkpoint_error": checkpoint_error,
        "recurrent_state_values_batch1": recurrent_state_values,
        "recurrent_state_bytes_fp32_batch1": recurrent_state_bytes_fp32,
        **construction,
        **gradients,
        "torch_version": torch.__version__,
        "python_version": platform.python_version(),
        "device": "cpu",
    }


def main() -> None:
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
