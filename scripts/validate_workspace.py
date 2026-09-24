#!/usr/bin/env python3
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"

errors = []

def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None

manifest = load_json(WORKSPACE / "manifest.json")
if isinstance(manifest, dict):
    if manifest.get("schema") != 1:
        errors.append("workspace/manifest.json: schema must be 1")
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        errors.append("workspace/manifest.json: paths must be an object")

bench_dir = WORKSPACE / "benchmarks"
bench_files = sorted(bench_dir.glob("*.json")) if bench_dir.exists() else []
if not bench_files:
    errors.append("workspace/benchmarks: at least one benchmark JSON is required")

allowed_check_types = {"regex", "contains_all"}
for path in bench_files:
    data = load_json(path)
    if not isinstance(data, dict):
        continue
    if data.get("schema") != 1:
        errors.append(f"{path.relative_to(ROOT)}: schema must be 1")
    if not isinstance(data.get("id"), str) or not data["id"].strip():
        errors.append(f"{path.relative_to(ROOT)}: id is required")
    turns = data.get("turns")
    if not isinstance(turns, list) or not turns:
        errors.append(f"{path.relative_to(ROOT)}: turns must be a non-empty array")
        continue
    seen = set()
    for index, turn in enumerate(turns):
        where = f"{path.relative_to(ROOT)} turn {index}"
        if not isinstance(turn, dict):
            errors.append(f"{where}: turn must be an object")
            continue
        turn_id = turn.get("id")
        if not isinstance(turn_id, str) or not turn_id:
            errors.append(f"{where}: id is required")
        elif turn_id in seen:
            errors.append(f"{where}: duplicate id {turn_id!r}")
        else:
            seen.add(turn_id)
        if not isinstance(turn.get("prompt"), str) or not turn["prompt"].strip():
            errors.append(f"{where}: prompt is required")
        if not isinstance(turn.get("thread"), str) or not turn["thread"].strip():
            errors.append(f"{where}: thread is required")
        checks = turn.get("checks", [])
        if not isinstance(checks, list):
            errors.append(f"{where}: checks must be an array")
            continue
        for check in checks:
            if not isinstance(check, dict):
                errors.append(f"{where}: each check must be an object")
                continue
            kind = check.get("type")
            if kind not in allowed_check_types:
                errors.append(f"{where}: unsupported check type {kind!r}")

for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    lower = path.name.lower()
    if lower.endswith((".gguf", ".safetensors", ".bin")) and "android-plugin" not in path.parts:
        errors.append(f"{path.relative_to(ROOT)}: model/checkpoint binaries must stay out of Git")

if errors:
    print("Workspace validation failed:")
    for error in errors:
        print(" -", error)
    sys.exit(1)

print(f"Workspace valid: {len(bench_files)} benchmark suite(s)")
