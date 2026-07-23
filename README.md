# Local AI Workbench

A local-first Android chat app built as three deliberately separate layers:

- **Godot**: interface, conversation state, model catalogue, and APK shell.
- **Kotlin Godot Android plugin**: downloads, Android storage, lifecycle, and JNI bridge.
- **llama.cpp**: native GGUF inference.

The model weights are not stored in Git. The app downloads approved GGUF files from Hugging Face into its Android app-specific model directory, verifies SHA-256, and then runs them offline.

## Repository layout

```text
app/                 Godot project
android-plugin/      Kotlin/JNI plugin and llama.cpp build
docs/                Architecture and build notes
.github/workflows/   CI that builds the plugin and APK
```

## Current scope

- Download and resume catalogue models.
- SHA-256 verification.
- Load and unload GGUF models.
- Stream generated tokens into Godot.
- Stop generation.
- Persist the current conversation locally.
- Expose context, thread, token, and sampling controls.
- Show backend and generation performance information.
- Build a debug APK in GitHub Actions.

The first backend is optimized ARM CPU inference. GPU/NPU backends stay isolated behind the native layer and can be added without rewriting the Godot interface.

## Build output

The `Build Android APK` workflow produces:

- `LocalAI-debug.aar`
- `LocalAI-release.aar`
- `LocalAIWorkbench-debug.apk`

See `docs/BUILD.md` for details.
