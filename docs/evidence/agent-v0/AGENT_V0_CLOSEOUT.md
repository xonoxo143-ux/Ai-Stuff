# Agent v0 — architecture closeout

**Date:** 2026-09-26  
**Status:** controlled architecture phase complete enough to advance to Agent v1.

Agent v0 was deliberately a controlled learned substrate, not a conversational
model. Its purpose was to falsify or retain the highest-risk architectural
assumptions before scaling.

## What survived

### Sparse activation pays on the real target

Matched sparse top-4 vs dense all-16 execution, with exact behavioral parity:

- sparse median thought: **0.732 ms**
- dense median thought: **1.304 ms**
- dense/sparse median: **1.783×**
- sparse saved about **43.9%** wall-clock latency

All 12 paired trials favored sparse execution.

### Recurrent thought performs real work

Same trained model, same tasks:

| internal thoughts | MAE |
|---:|---:|
| 1 | 0.8262 |
| 2 | 0.3100 |
| **3** | **0.1852** |
| 4 | 0.5937 |
| 6 | 1.0302 |

Three recurrent steps were useful; untrained extra depth caused drift.

### Learned cells have causal specialization

Execution lesions replicated stable causal roles on six fresh datasets.

Largest mean single-cell damage:

- cell 7: **+0.731 MAE**
- cell 3: **+0.411**
- cell 10: **+0.222**
- cell 12: **+0.174**
- cell 9: **+0.174**

### Useful computation can belong to an interaction

Cells **(1,10)** showed stable super-additive lesion damage:

- mean interaction synergy: **+0.1736 MAE**
- positive on **6/6** fresh replications

This supports retaining interaction motifs as first-class candidates rather than
forcing all credit onto individual capabilities.

### A discovered motif can be compiled

The (1,10) interaction was distilled into a 47,552-parameter composite.

Fresh-data probation:

- task degradation: **none on 6/6**
- mean task MAE delta: **−0.00202**
- use rate: **21.6%** of thought rows

Real phone boundary execution:

- original pair median: **0.1142 ms**
- compiled motif median: **0.0505 ms**
- local speedup: **2.263×**

So a recurring learned interaction can be discovered, causally validated,
compressed, and made materially cheaper on the target hardware.

## What did not survive as a naive rule

- more recurrent thought is not automatically better;
- theoretical FLOP savings do not equal device savings;
- coactivation alone is not a promotion criterion;
- local motif speedup is not equivalent to whole-Agent speedup;
- a compiled candidate should not automatically replace its sources.

## Motif (1,10) status

`validated_compiled_candidate / whole-system probation`

It passes local causal, quality, and hardware tests.

It is **not** yet the default runtime implementation because its observed 21.6%
use rate and ~0.066 ms local mean saving imply only about 0.014 ms expected
saving per thought before dispatch/boundary overhead. Current evidence therefore
does not yet establish positive total-system marginal utility.

Preserve the compiled candidate and its provenance. Do not retire cells 1 or 10.

## Agent v1 requirements derived from evidence

Agent v1 should not simply scale Agent v0.

It must specifically address the failure and uncertainty exposed by v0:

1. **Keep sparse top-k activation.**
2. **Keep private recurrent capability state and bounded workspace.**
3. **Train recurrent trajectories beyond one fixed depth.**
4. **Separate trajectory learning from stopping policy.**
   The v0 depth sweep shows why an untrained halt head is not acceptable.
5. **Fit stopping on frozen or stabilized trajectories**, so the halt objective
   cannot silently distort the computation it is trying to measure.
6. **Increase stored capability while holding active capability narrow**, to test
   whether runtime grows slower than stored capacity.
7. **Use a richer multi-family controlled curriculum**, so specialization is not
   an artifact of one scalar register task.
8. **Preserve causal tracing and slow structural analysis.**
9. **Carry validated motifs as versioned library candidates**, with reversible
   activation and source fallback.
10. **Do not attach language until the v1 core can demonstrate variable-depth,
    multi-family reuse and persistent state without relying on language as the
    computational substrate.**

## Research alignment checked before v1

Existing work supports several individual pieces without settling this project's
integration:

- Adaptive Computation Time and PonderNet establish learnable variable recurrent
  computation.
- Recurrent Independent Mechanisms support sparse recurrent modules with private
  dynamics and limited communication.
- Sparse routing work in continual learning supports reduced interference through
  selective paths.

Agent v1 should use those results as constraints, not copy their architectures.
The project-specific question remains whether the complete ecology can combine
sparse hardware economics, recurrent state, causal specialization, developmental
promotion, and later language interaction under one persistent runtime.
