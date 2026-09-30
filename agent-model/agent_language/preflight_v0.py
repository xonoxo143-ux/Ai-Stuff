from __future__ import annotations

import json
import subprocess
from pathlib import Path

import torch

from .fetch_v0_sources import SOURCES, sha256_file
from .train_v0 import build_model
from .v0_model import parameter_count


def check(name: str, ok: bool, detail) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    repo = root.parent
    manifest = json.loads(
        (root / "configs" / "corpus_v0_manifest.json").read_text(encoding="utf-8")
    )
    suite = json.loads(
        (root / "configs" / "eval_v0.json").read_text(encoding="utf-8")
    )
    cfg = json.loads(
        (root / "configs" / "v0_first_run.json").read_text(encoding="utf-8")
    )
    rows = []

    train = root / cfg["train_file"]
    valid = root / cfg["valid_file"]
    rows.append(check("train_exists", train.exists(), str(train)))
    rows.append(check("valid_exists", valid.exists(), str(valid)))

    if train.exists():
        actual = sha256_file(train)
        rows.append(check("train_hash", actual == manifest["train_sha256"], actual))
    if valid.exists():
        actual = sha256_file(valid)
        rows.append(check("valid_hash", actual == manifest["valid_sha256"], actual))

    raw = root / "data" / "raw"
    for key, source in SOURCES.items():
        p = raw / source["filename"]
        actual = sha256_file(p) if p.exists() else None
        rows.append(check(f"source_{key}", actual == source["sha256"], actual))

    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain"], text=True
    ).strip()
    rows.append(check("git_clean", not dirty, dirty or "clean"))

    hybrid = build_model("hybrid")
    control = build_model("transformer")
    hp = parameter_count(hybrid)
    cp = parameter_count(control)
    delta = abs(hp - cp) / hp
    rows.append(
        check("parameter_match", delta < 0.02, {
            "hybrid": hp, "control": cp, "delta": delta
        })
    )

    x = torch.randint(0, 256, (2, int(cfg["sequence_length"])))
    with torch.no_grad():
        y = hybrid(x)
    rows.append(check(
        "hybrid_forward",
        y.shape == (2, int(cfg["sequence_length"]), 256)
        and bool(torch.isfinite(y).all()),
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
    rows.append(check(
        "training_budget",
        sampled_bytes >= 2 * int(manifest["train_bytes"]) - 4096,
        {
            "sampled_bytes": sampled_bytes,
            "train_bytes": manifest["train_bytes"],
        },
    ))

    ready = all(row["ok"] for row in rows)
    result = {"ready": ready, "git_head": head, "checks": rows}
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if ready else 1)


if __name__ == "__main__":
    main()
