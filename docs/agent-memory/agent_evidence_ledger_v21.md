# Agent Evidence Ledger

Version: 2.4
Date: 2026-10-02
Role: durable high-value evidence summary.
Current-state authority: ../AGENT_CURRENT.md

Historical result files remain the detailed source for older experiments.

## Status vocabulary

- SUPPORTED — strong enough to guide design.
- PROMISING — useful signal that needs broader replication.
- WEAK / MIXED — insufficient to guide architecture.
- REJECTED FORMULATION — this implementation failed; the broader idea may remain open.
- OPEN — not established.

## Current language / architecture evidence

### E-LANG-007 — V0 batch/stream causal misalignment
Status: SUPPORTED ROOT CAUSE

The frozen V0 hybrid trained and generated under different causal interfaces.
The targeted probe found zero sensitivity to the immediately previous byte,
matching the code-level one-byte alignment error.

Design consequence:
- preserve the old checkpoint as failed-formulation evidence;
- never resume/fork from it;
- require batch-to-stream equivalence tests permanently.
### E-LANG-008 — Correcting alignment materially improves matched learning
Status: SUPPORTED

Controlled same-init/same-batch/same-optimizer step-64 ablation:

    corrected hybrid   4.7050 BPB
    legacy hybrid      4.8164 BPB
    delta              0.1114 BPB

The correctness fix is promoted.

### E-LANG-009 — Equal-step gate favors hybrid quality but Transformer throughput
Status: SUPPORTED / INSUFFICIENT FOR PROMOTION

Fresh 256-step dual-T4 comparison:

    hybrid        3.5306 BPB    ~89k bytes/s
    Transformer   3.6260 BPB   ~202k bytes/s

Equal-step/data comparison alone was misleading because training throughput
differed by more than 2×.

### E-LANG-010 — Compute-normalized gate favors Transformer decisively
Status: SUPPORTED

After a fresh 128-step calibration, the main run targeted roughly 30 training
seconds per architecture.
Observed result:

                         Hybrid         Transformer
    steps                  324              674
    train bytes          2.65M            5.52M
    train seconds        31.92            26.18
    held-out BPB          3.4148           2.8815
    phase-valid BPB       3.2666           2.7629

The Transformer used less actual training time and still finished about
0.533 BPB better.

Design consequence:
- causal byte Transformer becomes the current performance baseline;
- corrected GRU/patch hybrid is demoted for heavy language training;
- equal-compute gates are mandatory for future architecture races.

### E-LANG-011 — Gated-Delta reference correctness gate passes
Status: SUPPORTED REFERENCE INVARIANT

Kaggle CPU version 2, pinned to clean source commit
`ba7999a0c57b4dcc4d166fa374e63e170fc18fef`, passed the Delta V1 reference
correctness gate:

    reference cases            128
    expanded-equation cases      8
    gradient cases                8
    causal error                0.0
    stream/chunk output error   0.0
    state/reset/resume error    0.0
    equation max error          4.44e-16

The first kernel version failed because a connector wrapper line contaminated
the published Python source. That failure is preserved as infrastructure
provenance, not architecture evidence.

Design consequence:
- the readable Gated-Delta recurrence is promoted as the correctness oracle;
- Stage 2 may build an efficient batched/chunked path;
- this prerequisite was subsequently satisfied by E-LANG-012.

### E-LANG-012 — Chunk-parallel Gated-Delta matches the reference oracle
Status: SUPPORTED EXECUTION EQUIVALENCE

Kaggle CPU at source commit
`639e7eb49b04f826f82484d316cbfed4c79e7e25` passed the preregistered
WY/UT chunk-equivalence gate:

    forward cases                 72
    reset cases                    8
    gradient cases                 8
    max forward output error    8.88e-16
    max forward state error     5.55e-16
    max reset error             4.44e-16
    max gradient error          1.67e-16
    forward tolerance            1.0e-10
    gradient tolerance           1.0e-09
    CUDA devices                       0

Design consequence:
- the hardware-friendly chunk-parallel formulation is accepted as numerically
  equivalent to the reference at this gate;
- model construction may proceed around this execution path;
- serious T4 training remains blocked until the parameter-matched model and its
  CPU preflight are clean.

### E-LANG-013 — Parameter-matched DeltaHybrid V1 passes model construction gate
Status: SUPPORTED MODEL PREFLIGHT

Kaggle CPU at source commit
`96e2fc90eb64f79ea282229f413e367ef25fff83` passed the preregistered
model-construction gate:

    Delta parameters              1,064,962
    Transformer control           1,051,232
    parameter difference             +1.306%
    causal error                       0.0
    checkpoint error                   0.0
    finite forward                      yes
    finite gradients                    yes
    FP32 recurrent state / sample   292,032 bytes

Design consequence:
- the first raw-byte 3:1 Delta/attention model is accepted for trainer integration;
- parameter matching is close enough for the planned architecture race;
- this is not evidence of superior language quality or GPU efficiency;
- T4 training remains blocked until the end-to-end trainer smoke passes.

### E-INFRA-001 — Direct Optiplex control removes phone dependency
Status: SUPPORTED OPERATIONALLY

The Optiplex is registered as a first-class Remote Desktop Commander device
with persistent restart configuration. Kaggle authentication is stored on the
Optiplex and has successfully submitted/retrieved private 2×T4 kernels.

Design consequence:
- phone is no longer required as a bridge;
- Optiplex becomes persistent control/storage;
- Kaggle becomes the default compute fabric.
## Earlier durable evidence retained

The following earlier conclusions remain useful unless superseded by a new
controlled result:

- sparse top-k execution can produce real wall-clock savings;
- useful cell-specific and pairwise causal specialization exists;
- simple usage/gradient/importance heuristics are weak predictors of destructive
  updates;
- factor-graph organization produced a large OOD gain over a flat baseline in
  the controlled cognitive benchmark;
- repeated thought can unlock specific capabilities but extra depth saturates;
- bounded structured state can drive compositional language in synthetic tasks;
- different architectures can dominate different metrics, so same-step quality
  must not be confused with compute efficiency.

## Next evidence target

DeltaHybrid V1 has established reference-recurrence correctness and
hardware-friendly chunk-parallel equivalence, including gradients and reset
semantics. The next evidence target is a parameter-matched ~1.05M raw-byte
DeltaHybrid model that passes CPU construction/smoke preflight against a frozen
Transformer-Control-V1 contract.

After that: competitive equal-step and equal-compute language learning plus a
measurable long-context/state advantage. Until those architecture-level gates
pass, Gated-Delta/state-heavy architecture remains a challenger rather than a
promoted substrate.
