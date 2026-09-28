# Agent language-spine screen

**Date:** 2026-09-28  
**Status:** control/reference screen  
**Runtime contract:** `agent_runtime.LanguageBackend`

## Goal

Choose the first practical language spine by experiment, not architecture preference.

Every candidate must run behind the same Agent runtime contract and be compared both:

1. alone as a language baseline;
2. inside the hybrid runtime with memory/capability contributions.

## First comparison set

### A — dense Transformer baseline

**Qwen3-1.7B**

Why:
- compact enough for early local work;
- mature dense Transformer baseline;
- Apache-2.0 model license;
- supported by common local inference stacks.

Purpose:
- establish what the hybrid must beat or extend.

### B — attention + SSM hybrid

**Falcon-H1-1.5B-Instruct**

Why:
- similar scale to the dense baseline;
- explicitly combines Transformer attention with Mamba/SSM machinery;
- official model card documents llama.cpp support.

Purpose:
- test whether hybrid sequence machinery has an intrinsic advantage for our persistent conversational use case before our outer architecture adds anything.

### C — newer recurrent/attention hybrid, exploratory

**Qwen3.5-2B**

Why:
- uses recurrent/linear-attention-style layers with periodic full attention;
- architecturally close to the project's interest in fixed-size persistent state.

Caution:
- current llama.cpp reports include stateful/prefix-cache issues for some Qwen3.5 variants.
- do not make this the first production spine until multi-turn state reuse is verified.

Purpose:
- research candidate, not default.

## Runtime choice

Use an OpenAI-compatible local-server boundary first.

This gives one stable Agent interface while allowing the backend to be:

- llama.cpp;
- another compatible local server;
- a test fake;
- later, a direct in-process backend.

The HTTP boundary is for rapid comparison.

It is not assumed to be the final lowest-latency deployment boundary.

## Metrics

For the same prompt/conversation suite record:

### Quality
- instruction following;
- ordinary conversation;
- multi-topic switching;
- reasoning;
- coding;
- long-turn continuity;
- robustness when external capability facts are injected.

### Runtime
- load time;
- prompt processing;
- time to first token;
- decode tokens/s;
- total latency;
- peak RAM;
- context/state memory;
- second-turn reuse behavior.

### Hybrid compatibility
- ability to consume bounded capability reports;
- ability to use semantic memory without raw transcript replay;
- whether external exact capabilities improve output;
- whether model-only baseline already solves the case;
- integration complexity.

## Decision rule

Do not select a winner from architecture labels.

Select the smallest/cheapest spine that gives enough language quality for the rest of the Agent architecture to matter.

If a denser conventional model dominates quality and real latency, keep it.

If a hybrid model gives materially better state reuse, memory behavior, or quality/cost at similar scale, that is evidence for using hybrid sequence machinery.

## Next implementation step

The runtime now has a generic OpenAI-compatible language backend.

Next:
1. run the same small conversation suite against A and B;
2. add C only after its state-reuse path is verified;
3. keep all prompts/results as comparable artifacts.


## Automated first screen

Workflow:

```text
.github/workflows/agent-language-spine-screen.yml
```

The first rigorous screen runs both candidates sequentially on the **same GitHub Actions runner** using the same pinned llama.cpp release and Q4_K_M quantization.

Initial pair:

```text
ggml-org/Qwen3-1.7B-GGUF:Q4_K_M
tiiuae/Falcon-H1-1.5B-Instruct-GGUF:Q4_K_M
```

Qwen reasoning is disabled for this first small-model latency/quality comparison.

The suite records:

- automatic exact/factual/logic/recall checks;
- raw explanation/code/flexibility responses for manual inspection;
- model-only versus hybrid Agent mode;
- per-turn latency;
- completion-token throughput when the server reports token counts;
- model-server load time;
- process RSS before/after the suite;
- complete server logs and runner information.

This first screen is deliberately small. It chooses what deserves a deeper benchmark; it is not a final language-model ranking.


## Screen 01 protocol correction

The first completed A/B run was informative but **not promoted as a clean comparison**.

Observed in the first run:

- Falcon-H1 baseline passed 10/12 automatic common cases; Qwen3 passed 8/12.
- Qwen3 in hybrid mode consumed the exact arithmetic capability and semantic-memory item correctly.
- Falcon-H1 in hybrid mode ignored both in this prompt format.

However, hybrid mode also carried the semantic-memory item into unrelated cases. That changed the model prompt even when no relevant capability was needed and created a confound in baseline-vs-hybrid comparisons.

Therefore Screen 01 is retained as a protocol-discovery result, not as a model-selection result.

Screen 02 fixes the design:

- common cases receive identical language-model messages in baseline and hybrid modes unless a capability actually fires;
- semantic memory is injected only into the semantic-memory case;
- arithmetic contributes only when its exact capability offers on the arithmetic expression;
- load/RSS metadata is printed to logs as well as preserved in the artifact.

The model choice remains **open** until the corrected run completes.


## Main-path correction

This screen no longer chooses the primary Agent language implementation.

The project now builds its own trainable language organ under `agent_language/`.

Qwen, Falcon-H1, and other imported models remain useful controls that answer:

> What quality/cost/integration behavior does a compact existing LLM provide for free?

They do **not** answer:

> What should the Agent's own language organ be?
