# V0 Causal Alignment Correction

Date: 2026-10-02

## Status

**Promoted correctness fix.** The original Phase-1 checkpoint remains immutable
historical evidence, but it must not be resumed or used as a parent checkpoint.

The corrected lineage starts from fresh initialization.

## Failure discovered

BytePatchHybridV0 trained with next-byte targets, but _local_inputs shifted
each 4-byte patch from actual bytes to [BOS, x0, x1, x2], while targets
were [x1, x2, x3, x4].

Therefore every training prediction was missing the immediately preceding byte.
At a patch boundary, the final prediction never consumed x3.

Streaming generation used a different causal contract: accepted bytes were fed
before the next prediction, and completed patches updated global state.
Batch training and streaming inference were therefore misaligned.
## Diagnostic evidence

Frozen Phase-1 checkpoint:
- 16,777,216 sampled bytes
- final phase-valid: 4.8939156542 BPB
- unigram baseline: ~4.6384 BPB
- behavioral audit: 0/6
- greedy decoding: spaces

Context probes on the frozen formulation:
- shuffled full context penalty: +0.01446 BPB
- randomized full context penalty: +0.56642 BPB
- shuffled earlier history, last byte preserved: +0.03400 BPB
- randomized earlier history, last byte preserved: +0.48667 BPB
- randomized immediately previous byte only: **+0.00000 BPB**

The zero last-byte effect matches the code-level alignment error.

## Correction

The batch local GRU now consumes the actual patch bytes directly.
Streaming now consumes every byte before producing its next-byte logits.
At patch boundaries it preserves the prediction from the completed local
sequence while resetting local hidden state from the updated global context.

A regression test now requires batch forward and streaming inference to
produce matching next-byte logits after every consumed byte.
## Verification

Full test suite after the correction: **100/100 passed**.

Fresh 32-step real-data smoke:
- phase-valid at step 1: 7.7147 BPB
- step 8: 5.9677 BPB
- step 16: 5.0822 BPB
- step 24: 4.8346 BPB
- step 32: **4.7666 BPB**
- sampled training bytes: 16,384

The smoke is not directly comparable to the frozen run because its evaluation
budget and sequence/batch settings differ. It is a sanity result, not a claim
of final superiority.

## Controlled alignment ablation

Protocol: same initialization, same batches, same optimizer, same data,
same validation batches. The only difference was corrected vs legacy local
input alignment.

| Step | Corrected BPB | Legacy BPB | Corrected advantage |
|---:|---:|---:|---:|
| 0 | 7.9534 | 7.9572 | 0.0039 |
| 1 | 7.7081 | 7.7050 | -0.0031 |
| 8 | 5.9803 | 6.0357 | 0.0553 |
| 16 | 5.0857 | 5.1126 | 0.0269 |
| 32 | 4.7844 | 4.8521 | 0.0677 |
| 64 | **4.7050** | **4.8164** | **0.1114** |
## Decision

1. Preserve v0-phase1-2048 unchanged as a failed-formulation artifact.
2. Do not resume or fork from that checkpoint for future language work.
3. Treat causal batch/stream equivalence as a permanent invariant.
4. Restart language-foundation training from fresh initialization.
5. Re-run accelerator benchmarks on corrected code/checkpoints before heavy training.
6. Keep Phase 2 blocked until a corrected Phase-1 run clears language and behavioral gates.
7. Use the two T4s as independent experiment lanes by default; promote only
   configurations that beat controlled alternatives.

This correction changes the interpretation of the old Phase-1 failure:
insufficient exposure is no longer the leading explanation. The run was
trained under a defective autoregressive interface. Architecture quality
beyond this alignment bug remains an open empirical question.
