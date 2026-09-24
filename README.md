# AI Workbench

Local-first Android workbench for developing and benchmarking the modular chatbot project.

The `aistuff` branch is the active workspace.

## Goal

Build a local chatbot that improves both useful answer quality and wall-clock efficiency relative to a comparable conventional model.

Storage is a soft constraint. Active compute, latency, memory movement, and quality are the hard measurements.

## Android workbench

The app is deliberately small:

- **Run** — download/load/unload a local GGUF and inspect runtime metrics.
- **Chat** — manual conversation testing with optional useful/poor trace capture.
- **Bench** — run versioned mixed-mode benchmark suites and save per-turn timing/results.
- **Data** — show local workspace/outbox state and configure secure GitHub push credentials.
- **Pull / Push** — sync experiment definitions down and append-only result artifacts up.

The APK contains the stable Android/native layer. Ordinary experiments live under `workspace/` and can change without rebuilding the app.

## Repository role

Git stores:

- source code
- benchmark suites
- configs and manifests
- small logs/results
- architecture notes

Git does **not** store:

- GGUF weights
- safetensors/checkpoints
- large datasets
- training caches

## Runtime stack

```text
Godot UI / experiment runner
        ↓
Kotlin Android bridge
        ↓
llama.cpp (ARM64)
        ↓
local GGUF
```

GitHub sync is separate from inference:

```text
aistuff/workspace
        ↓ Pull
phone local workspace
        ↓ experiment
phone outbox
        ↓ Push
aistuff/devices/<device-id>/results
```

## Performance metrics

The backend records prompt processing separately from decoding:

- prompt token count
- prompt processing time
- time to first token (TTFT)
- generated token count
- generation time
- generation tokens/s
- total turn time

This separation is required for fair performance comparisons.

## Current checkpoint

Before first physical-device testing, CI should be able to:

1. validate workspace/model manifests,
2. compile the Kotlin/JNI plugin and llama.cpp,
3. parse/export the Godot Android app,
4. verify the native backend is packaged,
5. publish a debug APK artifact.

See `docs/WORKBENCH_V0.md` and `docs/ARCHITECTURE.md`.
