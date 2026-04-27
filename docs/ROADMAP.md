# LocalAI Lab Roadmap

## v0: APK loop

Goal: prove that GitHub can build and deliver an installable debug APK from `TEST-2`.

Acceptance:

- App installs on Android.
- App launches.
- Status screen renders.
- Delivery workflow posts a usable APK link.

## v1: diagnostics

Add practical diagnostics for phone testing:

- storage visibility
- app data directory
- Android API details
- model file placeholder checks
- basic log copy/export path

## v2: runtime decision

Choose first local inference route after the APK loop is stable.

Candidates:

- llama.cpp native library
- ONNX Runtime
- ExecuTorch
- MLC
- WebView/Transformers.js experiment

## v3: first local model test

Wire one small model path and show honest runtime status. No fake AI claims.
