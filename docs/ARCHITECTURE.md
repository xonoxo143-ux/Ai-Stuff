# Architecture — AI Workbench

## Principle

> Stable native Android kernel + mutable GitHub-delivered web workbench.

The active app no longer uses Godot as its application/update architecture. The old Godot implementation remains in the repository only as a reference/fallback prototype and its CI is manual-only.

## Layer 1 — Native Android kernel

`android-shell/` is the durable device layer.

It owns capabilities that genuinely require an APK/native boundary:

- Android lifecycle and secure WebView host
- app-private storage
- model download/resume + SHA-256 verification
- Android-Keystore-backed credential storage
- llama.cpp/JNI runtime
- GGUF load/unload
- cancellation
- native performance measurement
- GitHub workbench bundle updater
- append-only result upload

The kernel exposes a narrow message API to the workbench. The WebView bridge uses `WebViewCompat.addWebMessageListener` restricted to the local `appassets.androidplatform.net` origin; it does not use a globally exposed `addJavascriptInterface`.

## Layer 2 — Mutable web workbench

`workbench-web/` contains ordinary application behavior:

- HTML
- CSS
- JavaScript
- Run / Chat / Bench / Data surfaces
- prompt construction
- conversation state
- benchmark orchestration
- result formatting
- update controls

This layer is intentionally replaceable without rebuilding the APK.

The APK includes a bundled fallback workbench. A verified newer bundle in app-internal storage overrides it.

## Layer 3 — llama.cpp

The current native path is ARM64 CPU with:

- `GGML_CPU_KLEIDIAI=ON`
- `GGML_NATIVE=OFF`
- `GGML_CPU_REPACK=ON`
- `GGML_OPENMP=OFF`
- `GGML_LLAMAFILE=OFF`
- `LLAMA_OPENSSL=OFF`
- forced optimized C/C++ native flags even in the debug-signed APK

KleidiAI is compiled into the native library and selects compatible Arm kernels at runtime.

The generation loop also keeps a token/KV prefix cache. A subsequent prompt reuses the longest exact token prefix and evaluates only the suffix when possible.

Streaming is chunked across JNI rather than emitting one Java/Godot callback per token.

Backend metrics separate:

```text
prompt token count
cached prompt tokens
evaluated prompt tokens
prompt processing time
TTFT
decode tokens/s
total latency
```

## Update flow

GitHub Actions owns the mutable-workbench build:

```text
workbench-web/
      ↓
validate JS + benchmark JSON
      ↓
build workbench.zip
      ↓
GitHub OIDC/Sigstore artifact attestation
      ↓
workspace/releases/workbench.zip
workspace/releases/current.json
      ↓
phone checks manifest
      ↓
repo/ref/kernel compatibility + SHA-256 verification
      ↓
safe unzip to app-internal storage
      ↓
atomic activation
      ↓
reload WebView
```

The manifest records the GitHub attestation URL and source commit.

### Current trust boundary

GitHub Actions currently generates a real keyless Sigstore/GitHub artifact attestation for each workbench bundle. The Android kernel currently enforces the expected repository, expected branch/ref, kernel compatibility, approved raw-GitHub URL, and exact SHA-256 before activation.

The kernel does **not yet perform full Sigstore attestation verification on-device**. Do not describe the current device-side check as attestation verification until that verifier is implemented.

No user-provided signing key is required for workbench releases.

## GitHub result flow

Model weights remain local.

Small experiment outputs can be pushed append-only:

```text
phone
  ↓
devices/<device-id>/results/<file>.json
```

Pull/update of the public workbench needs no GitHub credential. Result pushes currently require a fine-grained Contents-write token stored through Android Keystore.

## Legacy Godot implementation

The old `app/` + `android-plugin/` implementation proved:

- Android/JNI/llama.cpp model loading works on the physical phone
- first benchmark execution works
- the original inference path was far too slow
- fixed 9:16 Godot scaling was unsuitable on the Fold outer display

It is retained as a before-baseline and historical implementation, not the active trajectory.

## Hardware falsification target

The first native-kernel phone test should use the same 360M Q4 model as the Godot baseline and measure:

1. prompt tokens,
2. cached prompt tokens,
3. evaluated prompt tokens,
4. prompt tok/s,
5. TTFT,
6. decode tok/s.

The second same-thread turn should show substantial prefix reuse. If the 360M model still crawls after optimized KleidiAI + KV reuse + chunked streaming, treat that as evidence of a deeper native/runtime issue rather than normal phone performance.
