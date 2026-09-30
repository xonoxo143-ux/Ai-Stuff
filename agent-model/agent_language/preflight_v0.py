from __future__ import annotations

import json
import subprocess
from pathlib import Path

import torch

from .curriculum import allocate_counts, parse_phases
from .fetch_v0_sources import SOURCES, sha256_file
from .train_v0 import build_model
from .v0_model import parameter_count


def check(name: str, ok: bool, detail) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    repo = root.parent
    manifest = json.loads(
        (root / "configs" / "corpus_v0_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    suite = json.loads(
        (root / "configs" / "eval_v0.json").read_text(
            encoding="utf-8"
        )
    )
    cfg = json.loads(
        (root / "configs" / "v0_first_run.json").read_text(
            encoding="utf-8"
        )
    )
    rows = []
    timing = json.loads(
        (root / "configs" / "v0_phase1_timing.json").read_text(
            encoding="utf-8"
        )
    )
    config_hash = sha256_file(
        root / "configs" / "v0_first_run.json"
    )
    rows.append(check(
        "timing_matches_config",
        timing.get("config_sha256") == config_hash,
        {
            "timing_config_sha256": timing.get("config_sha256"),
            "current_config_sha256": config_hash,
        },
    ))

    for name, relative in sorted(cfg["train_streams"].items()):
        path = root / relative
        actual = sha256_file(path) if path.exists() else None
        expected = manifest["stream_sha256"][f"train_{name}"]
        rows.append(check(
            f"train_stream_{name}",
            actual == expected,
            actual,
        ))

    for name, relative in sorted(cfg["valid_streams"].items()):
        path = root / relative
        actual = sha256_file(path) if path.exists() else None
        expected = manifest["stream_sha256"][f"valid_{name}"]
        rows.append(check(
            f"valid_stream_{name}",
            actual == expected,
            actual,
        ))

    valid = root / cfg["valid_file"]
    actual_valid = sha256_file(valid) if valid.exists() else None
    rows.append(check(
        "valid_hash",
        actual_valid == manifest["valid_sha256"],
        actual_valid,
    ))


    raw = root / "data" / "raw"
    for key, source in SOURCES.items():
        path = raw / source["filename"]
        actual = sha256_file(path) if path.exists() else None
        rows.append(check(
            f"source_{key}",
            actual == source["sha256"],
            actual,
        ))

    phases = parse_phases(
        list(cfg["curriculum"]),
        set(cfg["train_streams"]),
        int(cfg["steps"]),
    )
    first_counts = allocate_counts(
        phases[0].weights,
        int(cfg["batch_size"]),
    )
    rows.append(check(
        "phase1_mix",
        first_counts == {"dialogue": 16, "prose": 48},
        {
            "phase": phases[0].name,
            "end_step": phases[0].end_step,
            "batch_counts": first_counts,
        },
    ))
    rows.append(check(
        "phase_boundaries",
        [p.end_step for p in phases] == [2048, 3072, 4096],
        [p.end_step for p in phases],
    ))

    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain"],
        text=True,
    ).strip()
    rows.append(check("git_clean", not dirty, dirty or "clean"))

    hybrid = build_model("hybrid")
    control = build_model("transformer")
    hp = parameter_count(hybrid)
    cp = parameter_count(control)
    delta = abs(hp - cp) / hp
    rows.append(check(
        "parameter_match",
        delta < 0.02,
        {"hybrid": hp, "control": cp, "delta": delta},
    ))


    x = torch.randint(
        0,
        256,
        (2, int(cfg["sequence_length"])),
    )
    with torch.no_grad():
        y = hybrid(x)
    rows.append(check(
        "hybrid_forward",
        y.shape == (
            2,
            int(cfg["sequence_length"]),
            256,
        ) and bool(torch.isfinite(y).all()),
        list(y.shape),
    ))
    rows.append(check(
        "eval_suite_frozen",
        len(suite.get("tests", [])) >= 6,
        suite.get("version"),
    ))

    sampled_bytes = (
        int(cfg["steps"])
        * int(cfg["batch_size"])
        * int(cfg["sequence_length"])
    )
    phase1_bytes = (
        phases[0].end_step
        * int(cfg["batch_size"])
        * int(cfg["sequence_length"])
    )
    rows.append(check(
        "training_budget",
        sampled_bytes == 33554432
        and phase1_bytes == 16777216,
        {
            "sampled_bytes": sampled_bytes,
            "phase1_bytes": phase1_bytes,
        },
    ))

    ready = all(row["ok"] for row in rows)
    result = {
        "ready": ready,
        "git_head": head,
        "checks": rows,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if ready else 1)


if __name__ == "__main__":
    main()
