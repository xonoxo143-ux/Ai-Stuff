[Reading 90 lines from start (total: 90 lines, 0 remaining)]

# Agent Language V0 Training — Historical / Closed Lineage

Date: 2026-10-02

This document records the V0 language-training lineage. It is no longer the
mainline training plan.

## Original comparison

Candidate:
BytePatchHybridV0 — local 4-byte patches, local GRU, recurrent global state,
bounded patch-memory access.

Control:
parameter-matched causal byte Transformer.

Both used the same corpus streams, curriculum, batch size, sequence length,
optimizer, and held-out evaluation suite.

## Original Phase-1 artifact

The frozen V0 Phase-1 run reached step 2048 / 16,777,216 sampled bytes, but it
is not a valid parent checkpoint.

Postmortem discovered a causal-alignment error:
batch training and streaming inference consumed different effective histories.
The immediately previous byte had zero effect on the frozen model's final
next-byte prediction.

Preserve the artifact for provenance only.
Do not resume it.
Do not fork from it.
## Corrected formulation result

The causal interface was corrected and protected with batch↔stream equivalence
tests.

Same-init/same-batch/same-optimizer 64-step ablation:

    corrected hybrid   4.7050 BPB
    legacy hybrid      4.8164 BPB

So the bug fix paid rent.

However, architecture-level testing then showed:

### Equal-step 256
    hybrid        3.5306 BPB
    Transformer   3.6260 BPB

### Compute-normalized
    hybrid        3.4148 BPB in 31.92 train s
    Transformer   2.8815 BPB in 26.18 train s

The corrected hybrid therefore lost decisively per GPU compute.

## Decision

V0 Phase 2 and Phase 3 are not continued on the GRU/patch hybrid.

The byte Transformer is retained as the current performance control.
The next mainline training architecture is DeltaHybrid V1.

Historical V0 curriculum files remain useful as controlled datasets/evals, but
their phase numbering no longer defines the project roadmap.
## Reusable training invariants

The following survive V0 and apply to all future language spines:

- deterministic seeds and corpus hashes;
- strict provenance;
- fixed held-out evaluation;
- exact training-byte accounting;
- train throughput and GPU-time accounting;
- batch/stream/chunk equivalence where multiple execution modes exist;
- checkpoint/resume determinism;
- no silent change of corpus or evaluation after looking at results;
- same-step and compute-normalized architecture comparisons;
- behavioral probes in addition to likelihood metrics.

## Compute routing

All substantive experiments run on Kaggle.

- CPU correctness/reference work → Kaggle CPU.
- GPU architecture/training work → Kaggle 2×T4.
- Optiplex → control/storage/scheduling/result collection.
- Phone → optional interface/target, not project infrastructure.

See KAGGLE_V0.md and DELTA_HYBRID_V1.md.

[executed on device: optiplex-ai (fbcbb933-7ca0-4279-8624-6a1cd3f388d1)]