from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from fluidlm import FluidConfig, FluidLM
from fluidlm.corpus import load_corpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train FluidLM-0")
    parser.add_argument(
        "--corpus",
        choices=["synthetic", "tiny-shakespeare", "alice"],
        default="synthetic",
    )
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seq-len", type=int, default=64)
    parser.add_argument("--grid-size", type=int, default=6)
    parser.add_argument("--lr", type=float, default=3e-3)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--dt", type=float, default=0.04)
    parser.add_argument("--diffusion", type=float, default=0.08)
    parser.add_argument("--viscosity", type=float, default=0.08)
    parser.add_argument("--pressure", type=float, default=0.60)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--eval-batches", type=int, default=4)
    parser.add_argument("--sample-len", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--out-dir", default="outputs/run")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto")
    return parser.parse_args()


class CharCodec:
    def __init__(self, text: str):
        self.chars = sorted(set(text))
        self.stoi = {ch: i for i, ch in enumerate(self.chars)}
        self.itos = {i: ch for ch, i in self.stoi.items()}

    def encode(self, text: str) -> torch.Tensor:
        fallback = self.stoi.get(" ", 0)
        return torch.tensor([self.stoi.get(ch, fallback) for ch in text], dtype=torch.long)

    def decode(self, ids: list[int]) -> str:
        return "".join(self.itos[int(i)] for i in ids)


def choose_device(requested: str) -> torch.device:
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        return torch.device("cuda")
    if requested == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_batch(
    data: torch.Tensor,
    batch_size: int,
    seq_len: int,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    max_start = len(data) - seq_len - 1
    if max_start <= 0:
        raise ValueError("Corpus is shorter than seq_len")
    starts = torch.randint(0, max_start, (batch_size,))
    x = torch.stack([data[i : i + seq_len] for i in starts])
    y = torch.stack([data[i + 1 : i + seq_len + 1] for i in starts])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss(
    model: FluidLM,
    data: torch.Tensor,
    batch_size: int,
    seq_len: int,
    batches: int,
    device: torch.device,
) -> float:
    model.eval()
    values = []
    for _ in range(batches):
        x, y = get_batch(data, batch_size, seq_len, device)
        logits, _ = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        values.append(float(loss.item()))
    model.train()
    return sum(values) / len(values)


@torch.no_grad()
def generate_with_trace(
    model: FluidLM,
    codec: CharCodec,
    prompt: str,
    length: int,
    temperature: float,
    device: torch.device,
) -> tuple[str, dict[str, np.ndarray]]:
    model.eval()
    state = model.init_state(1, device)
    output_ids: list[int] = []

    encoded = codec.encode(prompt).to(device)
    last_logits = None
    for token_id in encoded:
        last_logits, state = model.step(token_id.view(1), state)
        output_ids.append(int(token_id.item()))

    if last_logits is None:
        token = torch.tensor([codec.stoi.get(" ", 0)], device=device)
        last_logits, state = model.step(token, state)

    density_frames = []
    vorticity_frames = []
    kinetic = []

    for _ in range(length):
        probs = torch.softmax(last_logits / max(temperature, 1e-4), dim=-1)
        token = torch.multinomial(probs, num_samples=1).squeeze(1)
        output_ids.append(int(token.item()))
        last_logits, state = model.step(token, state)

        rho, velocity = state
        vort = model.vorticity(velocity)
        density_frames.append(rho[0].detach().cpu().numpy())
        vorticity_frames.append(vort[0].detach().cpu().numpy())
        kinetic.append(float((velocity.square().mean()).item()))

    text = codec.decode(output_ids)
    trace = {
        "density": np.asarray(density_frames, dtype=np.float32),
        "vorticity": np.asarray(vorticity_frames, dtype=np.float32),
        "kinetic": np.asarray(kinetic, dtype=np.float32),
    }
    return text, trace


def main() -> None:
    args = parse_args()
    if args.steps < 1:
        raise ValueError("--steps must be positive")
    if args.grid_size < 3:
        raise ValueError("--grid-size must be at least 3")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = choose_device(args.device)
    print(f"device={device}")

    text = load_corpus(args.corpus)
    codec = CharCodec(text)
    encoded = codec.encode(text)
    split = max(args.seq_len + 2, int(0.90 * len(encoded)))
    split = min(split, len(encoded) - args.seq_len - 2)
    train_data = encoded[:split]
    val_data = encoded[split:]

    cfg = FluidConfig(
        vocab_size=len(codec.chars),
        grid_size=args.grid_size,
        dt=args.dt,
        diffusion=args.diffusion,
        viscosity=args.viscosity,
        pressure=args.pressure,
    )
    model = FluidLM(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    parameter_count = sum(p.numel() for p in model.parameters())
    uniform_loss = math.log(len(codec.chars))
    print(
        f"chars={len(encoded):,} vocab={len(codec.chars)} params={parameter_count:,} "
        f"uniform_loss={uniform_loss:.4f}"
    )

    metrics: list[dict[str, float | int]] = []
    for step in range(1, args.steps + 1):
        x, y = get_batch(train_data, args.batch_size, args.seq_len, device)
        logits, _ = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if step == 1 or step % args.eval_every == 0 or step == args.steps:
            val_loss = estimate_loss(
                model,
                val_data,
                args.batch_size,
                args.seq_len,
                args.eval_batches,
                device,
            )
            row = {
                "step": step,
                "train_loss": float(loss.item()),
                "val_loss": float(val_loss),
            }
            metrics.append(row)
            print(
                f"step={step:5d} train={row['train_loss']:.4f} "
                f"val={row['val_loss']:.4f}"
            )

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    prompt = "the " if "t" in codec.stoi and "h" in codec.stoi else codec.chars[0]
    sample, trace = generate_with_trace(
        model,
        codec,
        prompt=prompt,
        length=args.sample_len,
        temperature=args.temperature,
        device=device,
    )

    checkpoint = {
        "model_state": model.state_dict(),
        "config": asdict(cfg),
        "chars": codec.chars,
        "training_args": vars(args),
    }
    torch.save(checkpoint, out / "checkpoint.pt")

    summary = {
        "corpus": args.corpus,
        "seed": args.seed,
        "device": str(device),
        "characters": len(encoded),
        "vocab_size": len(codec.chars),
        "parameters": parameter_count,
        "uniform_loss": uniform_loss,
        "metrics": metrics,
    }
    (out / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "sample.txt").write_text(sample, encoding="utf-8")
    np.savez_compressed(out / "trace.npz", **trace)

    print("\n--- sample ---")
    print(sample[:1000])
    print(f"\nartifacts={out.resolve()}")


if __name__ == "__main__":
    main()
