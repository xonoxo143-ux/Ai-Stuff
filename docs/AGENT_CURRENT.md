# Agent — Current Architecture and Frontier

Date: 2026-10-02
Status: authoritative current orientation
Current research branch: experiment/v0-causal-alignment-fix

If another Agent document disagrees with this file about the current direction,
treat that document as historical unless this file explicitly re-promotes it.

## 0. Documentation contract

This is the single living project-state/build document.

Use result files for immutable experiment detail. Use the research
findings/synthesis documents for external literature and broader hypotheses.
Do not create another competing current-state file.

## 1. Product objective

Build a generally capable worker agent that can:

- understand instructions and constraints;
- communicate clearly;
- plan and revise plans;
- use tools and files;
- preserve persistent task state;
- recover from failures;
- complete useful multi-step work;
- eventually operate inside bounded economic workflows.
Conversation is an interface, not the purpose.

The final deployed learner must remain self-contained/homegrown. Frontier or
pretrained models may assist training-time research, curriculum generation,
critique, or evaluation, but they do not count as the deployed intelligence.

Target loop:

    UNDERSTAND
    → MAINTAIN STATE
    → PLAN
    → ACT
    → OBSERVE
    → REPAIR
    → COMPLETE
    → COMMUNICATE

## 2. Compute and infrastructure policy

All substantive model computation defaults to Kaggle.

    ChatGPT / project lead
            ↓
    Optiplex control + durable storage
            ↓
    Kaggle scheduler / API
       ├── CPU kernels: correctness, references, evals, multi-seed CPU work
       └── 2×T4 kernels: training, architecture races, promoted GPU runs
The Optiplex is not an AI-compute tier. It performs control-plane work:
Git, credentials, manifests, scheduling, result retrieval, dashboards, logs,
small file transforms, lightweight development/unit checks, and persistent
project state.

Basic development infrastructure such as Python, pip, and virtual environments
belongs on the Optiplex and may be installed as needed. Do not route substantive
model training, tensor-heavy evaluation, architecture races, or repeated
benchmark workloads there merely because the machine is reachable.

Later, the Optiplex has a deliberate secondary role as a weak-hardware
deployment canary. Mature promoted models may be tested there to measure whether
they can run on old commodity hardware (RAM, cold-start latency, throughput,
CPU load, and practical usability). That is a deployment/efficiency gate, not a
training tier, and must not distort architecture work prematurely.

The phone is not required for project continuity and should not be assumed to
be powered on or available.

Storage roles:

- 2 TB main Linux drive: canonical workspace, repos, manifests, results,
  selected checkpoints, automation state, caches worth retaining.
- 500 GB Toshiba USB external: bulk/secondary storage, checkpoint archive,
  large datasets, backups, and possible future worker/runtime home.
- 32 GB USB: deliberately unassigned for now; reserve it until a clear role
  such as recovery/bootstrap, isolated key material, or portable artifact earns
  promotion.

## 3. Current language-spine evidence

### 3.1 Frozen V0 failure

The original Phase-1 BytePatchHybridV0 checkpoint is a failed-formulation
artifact. Batch training and streaming inference used different causal
alignment: the batch path omitted the immediately previous byte for each
next-byte target while streaming consumed it.

Do not resume or fork from that checkpoint.
The corrected causal contract now has a permanent regression test requiring
batch and streaming next-byte logits to agree after each consumed byte.

Controlled local alignment ablation at step 64:

    corrected hybrid   4.7050 BPB
    legacy hybrid      4.8164 BPB
    advantage          0.1114 BPB

This validated the correctness fix but did not validate the architecture.

### 3.2 Equal-step dual-T4 gate

Fresh corrected models, matched data/seed/budget, 256 steps:

    corrected hybrid      3.5306 BPB   ~89k train bytes/s
    byte Transformer      3.6260 BPB  ~202k train bytes/s

At equal steps/data, the hybrid learned slightly better but trained about
2.3× slower. This gate was therefore insufficient for architecture promotion.

### 3.3 Compute-normalized dual-T4 gate

A fresh calibration estimated training cost and targeted about 30 seconds of
optimizer/training time per model.
Observed main-run result:

                         Hybrid         Transformer
    steps                  324              674
    train bytes          2.65M            5.52M
    train seconds        31.92            26.18
    train bytes/s          83k             211k
    held-out BPB          3.4148           2.8815
    phase-valid BPB       3.2666           2.7629

The Transformer received less actual training time yet finished about
0.533 BPB better and processed roughly 2.5× more data per second.

Decision:

The existing GRU/patch hybrid does not pay rent as the main language substrate
per T4-second at this scale.

