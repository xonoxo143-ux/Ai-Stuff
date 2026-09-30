from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from .curriculum import CurriculumBatcher, allocate_counts, parse_phases
from .data import ByteBatchStream
from .models import ByteTransformer
from .v0_model import BytePatchHybridV0, parameter_count

BYTES_PER_EQUIV_TOKEN = 4.0


def build_model(name: str):
    if name == "hybrid":
        return BytePatchHybridV0()
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


def evaluate(model, data: bytes, cfg: dict, seed: int) -> float:
    stream = ByteBatchStream(data, seed=seed)
    losses = []
    model.eval()
    with torch.no_grad():
        for _ in range(int(cfg["eval_steps"])):
            x, y = stream.batch(
                int(cfg["batch_size"]),
                int(cfg["sequence_length"]),
            )
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
            x = torch.cat(xs, dim=0)
            y = torch.cat(ys, dim=0)
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
            x = torch.tensor([list(window)], dtype=torch.long)
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
    started = time.perf_counter()
    raw = generate_bytes(
        model,
        model_name,
        prompt,
        count,
        int(cfg["sequence_length"]),
    )
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
        choices=("hybrid", "transformer"),
        required=True,
    )
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-step", type=int)
    args = ap.parse_args()

    cfg = json.loads(
        Path(args.config).read_text(encoding="utf-8")
    )
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
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["learning_rate"]),
        weight_decay=float(
            cfg.get("weight_decay", 0.01)
        ),
    )

    step = 0
    history: list[dict] = []
    cumulative_train_bytes = 0
    cumulative_train_seconds = 0.0

    if args.resume:
        payload = torch.load(
            ckpt_path,
            map_location="cpu",
            weights_only=False,
        )
        if payload["model_name"] != args.model:
            raise ValueError("checkpoint model mismatch")
        if payload.get("provenance") != provenance:
            raise ValueError(
                "checkpoint provenance mismatch"
            )
        model.load_state_dict(payload["model"])
        optimizer.load_state_dict(payload["optimizer"])
        step = int(payload["step"])
        history = list(payload.get("history", []))
        batcher.set_rng_states(
            payload["curriculum_rng_states"]
        )
        random.setstate(payload["python_rng_state"])
        torch.set_rng_state(payload["torch_rng_state"])
        cumulative_train_bytes = int(
            payload.get("cumulative_train_bytes", 0)
        )
        cumulative_train_seconds = float(
            payload.get("cumulative_train_seconds", 0.0)
        )


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
        train_started = time.perf_counter()
        x, y, phase, source_counts = batcher.batch(
            next_step,
            batch_size=int(cfg["batch_size"]),
            sequence_length=int(cfg["sequence_length"]),
        )
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = F.cross_entropy(
            logits.reshape(-1, 256),
            y.reshape(-1),
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            float(cfg.get("grad_clip", 1.0)),
        )
        optimizer.step()
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
            )
            phase_valid_loss = evaluate_weighted(
                model,
                valid_stream_data,
                phase.weights,
                cfg,
                seed + 149,
            )
            row = {
                "step": step,
                "phase": phase.name,
                "phase_end_step": phase.end_step,
                "source_batch_counts": source_counts,
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
                    "curriculum_rng_states":
                        batcher.rng_states(),
                    "python_rng_state":
                        random.getstate(),
                    "torch_rng_state":
                        torch.get_rng_state(),
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
