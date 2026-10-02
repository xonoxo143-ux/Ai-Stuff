#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-configs/v0_first_run.json}"
MAX_STEP="${MAX_STEP:-256}"
PRECISION="${PRECISION:-fp32}"
FUSED_ADAMW="${FUSED_ADAMW:-0}"
RESUME="${RESUME:-0}"
RUN_ROOT="${RUN_ROOT:-runs/delta-v1-t4-pair}"

python3 - <<'PY'
import torch
if not torch.cuda.is_available() or torch.cuda.device_count() < 2:
    raise SystemExit("run_delta_v1_t4_pair.sh requires two visible CUDA GPUs")
print({
    "cuda_count": torch.cuda.device_count(),
    "cuda_devices": [torch.cuda.get_device_name(i) for i in range(2)],
})
PY

mkdir -p "$RUN_ROOT"
extra=()
if [[ "$FUSED_ADAMW" == "1" ]]; then extra+=(--fused-adamw); fi
resume=()
if [[ "$RESUME" == "1" ]]; then resume+=(--resume); fi
python3 -m agent_language.train_v0 \
  --config "$CONFIG" --model delta \
  --run-dir "$RUN_ROOT/delta" --max-step "$MAX_STEP" \
  --device cuda:0 --execution chunked --precision "$PRECISION" \
  "${extra[@]}" "${resume[@]}" >"$RUN_ROOT/delta.log" 2>&1 &
pid_d=$!

python3 -m agent_language.train_v0 \
  --config "$CONFIG" --model transformer \
  --run-dir "$RUN_ROOT/transformer" --max-step "$MAX_STEP" \
  --device cuda:1 --execution reference --precision "$PRECISION" \
  "${extra[@]}" "${resume[@]}" >"$RUN_ROOT/transformer.log" 2>&1 &
pid_t=$!

set +e
wait "$pid_d"; rc_d=$?
wait "$pid_t"; rc_t=$?
set -e

echo "delta_exit=$rc_d transformer_exit=$rc_t"
tail -n 8 "$RUN_ROOT/delta.log" || true
tail -n 8 "$RUN_ROOT/transformer.log" || true
python3 - "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for name in ("delta", "transformer"):
    path = root / name / f"{name}.json"
    if not path.exists():
        print(json.dumps({"model": name, "metrics": "missing"}))
        continue
    data = json.loads(path.read_text())
    print(json.dumps({
        "model": name,
        "parameters": data.get("parameters"),
        "step": data.get("step"),
        "valid_bits_per_byte": data.get("valid_bits_per_byte"),
        "phase_valid_bits_per_byte": data.get("phase_valid_bits_per_byte"),
        "elapsed_seconds": data.get("elapsed_seconds_this_invocation"),
        "cumulative_throughput": data.get("cumulative_throughput"),
        "runtime": data.get("runtime"),
    }, sort_keys=True))
PY

if [[ "$rc_d" -ne 0 || "$rc_t" -ne 0 ]]; then
  exit 1
fi
