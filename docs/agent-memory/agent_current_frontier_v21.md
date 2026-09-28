# Agent Current Frontier

**Version:** 2.1  
**Date:** 2026-09-28  
**Role:** shortest current-state file. Update this after every meaningful experiment cycle.

## Current state

The project has two active tracks.

### Track A — developmental mechanism

Established:
- destructive forgetting exists;
- destructive private-cell updates can be localized post hoc;
- localization replicated on fresh seeds;
- simple one-shot prospective per-cell predictors are weak.

Current uncertainty:

> Is destructive interference predictable from **update trajectory/history or interactions**, or is the better solution to route new learning into spare capacity rather than predict danger precisely?

Next high-information experiment should distinguish at least these explanations:

1. **trajectory/history hypothesis**  
   Danger accumulates across a sequence of updates and cannot be inferred from one gradient snapshot.

2. **interaction hypothesis**  
   Destructive effects depend on combinations of cell updates, so per-cell pre-update scores are structurally insufficient.

3. **spare-capacity hypothesis**  
   Avoiding overlap may matter more than predicting exactly which old parameters are vulnerable.

Do not add a complex online plasticity controller before one of these earns support.

### Track B — chatbot integration

Goal:
Build the first hybrid chatbot bottom-up without waiting for every developmental mechanism to be finished.

Current direction:
1. build the Agent's own trainable language organ from scratch;
2. keep compact pretrained LLMs as controls/reference systems;
3. compare byte-recurrent, byte-attention, and multiscale candidates cheaply;
4. move survivors to a small real-language curriculum;
5. train the language organ to accept a bounded non-language conditioning state;
6. integrate it with the existing capability/memory runtime;
7. then bring developmental machinery in where it has a clear job.

## Development loop

```text
READ CURRENT DOCS
→ identify weakest assumption
→ RESEARCH prior solutions/failures
→ define smallest discriminating experiment
→ IMPLEMENT
→ run fast tests / ablations / combinations
→ FALSIFY / COMPARE
→ integrate only what survives
→ UPDATE docs + evidence + frontier
→ periodic end-to-end prototype
→ repeat
```

## Immediate documentation rule

After each cycle:
- update this file first;
- update Evidence Ledger only for durable results;
- update Decision Ledger only if architecture changed;
- save exact experiment/result separately;
- never append another competing "current" section to the archive.

## Integration progress — 2026-09-28

The bottom-up chatbot runtime has now started.

Implemented:

- lightweight standalone `agent_runtime` package, separate from the PyTorch developmental ecology;
- bounded capability offer/run contract;
- active/episodic/semantic/capability-memory separation;
- turn provenance and latency/error tracing;
- swappable OpenAI-compatible / llama.cpp language backend;
- reproducible language-spine benchmark harness;
- first durable SQLite memory backend with restart continuity.

The first same-runner Qwen3-1.7B vs Falcon-H1-1.5B model screen is automated in GitHub Actions.

This does not change the developmental Track A result: simple one-shot destructive-update predictors remain weak.


## Language-path correction — 2026-09-28

The main build path no longer assumes an imported pretrained LLM as the language spine.

Existing Qwen/Falcon screens are retained as **controls**.

A new `agent_language` package now tests language machinery trained from scratch.

First local ~130k-150k-parameter byte-level comparison at 160 updates:

```text
GRU          ~1.67 bits/byte
Transformer  ~2.62 bits/byte
Patch RNN    ~3.31 bits/byte
```

The Transformer trained much faster; the GRU had substantially better held-out loss at the same update budget; the first fixed-patch multiscale formulation lost.

This is only a one-seed synthetic result.

Current rigorous gate:

```text
five-seed parameter-matched language-organ replication
→ then small real-language training for survivors
```

Every candidate exposes a small external conditioning vector so future Agent cognition can drive language without requiring all internal state to be serialized as prompt text.


### External-state language seam

The language-organ conditioning contract was corrected so Agent state is available persistently during generation and zero condition is neutral.

