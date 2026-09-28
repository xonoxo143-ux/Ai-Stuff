# Agent language-spine Screen 01 — protocol-discovery result

**Date:** 2026-09-28  
**Workflow run:** `36388837409`  
**Conclusion:** successful execution; comparison partially confounded; no model promoted

## Models

Same GitHub Actions runner, pinned llama.cpp v0.5.0, Q4_K_M:

- `ggml-org/Qwen3-1.7B-GGUF:Q4_K_M`
- `tiiuae/Falcon-H1-1.5B-Instruct-GGUF:Q4_K_M`

Qwen reasoning was disabled.

## Raw automatic summary

### Qwen3-1.7B

```text
model-only common:  8 / 12
hybrid common:     12 / 12
hybrid total:      14 / 14
```

Model-only failed the repeated trap-reasoning and large-arithmetic cases.

With the Agent layer:
- exact arithmetic was consumed correctly;
- semantic memory `favorite_fruit=mango` was consumed correctly;
- common automatic cases all passed.

### Falcon-H1-1.5B-Instruct

```text
model-only common: 10 / 12
hybrid common:     10 / 12
hybrid total:      10 / 14
```

Model-only solved the trap-reasoning case but failed large arithmetic.

In hybrid mode:
- the arithmetic capability report was ignored;
- semantic memory was ignored and the model answered `Apple`.

## Why this is not yet a winner

The hybrid runtime seeded `favorite_fruit=mango` for **all** hybrid cases, not only the memory case.

Therefore the common baseline and hybrid prompts were not strictly matched. The unrelated memory context may have changed deterministic generations, including the Qwen trap-reasoning result.

This makes the large Qwen hybrid improvement unsuitable as clean causal evidence.

## Durable observation

One observation survives the confound as a useful integration hypothesis:

> In Screen 01's capability-report format, Qwen3 consumed the provided arithmetic and semantic-memory information while Falcon-H1 did not.

This must replicate under the corrected prompt-matching protocol before it guides architecture.

## Correction

Screen 02 changes the harness so:

- irrelevant semantic memory is absent;
- common baseline/hybrid prompts are identical when no capability fires;
- semantic memory appears only in its dedicated case;
- arithmetic changes only the arithmetic hybrid case.

Screen 01 remains preserved because discovering benchmark confounds early is part of the architecture evidence.
