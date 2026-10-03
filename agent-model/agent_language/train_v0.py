from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

import torch
import torch.nn.functional as F

from .curriculum import CurriculumBatcher, allocate_counts, parse_phases
from .data import ByteBatchStream
from .models import ByteTransformer
from .v0_model import BytePatchHybridV0, parameter_count
from delta_hybrid.model_v1 import DeltaHybridV1

BYTES_PER_EQUIV_TOKEN = 4.0


def resolve_device(name: str) -> torch.device:
    if name == "auto":
        name = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but torch.cuda.is_available() is false")
    return device


def sync_device(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def training_autocast(device: torch.device, precision: str):
    if precision == "fp32":
        return nullcontext()
    if precision == "fp16" and device.type == "cuda":
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    raise SystemExit(f"unsupported precision {precision!r} on {device.type}")


def optimizer_to(optimizer: torch.optim.Optimizer, device: torch.device) -> None:
    for state in optimizer.state.values():
        for key, value in list(state.items()):
            if torch.is_tensor(value):
                state[key] = value.to(device)


def build_model(name: str):
    if name == "hybrid":
        return BytePatchHybridV0()
    if name == "delta":
        return DeltaHybridV1()
    if name == "transformer":
        return ByteTransformer(
            model_dim=128,
            layers=5,
            heads=4,
            feedforward_dim=480,
            max_length=256,
            condition_dim=16,
        )
    raise ValueError(f"unknown model: {name}")


def evaluate(
    model,
    data: bytes,
    cfg: dict,
    seed: int,
    device: torch.device,
) -> float:
    stream = ByteBatchStream(data, seed=seed)
    losses = []
    model.eval()
    with torch.no_grad():
        for _ in range(int(cfg["eval_steps"])):
            x, y = stream.batch(
                int(cfg["batch_size"]),
                int(cfg["sequence_length"]),
            )
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            losses.append(
                F.cross_entropy(
                    logits.reshape(-1, 256),
                    y.reshape(-1),
                ).item()
            )
    model.train()
    return sum(losses) / len(losses)


def evaluate_weighted(
    model,
    data: dict[str, bytes],
    weights: dict[str, float],
    cfg: dict,
    seed: int,
    device: torch.device,
) -> float:
    streams = {
        name: ByteBatchStream(payload, seed=seed + 1009 * (i + 1))
        for i, (name, payload) in enumerate(sorted(data.items()))
    }
    counts = allocate_counts(weights, int(cfg["batch_size"]))
    losses = []
    model.eval()
    with torch.no_grad():
        for _ in range(int(cfg["eval_steps"])):
            xs = []
            ys = []
            for name in sorted(counts):
                count = counts[name]
                if count <= 0:
                    continue
                x, y = streams[name].batch(
                    count,
                    int(cfg["sequence_length"]),
                )
                xs.append(x)
                ys.append(y)
            x = torch.cat(xs, dim=0).to(device)
            y = torch.cat(ys, dim=0).to(device)
            logits = model(x)
            losses.append(
                F.cross_entropy(
                    logits.reshape(-1, 256),
                    y.reshape(-1),
                ).item()
            )
    model.train()
    return sum(losses) / len(losses)


def save_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state() -> tuple[str, bool]:
    repo = Path(__file__).resolve().parents[2]
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"],
            text=True,
        ).strip()
    )
    return head, dirty


def load_bytes(path: str) -> bytes:
    data = Path(path).read_bytes()
    if len(data) < 4096:
        raise ValueError(f"corpus too small: {path}")
    return data


def transformer_generate(
    model,
    prompt: str,
    max_new: int,
    context: int,
) -> bytes:
    prefix = bytearray(prompt.encode("utf-8"))
    model.eval()
    with torch.no_grad():
        for _ in range(max_new):
            window = bytes(prefix[-context:])
            device = next(model.parameters()).device
            x = torch.tensor(
                [list(window)],
                dtype=torch.long,
                device=device,
            )
            logits = model(x)
            prefix.append(int(logits[0, -1].argmax().item()))
    return bytes(prefix)


def generate_bytes(
    model,
    model_name: str,
    prompt: str,
    max_new: int,
    context: int,
) -> bytes:
    if model_name == "hybrid":
        return model.generate(prompt, max_new_bytes=max_new)
    return transformer_generate(model, prompt, max_new, context)


