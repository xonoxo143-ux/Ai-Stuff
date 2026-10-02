[Reading 94 lines from start (total: 94 lines, 0 remaining)]

# Deployment Gate — Agent Models

Date: 2026-10-02

## Governing rule

Train on Kaggle. Deploy on hardware we control.

Kaggle is a research/training dependency, not a required runtime dependency.
The eventual worker should remain exportable and runnable without requiring a
live Kaggle session, hidden cloud model, or proprietary inference service.

This document no longer assumes the phone is the primary deployment target.

## Separation of roles

### Training
May use:
- Kaggle CPU;
- Kaggle 2×T4;
- mixed precision;
- fused optimizers;
- training-only vectorization/chunking;
- large temporary batches;
- parallel architecture sweeps.

### Persistent control/storage
The Optiplex provides:
- canonical repos/state;
- credentials;
- scheduling;
- result retrieval;
- logs/artifact retention;
- future worker-hosting experiments if appropriate.

### Runtime target
The mature worker may eventually run on the Optiplex/Toshiba environment,
another owned machine, or a portable target. The exact target is still open.
## Candidate graduation gate

Every serious architecture candidate is evaluated on two independent axes:

1. Learning/work quality
   - held-out loss;
   - state/retrieval probes;
   - worker task success;
   - recovery;
   - transfer;
   - calibration.

2. Deployment economics
   - checkpoint size;
   - persistent-state size;
   - RAM;
   - forward/inference latency;
   - prompt/context ingestion;
   - sustained generation/action rate;
   - storage requirements;
   - whether inference needs special kernels or cloud services.

Do not reject a candidate merely because its training implementation is
GPU-specific. Reject it if the resulting runtime cannot be made practical on
owned hardware or if its capability does not justify the runtime cost.

## Long-context consequence

Delta/state-heavy architectures are specifically expected to improve scaling of
persistent context/state.

Therefore measure runtime state and memory growth as context grows. A candidate
that matches short-context quality but keeps bounded recurrent state may still
be valuable if exact-access mechanisms remain efficient.
## Historical phone baseline

Older Fold 4 measurements remain valid historical deployment evidence for the
models that produced them. They are not the current compute plan and should not
drive architecture selection by themselves.

Phone benchmarking is now optional and should be used only when mobile
deployment becomes a real target again.

## Promotion principle

Choose from the Pareto frontier:

    useful capability
    / training compute
    / inference compute
    / persistent memory
    / operational complexity

The goal is not to maximize GPU utilization or minimize model size in
isolation. The goal is the strongest worker architecture that remains practical
to own and operate.
