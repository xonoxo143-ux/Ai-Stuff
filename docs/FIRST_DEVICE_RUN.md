# Physical-Device Checkpoint — Native Kernel

## Baseline already established

The original Godot implementation proved the full Android -> JNI -> llama.cpp path could load the 360M Q4 model, but the physical-device benchmark exposed unacceptable performance:

- Turn 1 streamed slowly.
- Turn 2 had a blank-response TTFT of at least ~52 seconds in the recorded session.
- The old runtime cleared KV state every turn and recomputed full thread history.
- Streaming crossed the native/UI bridge per token and repeatedly redrew accumulated output.
- The native build did not use the current optimized KleidiAI Android path.

Keep the old app installed temporarily as the before-baseline.

## Native-kernel candidate

The replacement app is a separate Android package:

- package: `com.xonoxo.aiworkbench`
- kernel version: 1
- app version: `0.3.0-kernel1`
- workflow run: `36064813529`
- artifact id: `10836101506`
- APK SHA-256: `3f95c3683d6cf72c7aff12a67cb892ac6104f640a85dfec38b6ee0ea5e0eaf4a`
- GitHub artifact attestation: `https://github.com/xonoxo143-ux/Ai-Stuff/attestations/50006854`

CI verified the APK signature, package id, launcher activity, native ARM64 library, bundled fallback web workbench, and benchmark payload.

The native library contains KleidiAI kernels and is built with Android-safe llama.cpp settings plus forced optimized native flags.

## Mutable workbench release

The phone can update ordinary UI/benchmark/application behavior without another APK.

Current release manifest lives at:

`workspace/releases/current.json`

The release workflow:

1. validates JS and benchmark JSON,
2. builds `workbench.zip`,
3. generates a GitHub OIDC/Sigstore artifact attestation,
4. publishes the bundle + manifest to `aistuff`.

The kernel currently enforces the expected repo/ref, kernel compatibility, approved raw-GitHub URL and SHA-256 before activation. Full Sigstore verification is not yet performed on-device.

## Next phone session

Do **not** run the full 13-turn benchmark first.

1. Install the native-kernel APK beside the old app.
2. Open it and confirm Run / Chat / Bench / Data appear.
3. Check/apply the GitHub workbench update if offered.
4. Download the same SmolLM2 360M Q4_K_M validation model in the new app.
5. Load it with context 2048 and 4 threads.
6. Send one short chat prompt.
7. Record:
   - prompt tokens
   - cached prompt tokens
   - evaluated prompt tokens
   - prompt tok/s
   - TTFT
   - decode tok/s
   - total time
8. Send a second message in the same chat.
9. Verify the second turn reports substantial cached-prefix reuse.
10. Only then run the first two benchmark turns.

## Pass/fail

The new architecture must show a large improvement over the recorded Godot baseline.

The critical second-turn invariant is:

```text
cached_prompt_tokens >> 0
evaluated_prompt_tokens << prompt_tokens
```

If that does not hold, fix KV-prefix reuse before doing broader benchmarking.

If prefix reuse works but a 360M Q4 model still has extremely poor prefill/decode throughput, investigate the native CPU backend/hardware dispatch rather than accepting the result as normal phone performance.

## After this test

Once the kernel is validated, ordinary workbench changes should ship through GitHub bundle updates rather than APK rebuilds. Native APK rebuilds are reserved for real kernel/backend changes.
