from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from .train_v0 import build_model, transformer_generate


def generate_bytes(model, name: str, prompt: str, max_new: int, context: int) -> bytes:
    prefix = prompt.encode("utf-8")
    if name == "hybrid":
        full = model.generate(prompt, max_new_bytes=max_new)
    else:
        full = transformer_generate(model, prompt, max_new, context)
    return full[len(prefix) :]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--model", choices=("hybrid", "transformer"), required=True)
    ap.add_argument("--suite", default="configs/eval_v0.json")
    ap.add_argument("--out")
    args = ap.parse_args()

    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if payload["model_name"] != args.model:
        raise ValueError("checkpoint model mismatch")
    model = build_model(args.model)
    model.load_state_dict(payload["model"])
    model.eval()
    cfg = payload["config"]
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))

    rows = []
    for test in suite["tests"]:
        raw = generate_bytes(
            model,
            args.model,
            test["prompt"],
            int(test.get("max_new_bytes", 200)),
            int(cfg["sequence_length"]),
        )
        text = raw.decode("utf-8", errors="replace")
        required_all = test.get("required_all", [])
        required_any = test.get("required_any", [])
        low = text.casefold()
        all_ok = all(str(v).casefold() in low for v in required_all)
        any_ok = (
            any(str(v).casefold() in low for v in required_any)
            if required_any
            else True
        )
        replacement_rate = text.count("\ufffd") / max(1, len(text))
        rows.append(
            {
                "id": test["id"],
                "pass": bool(all_ok and any_ok),
                "required_all_ok": all_ok,
                "required_any_ok": any_ok,
                "replacement_rate": replacement_rate,
                "continuation": text,
            }
        )

    result = {
        "suite": suite["version"],
        "model": args.model,
        "checkpoint_step": int(payload["step"]),
        "passes": sum(int(row["pass"]) for row in rows),
        "total": len(rows),
        "rows": rows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
