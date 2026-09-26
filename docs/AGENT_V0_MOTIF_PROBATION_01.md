# Agent v0 — Result 06: compiled motif probation

**Date:** 2026-09-26  
**Motif:** cells **(1,10)**  
**Composite:** hidden width 64, 47,552 parameters

## Purpose

The first compilation result was promising but used a single evaluation seed.

This probation repeats the compiled-vs-teacher comparison on six fresh held-out
evaluation sets. The original two-cell route remains the teacher.

## Result

Across seeds 401, 409, 419, 421, 431, and 433:

| seed | teacher MAE | compiled MAE | Δ MAE |
|---:|---:|---:|---:|
| 401 | 0.24814 | 0.24412 | **−0.00403** |
| 409 | 0.23020 | 0.23013 | **−0.00007** |
| 419 | 0.26916 | 0.26785 | **−0.00131** |
| 421 | 0.26499 | 0.26219 | **−0.00280** |
| 431 | 0.24479 | 0.24408 | **−0.00071** |
| 433 | 0.25568 | 0.25250 | **−0.00317** |

Summary:

- mean Δ MAE: **−0.00202**
- SD: **0.00141**
- worst observed Δ MAE: **−0.00007**
- non-worse fraction: **6/6**
- within +0.005 MAE tolerance: **6/6**
- mean motif use: **21.6%** of thought rows
- mean absolute output delta vs teacher: **0.0173**

The compiled implementation therefore did not degrade task MAE on any of the six
fresh evaluation sets. It slightly improved MAE on all six.

The improvement should not be interpreted as the composite being intrinsically
"smarter." Distillation can smooth teacher noise or act as regularization. The
important engineering result is that the cheaper composite stays inside the
validated behavioral envelope on these fresh contexts.

## Current state of the promotion test

The candidate has now passed:

```text
recurring coactivation
        ✓
causal pair interaction
        ✓
fresh-data causal replication
        ✓
compilation
        ✓
fresh-data quality probation
        ✓

real hardware cost probation
        NEXT
```

The 64-hidden composite remains the candidate implementation.

Its estimated private multiply requirement is about **27.5%** of the original two
source cells, but that is not enough for promotion. Real phone latency still has
to be measured because invocation, memory movement, and runtime overhead may erase
the theoretical saving.

## Decision

Advance motif (1,10) from **provisional learned motif** to **hardware probation**.

Do not yet retire or bypass the original two-cell implementation. It remains the
fallback until real-device total-cost measurements pass.