def sample_text(model, model_name: str, prompt: str, cfg: dict) -> str:
    raw = generate_bytes(
        model,
        model_name,
        prompt,
        int(cfg.get("sample_bytes", 160)),
        int(cfg["sequence_length"]),
    )
    return raw.decode("utf-8", errors="replace")


def benchmark_generation(
    model,
    model_name: str,
    prompt: str,
    cfg: dict,
) -> dict:
    count = int(cfg.get("speed_sample_bytes", 64))
    was_training = model.training
    model.eval()
    device = next(model.parameters()).device
    sync_device(device)
    started = time.perf_counter()
    raw = generate_bytes(
        model,
        model_name,
        prompt,
        count,
        int(cfg["sequence_length"]),
    )
    sync_device(device)
    elapsed = time.perf_counter() - started
    if was_training:
        model.train()
    generated = max(0, len(raw) - len(prompt.encode("utf-8")))
    bps = generated / elapsed if elapsed > 0 else 0.0
    return {
        "generation_bytes": generated,
        "generation_seconds": elapsed,
        "generation_bytes_per_sec": bps,
        "generation_equiv_tokens_per_sec": bps / BYTES_PER_EQUIV_TOKEN,
    }


def throughput(bytes_seen: int, seconds: float) -> dict:
    bps = bytes_seen / seconds if seconds > 0 else 0.0
    return {
        "train_bytes": int(bytes_seen),
        "train_seconds": float(seconds),
        "train_bytes_per_sec": float(bps),
        "train_equiv_tokens_per_sec": float(
            bps / BYTES_PER_EQUIV_TOKEN
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument(
        "--model",
        choices=("hybrid", "delta", "transformer"),
        required=True,
    )
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--fork-from")
    ap.add_argument("--max-step", type=int)
    ap.add_argument("--device")
    ap.add_argument(
        "--execution",
        choices=("reference", "vectorized", "chunked"),
    )
    ap.add_argument(
        "--precision",
        choices=("fp32", "fp16"),
    )
    ap.add_argument("--fused-adamw", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(
        Path(args.config).read_text(encoding="utf-8")
    )
    if args.resume and args.fork_from:
        raise SystemExit("--resume and --fork-from are mutually exclusive")

    device = resolve_device(
        str(args.device or cfg.get("device", "cpu"))
    )
    execution = str(
        args.execution or cfg.get("execution", "reference")
    )
    precision = str(
        args.precision or cfg.get("precision", "fp32")
    )
    fused_adamw = bool(
        args.fused_adamw or cfg.get("fused_adamw", False)
    )
    if precision == "fp16" and device.type != "cuda":
        raise SystemExit("fp16 training requires CUDA")
    if fused_adamw and device.type != "cuda":
        raise SystemExit("fused AdamW requires CUDA")
    if execution == "vectorized" and args.model != "hybrid":
        raise SystemExit("vectorized execution is only defined for the hybrid model")
    if execution == "chunked" and args.model != "delta":
        raise SystemExit("chunked execution is only defined for the delta model")
    if args.model == "delta" and execution not in {"reference", "chunked"}:
        raise SystemExit(
            "delta model supports --execution reference or chunked"
        )

    runtime = {
        "device_type": device.type,
        "execution": execution,
        "precision": precision,
        "fused_adamw": fused_adamw,
    }

    git_head, git_dirty = git_state()
    if cfg.get("require_clean_git", False) and git_dirty:
        raise SystemExit(
            "refusing training: git working tree is dirty"
        )

    stream_paths = {
        str(name): str(path)
        for name, path in cfg["train_streams"].items()
    }
    valid_stream_paths = {
        str(name): str(path)
        for name, path in cfg["valid_streams"].items()
    }
    provenance = {
        "git_head": git_head,
        "config_sha256": file_sha256(args.config),
        "train_stream_sha256": {
            name: file_sha256(path)
            for name, path in sorted(stream_paths.items())
        },
        "valid_stream_sha256": {
            name: file_sha256(path)
            for name, path in sorted(valid_stream_paths.items())
        },
        "valid_sha256": file_sha256(cfg["valid_file"]),
        "runtime": runtime,
    }

    if int(cfg["sequence_length"]) % 4:
        raise SystemExit(
            "sequence_length must be divisible by 4"
        )
    torch.set_num_threads(int(cfg.get("threads", 4)))
    if cfg.get("deterministic", False):
        torch.use_deterministic_algorithms(True)

    seed = int(cfg["seed"])
    random.seed(seed)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    train_data = {
        name: load_bytes(path)
        for name, path in stream_paths.items()
    }
    valid_data = load_bytes(cfg["valid_file"])
    valid_stream_data = {
        name: load_bytes(path)
        for name, path in valid_stream_paths.items()
    }
    total_steps = int(cfg["steps"])
    phases = parse_phases(
        list(cfg["curriculum"]),
        set(train_data),
        total_steps,
    )
    batcher = CurriculumBatcher(
        train_data,
        seed=seed + 17,
        phases=phases,
    )

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = run_dir / f"{args.model}.pt"
    metrics_path = run_dir / f"{args.model}.json"
    telemetry_path = run_dir / f"{args.model}.telemetry.jsonl"
    if not args.resume:
        telemetry_path.write_text("", encoding="utf-8")

    model = build_model(args.model)
    if args.model == "hybrid":
        model.set_vectorized_forward(execution == "vectorized")
    elif args.model == "delta":
        model.set_execution(execution)
    model.to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["learning_rate"]),
        weight_decay=float(
            cfg.get("weight_decay", 0.01)
        ),
        fused=fused_adamw,
    )
    use_amp = precision == "fp16"
    scaler = (
        torch.amp.GradScaler("cuda", enabled=True)
        if use_amp
        else None
    )

    step = 0
    history: list[dict] = []
    cumulative_train_bytes = 0
    cumulative_train_seconds = 0.0
    forked_from: dict | None = None

    load_path: Path | None = None
    if args.resume:
        load_path = ckpt_path
    elif args.fork_from:
        load_path = Path(args.fork_from)

    if load_path is not None:
        payload = torch.load(
            load_path,
            map_location="cpu",
            weights_only=False,
        )
        if payload["model_name"] != args.model:
            raise ValueError("checkpoint model mismatch")
        if args.resume and payload.get("provenance") != provenance:
            raise ValueError(
                "checkpoint provenance mismatch"
            )

        model.load_state_dict(payload["model"])
        optimizer.load_state_dict(payload["optimizer"])
        optimizer_to(optimizer, device)
        if scaler is not None and payload.get("grad_scaler") is not None:
            scaler.load_state_dict(payload["grad_scaler"])
        step = int(payload["step"])
        batcher.set_rng_states(
            payload["curriculum_rng_states"]
        )
        random.setstate(payload["python_rng_state"])
        torch.set_rng_state(payload["torch_rng_state"])

        if args.resume:
            history = list(payload.get("history", []))
            cumulative_train_bytes = int(
                payload.get("cumulative_train_bytes", 0)
            )
            cumulative_train_seconds = float(
                payload.get("cumulative_train_seconds", 0.0)
            )
            if device.type == "cuda":
                cuda_rng = payload.get("torch_cuda_rng_state_all")
                if cuda_rng is not None:
                    torch.cuda.set_rng_state_all(cuda_rng)
        else:
            forked_from = {
                "checkpoint": str(load_path),
                "checkpoint_sha256": file_sha256(load_path),
                "step": step,
                "provenance": payload.get("provenance"),
                "cumulative_train_bytes": int(
                    payload.get("cumulative_train_bytes", 0)
                ),
                "cumulative_train_seconds": float(
                    payload.get("cumulative_train_seconds", 0.0)
                ),
            }

    target_step = min(
        total_steps,
        args.max_step or total_steps,
    )
    checkpoint_every = int(cfg["checkpoint_every"])
    eval_every = int(cfg["eval_every"])
    prompt = str(
        cfg.get(
            "sample_prompt",
            "User: Explain why evidence matters.\nAssistant:",
        )
    )
    invocation_started = time.perf_counter()
    interval_bytes = 0
    interval_train_seconds = 0.0
    model.train()

    while step < target_step:
        next_step = step + 1
        sync_device(device)
        train_started = time.perf_counter()
        x, y, phase, source_counts = batcher.batch(
            next_step,
            batch_size=int(cfg["batch_size"]),
            sequence_length=int(cfg["sequence_length"]),
        )
        x = x.to(device)
        y = y.to(device)
        optimizer.zero_grad(set_to_none=True)
        with training_autocast(device, precision):
            logits = model(x)
            loss = F.cross_entropy(
                logits.reshape(-1, 256),
                y.reshape(-1),
            )

        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                float(cfg.get("grad_clip", 1.0)),
            )
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                float(cfg.get("grad_clip", 1.0)),
            )
            optimizer.step()

        sync_device(device)
        train_elapsed = (
            time.perf_counter() - train_started
        )

        step = next_step
        step_bytes = int(x.numel())
        interval_bytes += step_bytes
        interval_train_seconds += train_elapsed
        cumulative_train_bytes += step_bytes
        cumulative_train_seconds += train_elapsed

        if (
            step == 1
            or step % eval_every == 0
            or step == target_step
        ):
            valid_loss = evaluate(
                model,
                valid_data,
                cfg,
                seed + 99,
                device,
            )
            phase_valid_loss = evaluate_weighted(
                model,
                valid_stream_data,
                phase.weights,
                cfg,
                seed + 149,
                device,
            )
            row = {
                "step": step,
                "phase": phase.name,
                "phase_end_step": phase.end_step,
                "source_batch_counts": source_counts,
                "runtime": runtime,
                "train_loss_nats": float(loss.item()),
                "valid_loss_nats": float(valid_loss),
                "valid_bits_per_byte": float(
                    valid_loss / math.log(2.0)
                ),
                "phase_valid_loss_nats": float(
                    phase_valid_loss
                ),
                "phase_valid_bits_per_byte": float(
                    phase_valid_loss / math.log(2.0)
                ),
                "interval_throughput": throughput(
                    interval_bytes,
                    interval_train_seconds,
                ),
                "cumulative_throughput": throughput(
                    cumulative_train_bytes,
                    cumulative_train_seconds,
                ),
                **benchmark_generation(
                    model,
                    args.model,
                    prompt,
                    cfg,
                ),
            }
            history.append(row)
            with telemetry_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            print(json.dumps(row), flush=True)
            interval_bytes = 0
            interval_train_seconds = 0.0


        if (
            step % checkpoint_every == 0
            or step == target_step
        ):
            save_checkpoint(
                ckpt_path,
                {
                    "model_name": args.model,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "step": step,
                    "history": history,
                    "config": cfg,
                    "provenance": provenance,
                    "runtime": runtime,
                    "forked_from": forked_from,
                    "grad_scaler":
                        scaler.state_dict()
                        if scaler is not None
                        else None,
                    "curriculum_rng_states":
                        batcher.rng_states(),
                    "python_rng_state":
                        random.getstate(),
                    "torch_rng_state":
                        torch.get_rng_state(),
                    "torch_cuda_rng_state_all":
                        torch.cuda.get_rng_state_all()
                        if device.type == "cuda"
                        else None,
                    "cumulative_train_bytes":
                        cumulative_train_bytes,
                    "cumulative_train_seconds":
                        cumulative_train_seconds,
                },
            )

    elapsed = time.perf_counter() - invocation_started
    valid_loss = evaluate(
        model,
        valid_data,
        cfg,
        seed + 199,
        device,
    )
    sample = sample_text(
        model,
        args.model,
        prompt,
        cfg,
    )
    current_phase = (
        batcher.phase_for_step(step)
        if step > 0
        else phases[0]
    )
    result = {
        "model": args.model,
        "parameters": parameter_count(model),
        "step": step,
        "phase": current_phase.name,
        "target_step": target_step,
        "total_steps": total_steps,
        "elapsed_seconds_this_invocation": elapsed,
        "valid_loss_nats": valid_loss,
        "valid_bits_per_byte":
            valid_loss / math.log(2.0),
        "cumulative_throughput": throughput(
            cumulative_train_bytes,
            cumulative_train_seconds,
        ),
        "history": history,
        "sample": sample,
        "checkpoint": str(ckpt_path),
        "telemetry": str(telemetry_path),
        "runtime": runtime,
        "forked_from": forked_from,
        "provenance": provenance,
        "git_dirty": git_dirty,
    }
    metrics_path.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
