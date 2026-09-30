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

from .data import ByteBatchStream
from .models import ByteTransformer
from .v0_model import BytePatchHybridV0, parameter_count


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
            x, y = stream.batch(int(cfg["batch_size"]), int(cfg["sequence_length"]))
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
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True).strip())
    return head, dirty


def load_bytes(path: str) -> bytes:
    data = Path(path).read_bytes()
    if len(data) < 4096:
        raise ValueError(f"corpus too small: {path}")
    return data


def transformer_generate(model, prompt: str, max_new: int, context: int) -> bytes:
    prefix = bytearray(prompt.encode("utf-8"))
    model.eval()
    with torch.no_grad():
        for _ in range(max_new):
            window = bytes(prefix[-context:])
            x = torch.tensor([list(window)], dtype=torch.long)
            logits = model(x)
            prefix.append(int(logits[0, -1].argmax().item()))
    return bytes(prefix)


def sample_text(model, model_name: str, prompt: str, cfg: dict) -> str:
    max_new = int(cfg.get("sample_bytes", 160))
    if model_name == "hybrid":
        raw = model.generate(prompt, max_new_bytes=max_new)
    else:
        raw = transformer_generate(
            model,
            prompt,
            max_new,
            int(cfg["sequence_length"]),
        )
    return raw.decode("utf-8", errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", choices=("hybrid", "transformer"), required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-step", type=int)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    git_head, git_dirty = git_state()
    if cfg.get("require_clean_git", False) and git_dirty:
        raise SystemExit("refusing training: git working tree is dirty")
    provenance = {
        "git_head": git_head,
        "config_sha256": file_sha256(args.config),
        "train_sha256": file_sha256(cfg["train_file"]),
        "valid_sha256": file_sha256(cfg["valid_file"]),
    }
    if int(cfg["sequence_length"]) % 4:
        raise SystemExit("sequence_length must be divisible by 4")
    torch.set_num_threads(int(cfg.get("threads", 4)))
    if cfg.get("deterministic", False):
        torch.use_deterministic_algorithms(True)
    seed = int(cfg["seed"])
    random.seed(seed)
    torch.manual_seed(seed)

    train_data = load_bytes(cfg["train_file"])
    valid_data = load_bytes(cfg["valid_file"])
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = run_dir / f"{args.model}.pt"
    metrics_path = run_dir / f"{args.model}.json"

    model = build_model(args.model)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["learning_rate"]),
        weight_decay=float(cfg.get("weight_decay", 0.01)),
    )
    stream = ByteBatchStream(train_data, seed=seed + 17)
    step = 0
    history: list[dict] = []

    if args.resume:
        payload = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        if payload["model_name"] != args.model:
            raise ValueError("checkpoint model mismatch")
        if payload.get("provenance") != provenance:
            raise ValueError("checkpoint provenance mismatch")
        model.load_state_dict(payload["model"])
        optimizer.load_state_dict(payload["optimizer"])
        step = int(payload["step"])
        history = list(payload.get("history", []))
        stream.rng.setstate(payload["stream_rng_state"])
        random.setstate(payload["python_rng_state"])
        torch.set_rng_state(payload["torch_rng_state"])

    total_steps = int(cfg["steps"])
    target_step = min(total_steps, args.max_step or total_steps)
    checkpoint_every = int(cfg["checkpoint_every"])
    eval_every = int(cfg["eval_every"])
    started = time.perf_counter()
    model.train()

    while step < target_step:
        x, y = stream.batch(int(cfg["batch_size"]), int(cfg["sequence_length"]))
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, 256), y.reshape(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg.get("grad_clip", 1.0)))
        optimizer.step()
        step += 1

        row = None
        if step == 1 or step % eval_every == 0 or step == target_step:
            valid_loss = evaluate(model, valid_data, cfg, seed + 99)
            row = {
                "step": step,
                "train_loss_nats": float(loss.item()),
                "valid_loss_nats": float(valid_loss),
                "valid_bits_per_byte": float(valid_loss / math.log(2.0)),
            }
            history.append(row)
            print(json.dumps(row), flush=True)

        if step % checkpoint_every == 0 or step == target_step:
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
                    "stream_rng_state": stream.rng.getstate(),
                    "python_rng_state": random.getstate(),
                    "torch_rng_state": torch.get_rng_state(),
                },
            )

    elapsed = time.perf_counter() - started
    valid_loss = evaluate(model, valid_data, cfg, seed + 199)
    prompt = str(cfg.get("sample_prompt", "User: Explain why evidence matters.\nAssistant:"))
    sample = sample_text(model, args.model, prompt, cfg)
    result = {
        "model": args.model,
        "parameters": parameter_count(model),
        "step": step,
        "target_step": target_step,
        "total_steps": total_steps,
        "elapsed_seconds_this_invocation": elapsed,
        "valid_loss_nats": valid_loss,
        "valid_bits_per_byte": valid_loss / math.log(2.0),
        "history": history,
        "sample": sample,
        "checkpoint": str(ckpt_path),
        "provenance": provenance,
        "git_dirty": git_dirty,
    }
    metrics_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
