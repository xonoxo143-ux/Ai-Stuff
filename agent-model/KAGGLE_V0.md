[Reading 129 lines from start (total: 129 lines, 0 remaining)]

# Kaggle Compute Fabric — Agent Model Research

Date: 2026-10-02

This path name is retained for compatibility, but Kaggle is no longer only a
V0 GPU continuation mechanism. It is the default compute fabric for the model
research program.

## Roles

### Kaggle CPU
Use for substantive CPU work:
- reference implementations;
- causal/equivalence tests;
- gradient and numerical-stability checks;
- multi-seed CPU probes;
- data and evaluation generation;
- long-context correctness experiments;
- jobs too slow or wasteful for the Optiplex.

### Kaggle 2×T4
Use for:
- model training;
- architecture races;
- GPU throughput benchmarks;
- equal-compute comparisons;
- promoted longer runs.

### Optiplex
Control/storage only:
- credentials;
- Git/repos;
- kernel manifests;
- submission;
- scheduling;
- result retrieval;
- selected artifacts and logs.
The phone is not a required bridge.

## Scheduling rule

The default GPU unit is one independent experiment per T4.

For small models, do not combine the two T4s into one distributed job unless a
benchmark shows that synchronization pays for itself.

Typical session:

    CPU PREP / VALIDATION
            ↓
      ┌──────────────┐
      │ Kaggle 2×T4  │
      ├──────────────┤
      │ GPU0: arm A  │
      │ GPU1: arm B  │
      └──────────────┘
            ↓
      retrieve results
            ↓
      promote / kill

## Proven operational path

The Optiplex has successfully:
- authenticated to Kaggle;
- submitted private kernels;
- requested a Tesla T4 machine shape;
- received two visible Tesla T4 devices;
- retrieved outputs and logs.

The compute fabric therefore does not depend on the phone being powered on.
## Current architecture evidence

### Corrected equal-step gate — 256 steps

    hybrid        3.5306 BPB    ~89k train bytes/s
    Transformer   3.6260 BPB   ~202k train bytes/s

The hybrid was slightly better per step but much slower.

### Compute-normalized gate

Fresh calibration selected:
- hybrid: 324 steps;
- Transformer: 674 steps;
- target: roughly 30 seconds training per model.

Observed:

                         Hybrid         Transformer
    train seconds        31.92            26.18
    held-out BPB          3.4148           2.8815
    phase-valid BPB       3.2666           2.7629
    train bytes/s          83k             211k

The Transformer was substantially better despite receiving less actual
training time.

Decision: the corrected GRU/patch hybrid is demoted; the Transformer becomes
the performance baseline.
## DeltaHybrid V1 policy

DeltaHybrid V1 does not receive T4 budget until the Kaggle CPU correctness gate
passes.

Required CPU evidence:
- reference recurrence matches hand/slow formulation;
- no future-token leakage;
- streaming == batched reference;
- chunked == reference;
- gradients finite;
- deterministic checkpoint/resume;
- explicit state reset behavior.

Then run:
1. small equal-step dual-T4 gate;
2. equal-GPU-second dual-T4 gate;
3. long-context/state gate;
4. seed replication if close;
5. heavy training only after promotion.

## Quota discipline

- Treat Kaggle quota as dynamic state; query it before large campaigns.
- Never spend GPU time discovering basic correctness bugs.
- Pre-stage code/data/evals before accelerators are active.
- Keep failed variants and failure reasons.
- Judge by useful learning/capability per compute, not raw throughput alone.
- Prefer many cheap falsifications feeding a few serious long runs.
