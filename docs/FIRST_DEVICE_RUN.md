# First Physical-Device Checkpoint

Do not involve the phone until CI produces a clean APK artifact.

## What should already work before installation

- Run / Chat / Bench / Data tabs parse and export.
- llama.cpp ARM64 backend compiles.
- model download/resume + SHA-256 verification compiles.
- prompt processing, TTFT, decode rate, and total latency are reported separately.
- bundled workspace seeds first-run state.
- Pull updates workspace files from the `aistuff` branch.
- benchmark suites preserve independent thread histories.
- benchmark results are saved locally and copied to an explicit outbox.
- GitHub push credentials are encrypted using Android Keystore.
- Push writes append-only result files under `devices/<device-id>/results/`.

## First device session

The first session is intentionally narrow:

1. Install the CI APK.
2. Launch AI Workbench.
3. Pull workspace.
4. Download the tiny validation GGUF.
5. Load it.
6. Send one chat message.
7. Run `chatbot-v0`.
8. Configure the GitHub token once.
9. Push outbox.
10. Let ChatGPT inspect the uploaded result.

## What the phone is testing

This is not a model-quality test yet.

The first phone session establishes:

- real ARM64 model loading,
- RAM behavior,
- TTFT,
- prompt-processing rate,
- decode tokens/s,
- Android lifecycle stability,
- download/storage behavior,
- UI ergonomics,
- phone → GitHub result flow.

Only after that path works should larger candidate models be introduced.


## Validated candidate

The first phone candidate passed the full no-device CI gate on 2026-09-24.

- branch: `aistuff`
- source commit: `1144f77619c2494dfe413a89628e7217899b2bf8`
- workflow run: `36035508348`
- artifact: `LocalAIWorkbench-Android` (artifact id `10824421913`)

CI verified:

- workbench/catalog JSON validity,
- Godot script parsing,
- ARM64 llama.cpp/plugin compilation,
- deterministic Gradle-template installation,
- APK export,
- APK signature validity,
- package id `com.xonoxo.localaiworkbench`,
- launchable activity presence,
- packaged `liblocal_ai.so`,
- bundled workspace manifest and `chatbot-v0`,
- packaged Run/Chat/Bench/Data workbench scripts.

The catalogue's two initial GGUF filenames and SHA-256 values were also rechecked against their current Hugging Face file metadata before this checkpoint.

At this point the remaining unknowns are physical-device properties: Android launch/runtime behavior, model download/load, ARM64 inference, RAM/thermal behavior, UI ergonomics, and phone-to-GitHub push.
