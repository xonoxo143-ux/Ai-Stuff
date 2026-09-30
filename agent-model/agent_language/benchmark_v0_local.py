from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import torch

from .v0_model import BytePatchHybridV0, parameter_count


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rss_bytes() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except Exception:
        pass
    return None
def timed_generation(model, prompt: bytes, count: int) -> dict:
    started = time.perf_counter()
    state = model.begin_stream()
    for value in prompt:
        model.accept_byte(state, value)
    prompt_seconds = time.perf_counter() - started

    started = time.perf_counter()
    value = int(state.next_logits.argmax(dim=-1).item())
    model.accept_byte(state, value)
    first_seconds = time.perf_counter() - started

    remaining = max(0, count - 1)
    started = time.perf_counter()
    for _ in range(remaining):
        value = int(state.next_logits.argmax(dim=-1).item())
        model.accept_byte(state, value)
    sustained_seconds = time.perf_counter() - started
    return {
        "prompt_bytes": len(prompt),
        "prompt_seconds": prompt_seconds,
        "first_byte_seconds": first_seconds,
        "sustained_bytes": remaining,
        "sustained_seconds": sustained_seconds,
        "sustained_bytes_per_sec":
            remaining / sustained_seconds if sustained_seconds > 0 else 0.0,
    }
def forward_benchmark(model, sequence_length: int, repeats: int) -> dict:
    x = torch.randint(0, 256, (1, sequence_length), dtype=torch.long)
    model.eval()
    with torch.no_grad():
        for _ in range(2):
            model(x)
        times = []
        for _ in range(repeats):
            started = time.perf_counter()
            model(x)
            times.append(time.perf_counter() - started)
    return {
        "sequence_length": sequence_length,
        "repeats": repeats,
        "median_seconds": statistics.median(times),
        "min_seconds": min(times),
        "max_seconds": max(times),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--generate-bytes", type=int, default=128)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--sequence-length", type=int, default=128)
    ap.add_argument("--forward-repeats", type=int, default=8)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    checkpoint = Path(args.checkpoint)
    started = time.perf_counter()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = BytePatchHybridV0()
    model.load_state_dict(payload["model"])
    model.set_vectorized_forward(False)
    model.eval()
    load_seconds = time.perf_counter() - started

    model_state_bytes = sum(
        tensor.numel() * tensor.element_size()
        for tensor in model.state_dict().values()
    )
    prompt = (
        "<|dialogue|>\n"
        "User: Explain why conflicting evidence should lower confidence.\n"
        "Assistant:"
    ).encode("utf-8")

    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "checkpoint_step": int(payload["step"]),
        "parameters": parameter_count(model),
        "model_state_bytes": model_state_bytes,
        "threads": args.threads,
        "torch": torch.__version__,
        "load_seconds": load_seconds,
        "rss_bytes_after_load": rss_bytes(),
        "forward": forward_benchmark(
            model, args.sequence_length, args.forward_repeats
        ),
        "generation": timed_generation(
            model, prompt, args.generate_bytes
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
