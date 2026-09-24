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
