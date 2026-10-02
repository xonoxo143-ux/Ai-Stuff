# DeltaHybrid V1 — Build and Falsification Plan

Date: 2026-10-02
Status: next mainline architecture challenger

## Question

Can a modern state-heavy sequence model with occasional exact attention beat or
meaningfully complement the parameter-matched causal byte Transformer under the
worker project's actual constraints?

The V0 GRU/patch hybrid does not answer this question. It used a much cruder
recurrent mechanism and lost decisively per T4-second after its causal bug was
fixed.

## Frozen control

Transformer-Control-V1:
- causal byte Transformer;
- approximately 1.05M parameters;
- same corpus and held-out evaluation used by corrected V0 gates;
- same optimizer/config unless an experiment explicitly changes it.

Observed compute-normalized reference:
- 674 steps;
- 5.52M train bytes;
- 26.18 train seconds;
- 2.8815 held-out BPB;
- 2.7629 phase-valid BPB.

This is the bar, not the desired final architecture.

## V1 architectural prior

Start with raw bytes and approximately matched parameter count.
Provisional block pattern:

    embedding
      ↓
    Gated Delta
      ↓
    Gated Delta
      ↓
    Gated Delta
      ↓
    exact attention
      ↓
    repeat as budget allows
      ↓
    norm
      ↓
    byte prediction head

Initial ratio: about 3 state/recurrent blocks : 1 exact-attention block.

Why:
- recurrent/state blocks should maintain ordinary ongoing context with bounded
  state;
- exact attention should rescue precise retrieval/copy cases that fixed-size
  state alone handles poorly;
- the comparison should test sequence machinery, not tokenizer or curriculum
  changes.

Do not add learned patching yet.

## Stage 1 — Gated-Delta reference

Run on Kaggle CPU.

Implement the simplest readable mathematical recurrence first.
No custom CUDA kernels and no performance claims.

Required unit/invariant tests:
- hand-computed tiny recurrence;
- causal leakage = zero;
- finite forward values;
- finite gradients;
- deterministic seeded execution;
- reset behavior;
- state serialization/deserialization;
- checkpoint/resume determinism.

**Gate A result — PASSED (Kaggle CPU, 2026-10-02).**

- 128 reference shape/seed cases passed;
- 8 expanded-equation identity cases passed;
- 8 gradient cases passed;
- causal/stream/chunk/reset/resume/state max errors were exactly 0.0;
- expanded-equation max error was 4.44e-16;
- no CUDA device was allocated.

The failed first kernel attempt is preserved as an infrastructure/provenance
failure: a connector wrapper line had contaminated the published Python source.
It is not evidence against the Delta recurrence. Version 2 used clean source and
passed.

## Stage 2 — execution equivalence

Implement:
1. slow reference recurrence;
2. batched training formulation;
3. streaming byte-at-a-time formulation;
4. chunked/parallel formulation.

Precommitted gate:

    reference ≈ batch ≈ streaming ≈ chunked

within explicit numerical tolerance on logits/state.

Test:
- different sequence lengths;
- chunk boundaries;
- multiple batch sizes;
- reset in the middle of streams;
- gradient agreement where practical.

Failure here blocks all T4 training.

## Stage 3 — hardware-efficient implementation

Only after the reference is trusted:

- remove Python loops from the hot training path where possible;
- batch/chunk state updates;
- profile operation count and memory movement;
- avoid architecture changes made only for speed unless separately tested.

The optimized path must continue to match the reference implementation.

Kaggle CPU is used for correctness; T4 microbenchmarks may be used only after
equivalence is established.
## Stage 4 — parameter matching

Construct DeltaHybridV1 at roughly 1.05M parameters.

Freeze:
- raw-byte interface;
- sequence length for the short-context gate;
- source streams;
- data hashes;
- optimizer;
- seed schedule;
- validation;
- generation probes.

Record exact parameter delta from the Transformer.

Keep architecture-specific execution optimizations, but do not give either arm
different data or evaluation.

## Stage 5 — short-context T4 gates

### A. Equal-step/data
Fresh models on separate T4s.
Use a short budget such as 256 steps.

Purpose:
measure learning per example and catch gross training failure.

Do not promote on this result alone.

### B. Compute-normalized
Calibrate each architecture's training seconds/step, then train fresh models to
a matched GPU-training-time budget.

Primary metrics:
- held-out BPB;
- phase-valid BPB;
- bytes processed;
- train bytes/s;
- actual training seconds;
- generation quality/probes.

Repeat seeds if the margin is not decisive.
## Stage 6 — state and long-context gates

The architecture must be tested where state-heavy designs should earn their
complexity.

Context ladder:
- 128 bytes;
- 512 bytes;
- 2K bytes;
- 8K bytes;
- larger only after useful signal.

Probe families:
- delayed dependency;
- current-state tracking;
- overwrite/update state;
- distractor resistance;
- ordered events;
- exact copy/retrieval;
- needle-style retrieval;
- resume after chunk interruption.

Measure:
- quality;
- compute;
- persistent state memory;
- attention/KV memory;
- latency as context grows.

## Stage 7 — promotion rule

Promote DeltaHybridV1 if the combined evidence shows a meaningful advantage,
for example:
- competitive short-context learning;
- better long-context learning per GPU-second;
- bounded or materially smaller persistent inference state;
- stronger state-tracking behavior;
- exact-attention layers prevent unacceptable retrieval collapse.

Kill this implementation if it repeatedly loses equal-compute gates and shows
no compensating state/long-context advantage.
## Stage 8 — only after substrate promotion

Then test one variable at a time:
- finer-grained Delta/KDA-like gates;
- RWKV-style state update variants;
- xLSTM-style challenger;
- learned byte patching;
- external exact memory;
- worker-oriented curriculum.

Do not open all of these simultaneously.

## Compute routing

Optiplex:
- edit/store source;
- hold credentials;
- submit kernels;
- retrieve results;
- maintain ledgers;
- run lightweight server/dev checks where performance is irrelevant;
- keep basic Python/pip/venv infrastructure available.

Do not use the Optiplex for substantive PyTorch/model evaluation or training in
this architecture gate. A future promoted model may be run there only as an
explicit weak-hardware deployment/efficiency canary.

Kaggle CPU:
- Stages 1–3 correctness and substantial CPU tests.

Kaggle 2×T4:
- Stages 4–7 training and architecture races.

Phone:
- no required role.

## Immediate implementation task

Create Delta reference module + invariant test suite.
Package it as a Kaggle CPU kernel.
Do not allocate T4 time until the CPU correctness report is green.
