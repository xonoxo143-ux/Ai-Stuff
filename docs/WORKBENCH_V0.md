# AI Workbench v0

## Purpose

The Android app is a small local-first control surface for AI experiments.

It is not an IDE. It is not the model repository. It is not the training backend.

The stable APK owns Android integration and local inference. The `aistuff` branch acts as a lightweight control plane for experiment definitions, configs, manifests, and small results.

## Design rule

> Stable APK kernel + mutable workspace.

The APK should change only when native/app capabilities change. Ordinary experiments should be updateable by pulling workspace files from GitHub.

## Stable APK responsibilities

- Android UI and lifecycle
- secure GitHub credentials
- local storage access
- llama.cpp native runtime
- GGUF model loading/unloading
- streamed generation
- local performance measurement
- benchmark execution
- local conversation state
- workspace sync
- import/export of user-selected files

Model weights and large datasets remain local and are referenced by manifest.

## Initial surfaces

### Run

Minimal runtime control:

- selected model
- load/start
- unload/stop
- model status
- RAM / model size
- context size
- threads / backend
- TTFT
- generation tokens/s
- active workspace revision

### Chat

Normal local chat surface for manual testing.

Useful controls:

- model
- system preset
- context/sampling controls
- stop generation
- save run
- mark response useful / poor
- send selected run to outbox

### Bench

Run declarative benchmark suites from the workspace.

Show:

- current case / total
- TTFT
- generation speed
- total turn latency
- objective checks
- saved result path

Results are written locally first and can then be pushed to GitHub.

### Data

Import files/folders and classify them without assuming they are immediately used for training.

Initial tags:

- reference
- training-candidate
- evaluation
- benchmark
- archive

Large files stay local. GitHub receives metadata/hash manifests unless a file is intentionally small enough to commit.

## Sync model

Two primary actions:

- PULL WORKSPACE
- PUSH OUTBOX

Pull updates declarative project state such as:

- benchmark definitions
- prompt/system presets
- model manifests
- experiment recipes
- routing/settings configs

Push uploads small append-only artifacts such as:

- benchmark results
- device profile
- selected chat traces
- logs
- experiment status
- data manifests

Avoid automatic destructive sync in v0.

## Repository layout

```text
workspace/
  manifest.json
  benchmarks/
  presets/
  recipes/
  model-manifests/

devices/
  <device-id>/
    profile.json
    results/
    logs/
    outbox/

docs/
  WORKBENCH_V0.md
```

The directories under `devices/` are created lazily by the client.

## Local-only layout

Suggested Android-side workspace:

```text
files/
  models/
  datasets/
  workspace/
  conversations/
  results/
  outbox/
```

Weights and bulky datasets are never required to enter Git.

## Declarative experiment contract

Experiments should be data when possible rather than downloaded executable code.

Example:

```json
{
  "schema": 1,
  "id": "chatbot-baseline-v0",
  "type": "benchmark",
  "suite": "benchmarks/chatbot-v0.json",
  "model": "selected",
  "generation": {
    "temperature": 0.7,
    "max_tokens": 512
  }
}
```

This lets ChatGPT change benchmark logic, prompts, settings, and test sequences through GitHub without rebuilding the APK.

## Native-code rule

Do not use arbitrary remote executable code as the normal update path.

Native/runtime changes should normally ship in a new APK. A later signed-pack mechanism may be added deliberately if it becomes useful.

## Model storage

Model manifests may be committed.

Model weights remain local or come from an external model host.

A model manifest should eventually include:

- stable id
- display name
- source URL/repository
- expected filename
- byte size
- SHA-256
- quantization
- architecture
- prompt/chat template
- recommended context
- recommended runtime settings

## Job protocol — later, but keep the door open

The workbench should eventually support abstract executors:

```text
Executor
  Local llama.cpp
  Local benchmark
  Remote job
```

A remote job can initially use GitHub itself as a mailbox:

```text
jobs/pending/<id>.json
jobs/results/<id>.json
```

This lets a phone request work from another machine without turning the Android app into a remote-desktop or editor.

## v0 non-goals

- full code editor
- arbitrary shell
- arbitrary remote binary execution
- on-device large-model training
- Git as model-weight storage
- automatic merge-conflict resolution
- sophisticated autonomous SkillGraph learning

Those can be added only when a measured need appears.

## First success criterion

The app is useful when it can:

1. pull a benchmark/config change from `aistuff`,
2. load a local GGUF,
3. run a chat or benchmark,
4. record real device timing and quality data,
5. push the resulting small artifact back to the branch,

without rebuilding the APK.


## Update architecture — required before the next APK

The next physical APK should establish a permanent separation between the native kernel and the mutable workbench.

### APK kernel

Rebuilding/reinstalling the APK should only be necessary for changes such as:

- Android manifest or permissions,
- Godot engine version,
- Kotlin/JNI bridge changes,
- llama.cpp/native library changes,
- cryptographic trust-root changes,
- capabilities that cannot be represented by the mutable Godot layer.

### GitHub-delivered workbench layer

Ordinary changes should not require a new APK. This includes:

- UI layout and styling,
- Run / Chat / Bench / Data screens,
- GDScript behavior,
- benchmark logic,
- prompts and presets,
- model catalogue/manifests,
- experiment recipes,
- routing/configuration,
- most non-native bug fixes.

Godot supports runtime PCK/ZIP resource packs containing scenes, scripts, and assets. The kernel should use a small immutable bootstrap that loads a verified workbench pack before loading the main workbench scene.

### Proposed flow

```text
APK launches immutable bootstrap
        |
        v
check user://updates/current.pck
        |
        +-- valid + compatible --> load_resource_pack(..., true)
        |                         |
        |                         v
        |                   launch workbench
        |
        +-- missing/invalid --> launch bundled fallback workbench
```

The Pull action should also check a GitHub update manifest:

```text
workspace/app-update.json
```

Suggested fields:

```json
{
  "schema": 1,
  "channel": "aistuff",
  "version": 1,
  "kernel_min": 1,
  "kernel_max": 1,
  "pack": {
    "path": "workspace/releases/workbench-v1.pck",
    "sha256": "...",
    "signature": "..."
  }
}
```

Update sequence:

1. Pull update manifest.
2. Compare version and kernel compatibility.
3. Download the new PCK into app-internal storage as a staging file.
4. Verify SHA-256.
5. Verify an asymmetric signature using a public key embedded in the APK kernel.
6. Atomically promote staging to `current.pck`.
7. Restart/reload through the bootstrap.
8. If loading fails, disable the pack and fall back to the bundled workbench.

The pack must be loaded before the main workbench scene/scripts are loaded so it can replace those resources cleanly.

### Security rule

Do not trust a PCK merely because it came from GitHub or because its SHA-256 matches a manifest downloaded from the same location.

Patch packs can contain executable GDScript. The kernel therefore needs an embedded public verification key and should load only packs signed by the corresponding private key. Store downloaded packs only in app-internal storage.

### Practical result

After this kernel ships, a change like mobile scaling, button layout, benchmark behavior, or a new workbench screen should become:

```text
edit in aistuff
-> CI builds signed workbench PCK
-> phone taps Pull (or checks on launch)
-> pack downloads and verifies
-> restart workbench
```

No APK reinstall.

