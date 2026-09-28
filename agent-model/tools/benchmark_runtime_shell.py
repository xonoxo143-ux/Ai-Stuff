from __future__ import annotations

import argparse
import json
from statistics import median
from time import perf_counter

from agent_runtime.baselines import (
    ArithmeticCapability,
    EchoComposer,
    RememberCapability,
)
from agent_runtime.runtime import AgentRuntime


def run(turns: int, repeats: int) -> dict:
    samples = []
    for repeat in range(repeats):
        runtime = AgentRuntime(
            composer=EchoComposer(),
            contributors=[
                ArithmeticCapability(),
                RememberCapability(),
            ],
        )
        started = perf_counter()
        for i in range(turns):
            if i % 20 == 0:
                runtime.turn("2 + 3 * 4")
            elif i % 31 == 0:
                runtime.turn(
                    f"remember item{i} = value{i}"
                )
            else:
                runtime.turn(
                    "ordinary conversational turn"
                )
        elapsed = perf_counter() - started
        samples.append(
            {
                "repeat": repeat,
                "elapsed_seconds": elapsed,
                "microseconds_per_turn":
                    elapsed / turns * 1e6,
                "episodes": len(runtime.memory.episodes),
                "semantic_items": len(runtime.memory.semantic),
                "capability_stats":
                    runtime.memory.capability_stats,
            }
        )
    return {
        "turns_per_repeat": turns,
        "repeats": repeats,
        "median_microseconds_per_turn": median(
            x["microseconds_per_turn"]
            for x in samples
        ),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--turns",
        type=int,
        default=10000,
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = run(args.turns, args.repeats)
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    print(text)

    if args.output:
        with open(
            args.output,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
