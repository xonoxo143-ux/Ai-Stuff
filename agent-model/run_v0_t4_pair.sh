#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONFIG="${CONFIG:-configs/v0_first_run.json}"
MAX_STEP="${MAX_STEP:-256}"
PRECISION="${PRECISION:-fp32}"
FUSED_ADAMW="${FUSED_ADAMW:-0}"
RESUME="${RESUME:-0}"
RUN_ROOT="${RUN_ROOT:-runs/v0-t4-causal-pair}"

python3 - <<'PY'
import torch
if not torch.cuda.is_available() or torch.cuda.device_count() < 2:
    raise SystemExit("run_v0_t4_pair.sh requires at least two visible CUDA GPUs")
print({"cuda_devices": [torch.cuda.get_device_name(i) for i in range(2)]})
PY

mkdir -p "$RUN_ROOT"
extra=()
if [[ "$FUSED_ADAMW" == "1" ]]; then extra+=(--fused-adamw); fi
resume=()
if [[ "$RESUME" == "1" ]]; then resume+=(--resume); fi

python3 -m agent_language.train_v0 \
  --config "$CONFIG" --model hybrid \
  --run-dir "$RUN_ROOT/hybrid" --max-step "$MAX_STEP" \
  --device cuda:0 --execution vectorized --precision "$PRECISION" \
  "${extra[@]}" "${resume[@]}" >"$RUN_ROOT/hybrid.log" 2>&1 &
pid_h=$!

python3 -m agent_language.train_v0 \
  --config "$CONFIG" --model transformer \
  --run-dir "$RUN_ROOT/transformer" --max-step "$MAX_STEP" \
  --device cuda:1 --execution reference --precision "$PRECISION" \
  "${extra[@]}" "${resume[@]}" >"$RUN_ROOT/transformer.log" 2>&1 &
pid_t=$!

set +e
wait "$pid_h"; rc_h=$?
wait "$pid_t"; rc_t=$?
set -e

echo "hybrid_exit=$rc_h transformer_exit=$rc_t"
tail -n 5 "$RUN_ROOT/hybrid.log" || true
tail -n 5 "$RUN_ROOT/transformer.log" || true

python3 - "$RUN_ROOT" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
for name in ("hybrid", "transformer"):
    p=root/name/f"{name}.json"
    if not p.exists():
        print(json.dumps({"model":name,"metrics":"missing"}))
        continue
    d=json.loads(p.read_text())
    print(json.dumps({
        "model":name,
        "step":d.get("step"),
        "valid_bits_per_byte":d.get("valid_bits_per_byte"),
        "elapsed_seconds":d.get("elapsed_seconds_this_invocation"),
    }, sort_keys=True))
PY

if [[ "$rc_h" -ne 0 || "$rc_t" -ne 0 ]]; then exit 1; fi
