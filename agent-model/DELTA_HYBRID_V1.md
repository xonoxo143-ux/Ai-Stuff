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

**Stage 2 result — PASSED (Kaggle CPU, 2026-10-02).**

Pinned source commit: `639e7eb49b04f826f82484d316cbfed4c79e7e25`.

- 72/72 forward equivalence cases passed;
- 8/8 reset cases passed;
- 8/8 gradient cases passed;
- max output error: 8.88e-16;
- max final-state error: 5.55e-16;
- max reset error: 4.44e-16;
- max gradient error: 1.67e-16;
- tolerances: 1e-10 forward/state/reset, 1e-9 gradients;
- no CUDA device was allocated.

The accepted path uses WY/UT triangular solves plus batched matmuls within each
chunk and carries recurrent state only between chunks. Chunks containing resets
fall back to the serial oracle to preserve explicit reset semantics.

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

### Model-construction result — PASSED (Kaggle CPU, 2026-10-02)

Pinned source commit: `96e2fc90eb64f79ea282229f413e367ef25fff83`.

- DeltaHybrid V1 parameters: 1,064,962;
- Transformer control parameters: 1,051,232;
- parameter difference: +1.306% (inside the precommitted ±2% band);
- architecture: width 156, FFN 468, 3 Gated-Delta blocks, 1 exact-attention block;
- chunk size: 64;
- model-level causal error: 0.0 at tolerance 1e-6;
- checkpoint round-trip error: 0.0;
- implicit-zero vs explicit-zero conditioning error: 0.0;
- finite forward and finite gradients: passed;
- recurrent Delta state at batch 1 in FP32: 292,032 bytes;
- CUDA devices allocated: 0.

Decision: promote to trainer integration smoke. This does not yet establish
language-learning quality or GPU efficiency.

### Trainer-integration result — PASSED (Kaggle CPU, 2026-10-02)

Pinned source commit: `0c5f37e6e919568e644ce0399d714dc8338a3cdd`.

The real training harness completed a two-step CPU smoke using the frozen corpus
build and evaluation path:

- model: DeltaHybrid V1;
- parameters: 1,064,962;
- execution: chunked;
- precision: FP32;
- training bytes: 128;
- training seconds: 0.412;
- CPU throughput: ~311 bytes/s;
- valid BPB after the tiny smoke: 7.2162;
- checkpoint present;
- telemetry present;
- metrics present;
- CUDA devices: 0.

This gate only establishes end-to-end trainer compatibility. It is not a
meaningful language-learning or performance result.

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

Construct the raw-byte DeltaHybrid V1 around the validated reference and
chunk-parallel state block at roughly the ~1.05M Transformer-control parameter
scale. Freeze the exact parameter count, corpus/data hashes, optimizer, seed
schedule, validation, and generation probes, then run CPU construction/smoke
preflight. Do not allocate T4 training until that preflight is green.

## 2026-10-02 first T4 equal-step result

Fresh 256-step 2×T4 gate, same frozen data/config/seed/optimizer:
- step 128: Delta 3.3330 held-out BPB vs Transformer 3.8949;
- step 256: Delta became NaN; Transformer finished at 3.6260 BPB;
- cumulative Delta throughput ~122k train bytes/s;
- cumulative Transformer throughput ~184k train bytes/s.

Interpretation: the gate is falsified by Delta numerical instability. The
step-128 advantage is evidence worth diagnosing, not promotion evidence.
Equal-compute comparison is blocked until stability is explained.

Preregistered discriminator: run the same Delta model/data/seed for 256 steps
with chunked execution on one T4 and the trusted serial-reference execution on
the other. Manipulated variable: execution path only. If chunked alone becomes
non-finite, the optimized WY/UT path is implicated. If both become non-finite,
the recurrence/gating/training formulation is implicated. Do not tune learning
rate, gates, data, or evaluation before this discriminator is reconciled.

## 2026-10-02 masked-ratio numerical repair

The first T4 gate's NaN was traced to the chunk-parallel decay-ratio
implementation rather than treated as generic optimizer instability.

Old implementation:

    gamma_ratio = exp(log_gamma_i - log_gamma_j) * causal_mask