The causal byte Transformer is promoted to performance baseline/control.
It is not accepted as the final architecture.

## 4. Next architecture: DeltaHybrid V1

The mainline challenger is a modern state-heavy hybrid:

    raw bytes
      ↓
    embedding
      ↓
    Gated Delta block ×3
      ↓
    exact-attention block
      ↓
    repeat
      ↓
    norm + next-byte head
Initial target: about 3 recurrent/state blocks for every 1 exact-attention
block, approximately parameter-matched to the ~1.05M byte Transformer.

The first comparison intentionally keeps raw bytes, corpus, optimizer,
evaluation, and parameter scale fixed. Learned patching, worker curriculum,
retrieval, and external memory are later variables.

The design hypothesis is not "attention is bad." It is:

Persistent/recurrent state should carry ordinary ongoing context cheaply;
sparse exact access should handle information that must be recovered precisely.

## 5. DeltaHybrid V1 build gates

### Gate A — reference correctness on Kaggle CPU
- implement Gated-Delta reference recurrence;
- zero causal leakage;
- finite gradients;
- deterministic checkpoint/resume;
- streaming equals batched reference;
- chunked equals unchunked reference;
- state reset semantics explicit.

No T4 training before these pass.

### Gate B — hardware-efficient training path — PASSED
The WY/UT chunk-parallel Gated-Delta path matched the slow reference on Kaggle
CPU across 72 forward cases, 8 reset cases, and 8 gradient cases. Worst observed
errors were 8.88e-16 for outputs, 6.66e-16 for final state, 4.44e-16 for reset,
and 1.67e-16 for gradients, all far below the preregistered tolerances.

The implementation uses batched matmuls and triangular solves inside chunks,
with recurrent state only between chunks; reset-bearing chunks deliberately fall
back to the serial oracle.
### Gate C — small T4 architecture race
Fresh ~1.05M DeltaHybrid V1 versus frozen Transformer control:
1. equal-data/step gate;
2. equal-GPU-second gate;
3. several seeds if the effect is close.

### Gate D — long-context/state advantage
Test at increasing context lengths and on tasks that distinguish:
- compressed current-state tracking;
- delayed dependency;
- overwrite/update memory;
- distractor resistance;
- exact retrieval/copy;
- ordered-event memory.

A state-heavy architecture must show value where its inductive bias should
matter, not only at 128-byte contexts.

### Gate E — promote or kill
Promote only if the combined capability/compute/memory picture beats or
meaningfully complements the Transformer control. Otherwise kill the specific
implementation and move to the next serious recurrent/state formulation.

See agent-model/DELTA_HYBRID_V1.md.

## 6. Worker integration sequence

Do not bolt work onto a chatter model after the fact.
Once the substrate survives architecture gates, expand the curriculum toward:

1. broad causal language and semantics;
2. procedural/problem-solving text;
3. structured/code information;
4. tool/action trajectories;
5. failure → recovery trajectories;
6. grounded retrieval tasks;
7. persistent task state and resume-after-interruption;
8. bounded economic competence.

## 7. Evaluation rule

Structural changes must pay rent.

Track at least:
- held-out BPB / language quality;
- task completion;
- tool selection;
- recovery from failures;
- unnecessary actions;
- human interventions;
- long-task instruction retention;
- retrieval correctness;
- cross-domain transfer;
- compute and cost per successful task;
- resume-after-interruption;
- calibration;
- persistent-state quality.

A useful aggregate is verified useful work / compute, not raw benchmark score
alone.

## 8. Immediate next action

The first 2×T4 equal-step architecture gate completed and exposed a stability
failure in DeltaHybrid V1.

At step 128, before failure:
- DeltaHybrid V1: 3.3330 held-out BPB;
- Transformer control: 3.8949 held-out BPB.

By step 256:
- DeltaHybrid V1: NaN train/validation loss;
- Transformer control: 3.6260 held-out BPB;
- Delta throughput: ~122k train bytes/s;
- Transformer throughput: ~184k train bytes/s.

The early Delta quality signal is interesting but cannot count as a win because
the implementation became non-finite. Do not run the equal-GPU-second gate yet.

Highest-value unresolved question: is the collapse specific to the WY/UT
chunk-parallel numerical path, or intrinsic to the current Delta recurrence and
training setup? The cheapest discriminating experiment is a fresh 256-step
2×T4 A/B using identical Delta models/data/seed: chunked execution on one T4,
serial reference execution on the other. If only chunked collapses, localize and
repair the optimized path while preserving reference equivalence. If both
collapse, investigate recurrence/gating/training stability instead.

