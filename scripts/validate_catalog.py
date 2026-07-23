#!/usr/bin/env python3
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app" / "data" / "models.json"

def fail(message: str) -> None:
    print(f"catalog error: {message}", file=sys.stderr)
    raise SystemExit(1)

data = json.loads(CATALOG.read_text(encoding="utf-8"))
models = data.get("models")
if not isinstance(models, list) or not models:
    fail("models must be a non-empty list")

seen_ids: set[str] = set()
seen_files: set[str] = set()
required = {"id", "name", "filename", "url", "size_bytes", "sha256", "template", "recommended"}

for index, model in enumerate(models):
    missing = required - model.keys()
    if missing:
        fail(f"model {index} is missing {sorted(missing)}")
    if model["id"] in seen_ids:
        fail(f"duplicate id {model['id']}")
    if model["filename"] in seen_files:
        fail(f"duplicate filename {model['filename']}")
    if not str(model["filename"]).lower().endswith(".gguf"):
        fail(f"{model['filename']} is not a GGUF filename")
    if not str(model["url"]).startswith("https://"):
        fail(f"{model['id']} does not use HTTPS")
    digest = str(model["sha256"]).lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        fail(f"{model['id']} has an invalid SHA-256")
    seen_ids.add(model["id"])
    seen_files.add(model["filename"])

print(f"validated {len(models)} catalogue models")