Future/noncausal entries are mathematically unused, but some have large positive
log ratios. In FP32 they can overflow to inf before masking, after which
inf * 0 produces NaN.

Repair:

    safe_log_ratio = log_ratio.masked_fill(~causal_mask, -inf)
    gamma_ratio = exp(safe_log_ratio)

This preserves the causal lower-triangular values exactly while preventing the
unused upper triangle from being exponentiated.

Preregistered Kaggle CPU stress gate at repaired branch state:
- deliberately tiny decay reproduced a non-finite old-formula ratio matrix;
- patched chunk output finite;
- patched recurrent state finite;
- chunk/reference output max error: 8.94e-8;
- chunk/reference state max error: 5.96e-8;
- model chunk/reference max-logit error: 7.15e-7;
- loss finite;
- gradients finite.

Decision: authorize an identical fresh 256-step dual-T4 rerun. Do not change
learning rate, gate initialization, data, or architecture before reconciling that
rerun.

## 2026-10-02 repaired 256-step T4 rerun

The identical fresh 256-step 2×T4 equal-step/data gate was rerun after only the
masked-before-exp numerical repair.

Result:

    metric                         Delta        Transformer
    final held-out BPB             2.9625       3.6260
    step-256 valid BPB             2.9889       3.6530
    phase-valid BPB                2.8579       3.5205
    train bytes/s                136,315      204,280
    train seconds                 15.385       10.266

Delta remained finite through step 256 and reproduced its step-128 trajectory
exactly. The final held-out advantage is 0.6636 BPB at the same examples/steps.

Interpretation: the first run's collapse was caused by the optimized-path
numerical bug, not by an immediate failure of the recurrent architecture.
However, Delta is about 1.50× slower per training step on T4, so this gate is
not sufficient for promotion.

Compute-normalized calibration from this fresh run:
- Delta: 15.3846 s / 256 steps;
- Transformer: 10.2661 s / 256 steps;
- fixed ~30 s budgets: 499 Delta steps, 748 Transformer steps.

The next gate must use fresh initialization with those fixed step budgets.

## 2026-10-02 tight equal-GPU-time confirmation

Fresh models were trained with fixed budgets calibrated from the preceding
compute gate: 457 Delta steps versus 748 Transformer steps.

Observed result:

    metric                         Delta        Transformer
    train seconds                  29.536       30.638
    final held-out BPB              2.7204       2.8315
    phase-valid BPB                 2.6028       2.7109
    train bytes/s                 126,753      200,000
    train bytes                  3,743,744    6,127,616

Delta used about 3.6% less actual GPU training time and still finished
0.1111 BPB better on held-out validation and 0.1081 BPB better on phase-valid
data.

Decision: promote DeltaHybrid V1 to the current language-substrate candidate.
The Transformer remains the control/performance baseline. This promotion is
provisional with respect to seed robustness and long-context/state behavior;
it is not a claim that DeltaHybrid V1 is the final worker architecture.

The next gate is fresh-seed replication under the same tight compute-normalized
contract. Architecture/data/hyperparameter tuning remains frozen until that
replication is reconciled.

## 2026-10-02 persistent segmented-state gate

DeltaHybrid V1 now has an explicit segmented-execution wrapper that leaves the
existing training forward path and model parameters unchanged.

Persistent state contains:
- one recurrent Delta matrix per Gated-Delta block (three total);
- exact-attention hidden history;
- an exact-attention validity mask for independent per-row resets.

Preregistered Kaggle CPU gate at
`264c9df457663eb4693b59231cad30874c9426da` passed:
- 9 segmented forward cases;
- 3 save/restore resume cases;
- 3 independent reset cases;
- 2 gradient-parity cases;
- one-shot error: 0.0;
- max segmented error: 2.44e-15;
- max tokenwise error: 2.89e-15;
- max recurrent-state error: 6.66e-16;
- max attention-history error: 2.66e-15;
- max resume error: 1.78e-15;
- max reset error: 1.55e-15;
- max gradient error: 4.34e-18.

Decision: promote the state-carrying execution contract and proceed to
long-context/state evaluation.

Memory caveat: the three Delta matrices are fixed-size, but exact-attention
history remains O(context). Long-context claims must report this explicitly and
distinguish compressed recurrent-state tasks from exact-retrieval tasks.
