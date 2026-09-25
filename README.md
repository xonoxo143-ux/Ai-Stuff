# AI Workbench

Local-first Android workbench for developing and benchmarking the modular chatbot project.

The `aistuff` branch is the active workspace.

## Goal

Build a local chatbot that improves both useful answer quality and wall-clock efficiency relative to a comparable conventional model.

Storage is a soft constraint. Active compute, latency, memory movement, and quality are the hard measurements.

## Agent architecture

The Workbench is the laboratory, not the cognitive architecture itself.

The first faithful runtime specification for the agent is now frozen in `docs/AGENT_V0_SPEC.md`.

Agent v0 is defined as a persistent computational ecology with first-class capabilities and interaction motifs, context-sensitive temporary organization, bounded communication, explicit provenance, and a reversible developmental learning path.

## Active Workbench architecture

```text
native Android kernel
├── llama.cpp / ARM64 runtime
├── model storage + downloads
├── secure storage
├── update client
└── secure WebView bridge
          ↓
mutable HTML/CSS/JS workbench
├── Run
├── Chat
├── Bench
└── Data
```

The old Godot implementation remains in the repository as a historical prototype. It is not the current application architecture.

## Update model

Ordinary UI/benchmark/application changes live under `workbench-web/` and should not require another APK.

GitHub Actions:

1. validates the workbench,
2. builds `workbench.zip`,
3. creates a keyless GitHub/Sigstore artifact attestation,
4. publishes a versioned manifest + bundle to `workspace/releases/`.

The native kernel downloads the bundle, checks its source/ref compatibility and SHA-256, safely stages it in app-private storage, and reloads it.

Native changes to llama.cpp/JNI/Android itself still require a new APK.

## Runtime optimization

The native ARM64 path uses KleidiAI and keeps reusable prompt/KV prefixes rather than clearing and recomputing the whole conversation every turn. JNI streaming is chunked to avoid per-token UI bridge overhead.

Measured fields include:

- prompt tokens
- cached prompt tokens
- evaluated prompt tokens
- prompt processing time
- TTFT
- decode tokens/s
- total latency

## Repository role

Git stores source, workbench bundles/manifests, benchmark suites, small results, configs, and architecture notes.

Git does **not** store model weights, large checkpoints, bulky datasets, or training caches.

See `docs/AGENT_V0_SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/WORKBENCH_V0.md`.
