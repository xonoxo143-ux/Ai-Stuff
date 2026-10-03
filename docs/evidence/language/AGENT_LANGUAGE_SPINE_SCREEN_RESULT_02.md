# Agent language-spine Screen 02 — corrected control result

**Date:** 2026-09-28  
**Workflow run:** `36391764954`  
**Status:** CONTROL / REFERENCE RESULT  
**Purpose:** measure what compact imported LLMs provide inside the Agent shell; not choose the main Agent language path.

## Protocol

Same GitHub runner, pinned llama.cpp v0.5.0, Q4_K_M.

Common baseline/hybrid cases had matched model input unless an Agent capability actually fired.

Semantic memory appeared only in the dedicated semantic-memory case.

## Qwen3-1.7B

```text
model-only common automatic: 8 / 12
hybrid common automatic:    10 / 12
hybrid total automatic:     12 / 14
```

Stable behavior across both repeats:

- simple instruction, logic, factual, and two-turn recall passed;
- trap-reasoning prompt returned 17 rather than 9 in both modes;
- model-only multiplication was wrong;
- hybrid multiplication used the exact arithmetic capability correctly;
- hybrid semantic-memory query returned `mango`.

Runner/process observations:

```text
server readiness: ~20.1 s
RSS before suite: ~2.23 GB
RSS after suite:  ~2.31 GB
```

## Falcon-H1-1.5B-Instruct

```text
model-only common automatic: 10 / 12
hybrid common automatic:     10 / 12
hybrid total automatic:      10 / 14
```

Stable behavior across both repeats:

- trap-reasoning prompt correctly returned 9;
- multiplication was wrong in both modes;
- the exact arithmetic capability report was not used;
- semantic memory `favorite_fruit=mango` was not used; response was `Apple`;
- two-turn transcript recall passed.

Runner/process observations:

```text
server readiness: ~54.2 s
RSS before suite: ~1.77 GB
RSS after suite:  ~2.83 GB
```

## What this result means

At this tiny screen:

- Falcon-H1 had the stronger standalone automatic score.
- Qwen3 integrated more successfully with the Agent's current bounded capability/memory-report format.
- Neither result establishes a final language architecture.

The main Agent build path now develops its own trainable language organ.

These models remain useful controls for:

- conversational quality;
- runtime cost;
- capability integration;
- eventual end-to-end comparisons.
