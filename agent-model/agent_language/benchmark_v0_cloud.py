from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from .train_v0 import optimizer_to, sync_device, training_autocast
from .v0_model import BytePatchHybridV0


CASES = (
    ("reference_fp32", False, "fp32", False),
    ("vectorized_fp32", True, "fp32", False),
    ("vectorized_fp32_fused", True, "fp32", True),
    ("vectorized_fp16", True, "fp16", False),
    ("vectorized_fp16_fused", True, "fp16", True),
)


def load_case(payload: dict, device: torch.device, vectorized: bool, fused: bool):
    model = BytePatchHybridV0().to(device)
    model.load_state_dict(payload["model"])
    model.set_vectorized_forward(vectorized)
    # Benchmark optimizer work without moving the frozen weights.
    # Warmup initializes Adam state; lr=0 keeps every case numerically stable.
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.0,
        weight_decay=0.0,
        fused=fused,
    )
    return model, optimizer


def train_step(model, optimizer, x, y, precision, scaler, grad_clip):
    optimizer.zero_grad(set_to_none=True)
    with training_autocast(x.device, precision):
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, 256), y.reshape(-1))
    if scaler is not None:
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        scaler.step(optimizer)
        scaler.update()
    else:
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
    return loss


def run_case(payload, device, case, batches, warmup, steps):
    name, vectorized, precision, fused = case
    model, optimizer = load_case(payload, device, vectorized, fused)
    scaler = torch.amp.GradScaler("cuda", enabled=True) if precision == "fp16" else None
    grad_clip = float(payload["config"].get("grad_clip", 1.0))
    model.train()

    for i in range(warmup):
        x, y = batches[i]
        train_step(model, optimizer, x.to(device), y.to(device), precision, scaler, grad_clip)
    sync_device(device)

    torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    last_loss = None
    for i in range(steps):
        x, y = batches[warmup + i]
        last_loss = train_step(
            model,
            optimizer,
            x.to(device),
            y.to(device),
            precision,
            scaler,
            grad_clip,
        )
    sync_device(device)
    elapsed = time.perf_counter() - started
    batch_size, sequence_length = batches[0][0].shape
    train_bytes = steps * batch_size * sequence_length
    finite_loss = bool(torch.isfinite(last_loss).item())
    return {
        "name": name,
        "vectorized": vectorized,
        "precision": precision,
        "finite_loss": finite_loss,
        "fused_adamw": fused,
        "steps": steps,
        "seconds": elapsed,
        "steps_per_sec": steps / elapsed,
        "train_bytes": train_bytes,
        "train_bytes_per_sec": train_bytes / elapsed,
        "last_loss_nats": float(last_loss.detach().cpu()),
        "peak_memory_bytes": int(torch.cuda.max_memory_allocated(device)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint")
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--warmup", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--sequence-length", type=int, default=128)
    args = ap.parse_args()

    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise SystemExit("cloud benchmark requires CUDA")

    if args.checkpoint:
        payload = torch.load(
            Path(args.checkpoint), map_location="cpu", weights_only=False
        )
        if payload.get("model_name") != "hybrid":
            raise SystemExit("benchmark expects a hybrid checkpoint")
        checkpoint_source = str(Path(args.checkpoint))
    else:
        torch.manual_seed(args.seed)
        fresh = BytePatchHybridV0()
        payload = {
            "model": fresh.state_dict(),
            "model_name": "hybrid",
            "step": 0,
            "config": {"grad_clip": 1.0},
        }
        checkpoint_source = "fresh-init"

    generator = torch.Generator(device="cpu")
    generator.manual_seed(20260930)
    batches = []
    for _ in range(args.warmup + args.steps):
        x = torch.randint(
            0, 256, (args.batch_size, args.sequence_length),
            generator=generator, dtype=torch.long,
        )
        y = torch.randint(
            0, 256, (args.batch_size, args.sequence_length),
            generator=generator, dtype=torch.long,
        )
        batches.append((x, y))

    info = {
        "torch": torch.__version__,
        "device": torch.cuda.get_device_name(device),
        "cuda_count": torch.cuda.device_count(),
        "batch_size": args.batch_size,
        "sequence_length": args.sequence_length,
        "checkpoint_step": int(payload["step"]),
        "checkpoint_source": checkpoint_source,
        "seed": int(args.seed),
    }
    results = []
    for case in CASES:
        try:
            results.append(
                run_case(payload, device, case, batches, args.warmup, args.steps)
            )
        except Exception as exc:
            results.append({"name": case[0], "error": repr(exc)})
    print(json.dumps({"environment": info, "results": results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
