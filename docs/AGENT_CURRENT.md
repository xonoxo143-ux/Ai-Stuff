# Agent — Current Architecture and Frontier

Date: 2026-10-03
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

Terminology: `Worker` (capital W) refers only to the separate persistent AgentMail/SELF-ROOT operational project. This project develops a homegrown task-performing agent and its general work-performing capability; references below to economic competence or task performance do not mean the Worker project.

Build a generally capable task-performing agent that can:

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
- Toshiba 500 GB USB: currently dedicated as the agent Linux disk (`agent-root`,
  `agent-swap`, and `agent-home`); do not use it as bulk/backup storage without
  an explicit migration decision.
- VendorCo ~32 GB USB: currently Debian 13.7 installer media; do not use it as
  a project-backup target while it serves that role.

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
evaluation, and parameter scale fixed. Learned patching, task-performance curriculum,
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

## 6. Work-capability curriculum sequence

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

DeltaHybrid V1 now has a verified explicit persistent-state execution contract.

Kaggle CPU proved that the same model weights produce equivalent outputs and
gradients under:
- one-shot execution;
- irregular segmented execution;
- token-by-token execution;
- serialize → restore → continue;
- independent per-batch-row boundary resets.

Across 9 forward cases, 3 resume cases, 3 reset cases, and 2 gradient cases,
all errors were at floating-point-noise scale (~1e-15 or smaller), far inside
the preregistered tolerances. No GPU was allocated.

The carried state is:
- three bounded Delta recurrent matrices; plus
- a configurable bounded exact-attention hidden-history cache and validity mask.

The follow-up Kaggle CPU bounded-history gate passed when run from commit
`ba472116824a9b76e6af5d08525a88b6184e6804`. With batch 2, 128-token
segments, and a 128-token exact-attention continuation cap:
- history length was 128 at both 512 and 2,048 streamed tokens;
- total carried state was 744,064 bytes at both lengths;
- recurrent-only continuation was 584,064 bytes/sample-pair at 2,048 tokens;
- unlimited history reached 512 tokens / 1,224,064 bytes at only 512 tokens;
- all outputs remained finite; Kaggle reported zero CUDA devices.

This removes the earlier O(context) continuation-memory requirement when a
bounded exact cache is selected. It does not prove useful long-range memory.

Next action is the preregistered first discriminating T4 state-memory gate:
train fresh Delta and parameter-matched Transformer lanes for 400 steps on the
same synthetic current-state task (512-token training sequences, batch 8), with
both restricted to the same 256-token maximum exact local span. Evaluate frozen
held-out streams at 128/512/2K. Primary evidence is retrieval when the relevant
update is >256 tokens old. Promotion requires full Delta to beat the windowed
Transformer there and a no-recurrent Delta ablation to materially degrade that
metric. Otherwise do not extend to 8K or tune the benchmark; diagnose/falsify
the claimed recurrent-state advantage first.
