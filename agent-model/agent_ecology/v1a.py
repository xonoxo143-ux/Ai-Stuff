from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .lifetime_world import LifetimeWorld, LifetimeWorldConfig
from .v1_checkpoint import V1Checkpoint, world_fingerprint


def _tensor_digest(tensor) -> str:
    return sha256(
        tensor.detach().cpu().contiguous().numpy().tobytes()
    ).hexdigest()[:16]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic Agent v1-A lifetime traces."
    )
    parser.add_argument("--world-size", type=int, default=100_000)
    parser.add_argument("--sequence-length", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260926)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = LifetimeWorldConfig(
        total_experiences=args.world_size,
        sequence_length=args.sequence_length,
        seed=args.seed,
    )
    world = LifetimeWorld(config)

    stop = config.total_experiences
    if args.count is not None:
        if args.count < 0:
            raise ValueError("count must be non-negative")
        stop = min(stop, args.start + args.count)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for experience in world.iter_from(args.start, stop):
            evaluator_row = {
                "index": experience.index,
                "family_id": experience.family_id,
                "hidden_regime": experience.hidden_regime,
                "hidden_rules": list(experience.hidden_rules),
                "forced_pattern_applied":
                    experience.forced_pattern_applied,
                "decoy_pattern_applied":
                    experience.decoy_pattern_applied,
                "events_sha256_16":
                    _tensor_digest(experience.events),
                "targets_sha256_16":
                    _tensor_digest(experience.targets),
                "ops_sha256_16":
                    _tensor_digest(experience.op_ids),
            }
            handle.write(
                json.dumps(
                    evaluator_row,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    checkpoint = V1Checkpoint.for_world(
        config,
        next_experience=stop,
    )
    summary = {
        "world_fingerprint": world_fingerprint(config),
        "seed": config.seed,
        "start": args.start,
        "stop": stop,
        "next_experience": checkpoint.next_experience,
        "output": str(args.output),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
