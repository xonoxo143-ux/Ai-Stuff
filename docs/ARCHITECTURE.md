# Architecture — AI Workbench

## Principle

> Stable APK kernel + mutable experiment workspace.

The Android application is not an IDE and GitHub is not model storage. The APK provides durable device/native capabilities; the `aistuff` workspace tells it what experiment to run.

## Layer 1 — Godot

Godot owns user-facing and experiment-level behavior:

- Run / Chat / Bench / Data surfaces
- conversation state
- prompt formatting
- model catalogue
- benchmark execution
- objective benchmark checks
- result serialization
- local workspace/outbox management
- GitHub pull/push protocol

Godot does not perform tensor math.

## Layer 2 — Kotlin Android plugin

`LocalAIPlugin.kt` owns Android-specific/native integration:

- model download/resume
- SHA-256 verification
- app-specific model storage
- stable anonymous device ID
- Android-Keystore-backed secret storage
- JNI calls into llama.cpp
- lifecycle cleanup
- native event forwarding

The GitHub token is encrypted locally and never enters repository files or benchmark artifacts.

## Layer 3 — llama.cpp

The native library owns:

- GGUF loading
- tokenization
- context allocation
- prompt decode
- sampling/decode loop
- cancellation
- timing
- cleanup

Current backend: ARM64 CPU.

Backend-facing metrics intentionally separate:

```text
prompt processing
TTFT
token decode
total latency
```

so optimization does not accidentally improve one stage while hiding regressions in another.

## Mutable workspace

CI copies repository `workspace/` into the APK as the first-run seed.

At runtime it is copied into:

```text
user://workspace/
```

A Pull replaces/adds workspace files from the `aistuff` branch without changing the APK.

Current workspace classes:

```text
workspace/
  manifest.json
  benchmarks/
  presets/
  recipes/
  model-manifests/
```

## Result flow

Benchmarks and selected manual chat traces are saved locally first.

```text
generation
   ↓
user://results/
   +
user://outbox/
   ↓ explicit Push
devices/<device-id>/results/
```

Uploads are append-only in v0. Successful uploads move the local outbox file to `user://sent/`.

No automatic destructive synchronization is allowed in v0.

## Credential boundary

Pulling the public workspace does not require a token.

Pushing requires a fine-grained GitHub token with Contents write permission. On Android it is encrypted with an AES-GCM key held by Android Keystore.

The repository never contains the credential.

## Benchmark boundary

A benchmark suite defines prompts, thread IDs, qualitative criteria, and optional deterministic checks.

The runner preserves history independently per thread. This allows suites to test:

- abrupt mode switching
- returning to earlier threads
- cross-domain reasoning
- objective tasks
- epistemic restraint
- coding
- repeated reusable computation

Qualitative criteria are stored with the response for later judging. They are **not** falsely treated as deterministic scores.

## Large-file boundary

Weights/datasets stay outside Git.

Repository manifests may describe:

- model/source
- filename
- size
- SHA-256
- quantization
- prompt template
- recommended runtime settings

This lets storage scale independently of Git history.

## First physical-device boundary

The phone is not needed to validate application structure.

It becomes necessary for:

- actual ARM throughput
- TTFT
- memory pressure/OOM behavior
- thermal throttling
- battery use
- Android process/lifecycle behavior
- USB vs internal-storage model loading
- Fold UI ergonomics

Everything before those hardware truths should be tested in CI or headless/emulated environments first.