A local compositional probe held out 64 combinations of structured non-language state.

After 300 tiny updates:

```text
GRU          64 / 64 exact
Transformer  64 / 64 exact
```

This does not establish natural-language intelligence.

It establishes the interface property we wanted:

```text
non-language Agent state
→ bounded latent condition
→ from-scratch language organ
→ compositional English
```

The replicated workflow now tests both surface byte modeling and this external-state composition seam.


## Replicated language-organ gate

Workflow `36394549359` completed successfully.

Five-seed synthetic surface-language result:

```text
GRU          mean 2.002 bits/byte   5/5 validation wins
Transformer  mean 2.606 bits/byte   0/5 validation wins
Patch RNN    mean 3.381 bits/byte   0/5 validation wins
```

The Transformer trained roughly 2.5× faster than the GRU.

The fixed-patch RNN is removed from the main path.

The external-state→English seam also replicated:

```text
GRU          64/64 exact, 3/3 seeds
Transformer  64/64 exact, 3/3 seeds
```

Current next gate is the mirror interface:

```text
English bytes
→ small perception organ
→ bounded non-language state
```

The perception probe deliberately holds out both sentence forms and semantic combinations. It compares unidirectional GRU, bidirectional GRU, and Transformer encoders.

This begins testing whether language perception and language production should specialize into different architectures.


## First real-language production screen

The replicated synthetic production gate is complete, so the next stage has started.

Two surviving from-scratch production organs are scaled modestly:

```text
GRU          ~0.8M parameters
Transformer  ~0.93M parameters
```

Both remain raw-byte models with random initialization and the persistent external Agent-state conditioning seam.

A bounded TinyStories slice is used as training text only.

The first real-text workflow trains both on the same data for 800 updates, records held-out bits/byte, saves our checkpoints, and emits short greedy samples.

This is intentionally small enough to remain a screening experiment rather than a large training project.


## Replicated language-perception gate

Workflow `36435692995` completed successfully.

Three-seed controlled semantic-extraction result:

```text
BiGRU          72.0% exact   91.6% slot accuracy
GRU            36.3% exact   75.9% slot accuracy
Transformer    36.3% exact   77.9% slot accuracy
```

Transformer perception remained much faster to train, but BiGRU generalized substantially better.

The next cheap refinement keeps the BiGRU sequence encoder and replaces the single whole-sentence summary with **four learned semantic-slot queries**.

A local 100-update check improved exact-state recovery from roughly 38% to 62% on the same held-out split, so the attentive-BiGRU variant has entered replicated testing.

Current language specialization picture:

```text
production surface modeling:
  GRU quality lead / Transformer speed lead

perception:
  BiGRU quality lead
  Transformer speed lead
  attentive-BiGRU under test
```


## First real-English language-organ result

Workflow `36436244279` completed.

Seed 101, random initialization, ~3.4 MB bounded TinyStories training slice, 800 updates:

```text
GRU          800,640 params   1.659 bits/byte   133 s
Transformer  927,872 params   2.610 bits/byte    83 s
```

The GRU already generated recognizable but repetitive English:

```text
"Once upon a time there was a little girl named Lily..."
```

The Transformer remained largely malformed at the same update budget.

This is the first real-language evidence supporting the recurrent production path, but it is one seed only.

The exact experiment is now replicating over seeds 101, 202, and 303 before any scale increase.


## Perception refinement rejected; closed-loop gate started

The semantic-slot-query BiGRU refinement failed replication:

```text
plain BiGRU       72.0% exact
attentive BiGRU   64.6% exact
```

Plain BiGRU remains the first perception baseline.

The next integration experiment now couples:

```text
English
→ BiGRU perception
→ bounded semantic state
→ GRU production
→ English
```

with three bridge controls:

- oracle semantic state;
- hard one-hot predicted state;
- soft probability state.

This is designed to localize whether closed-loop failure comes from perception, state discretization, or production rather than judging only final text.
