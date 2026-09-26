# Agent v0 — Result 08: motif hardware probation

**Date:** 2026-09-26  
**Motif:** cells **(1,10)**  
**Compiled implementation:** hidden width 64, 47,552 parameters  
**Device:** physical Android target

## Real-device boundary benchmark

The teacher and compiled graphs consumed the exact same 482-float motif boundary.

| implementation | mean | median | p90 | p95 |
|---|---:|---:|---:|---:|
| original two-cell teacher | 0.1198 ms | **0.1142 ms** | 0.1296 ms | 0.1719 ms |
| compiled motif | 0.0542 ms | **0.0505 ms** | 0.0593 ms | 0.0640 ms |

Teacher / compiled:

- median ratio: **2.263×**
- mean ratio: **2.213×**
- local median latency reduction: **55.8%**
- local mean latency reduction: **54.8%**

The result is consistent across the 12 alternating-order trials. The compiled
path was faster in every trial.

## Behavioral envelope

Phone-sample boundary difference:

- maximum output absolute delta: **0.03323**
- offline mean absolute compiled-vs-teacher delta on the phone samples:
  **0.00152**

The separately completed six-seed task probation remains the relevant end-task
quality check:

- mean task MAE delta vs teacher: **−0.00202**
- non-worse fraction: **6/6**
- worst observed task delta: **−0.00007**
- motif use: **21.6%** of thought rows

The compiled implementation therefore remains inside the tested behavioral
envelope while being substantially cheaper at the motif boundary.

## Whole-system economics

Do **not** equate a 2.26× boundary speedup with a 2.26× Agent speedup.

At the observed 21.6% motif-use rate, a simple upper-bound estimate from the
standalone boundary timings gives roughly:

```text
mean local saving per motif use
  ≈ 0.119835 - 0.054159
  ≈ 0.065676 ms

usage-weighted saving per thought
  ≈ 0.216 × 0.065676
  ≈ 0.0142 ms
```

Against the earlier full sparse thought mean (~0.985 ms), that is only around
**1.4%** before accounting for motif recognition, boundary construction,
dispatch, and any loss of fusion/locality in the full runtime.

Therefore this hardware result passes **local hardware probation**, but it does
not yet prove that inserting this one motif into the full Agent lowers total
system cost.

## Developmental interpretation

The full candidate lifecycle has now demonstrated:

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
real-device local cost probation
        ✓
whole-system marginal utility
        NOT YET PROVEN
```

This is important: the project has now shown that a learned recurring interaction
can be discovered, causally validated, compressed into a smaller learned unit,
and executed materially faster on the target phone without degrading the tested
task distribution.

But the project's promotion rule is stricter than local success.

## Decision

Advance motif (1,10) to:

> **validated compiled candidate / whole-system probation**

Do not yet retire the source cells or make the compiled motif the default runtime
path.

The next implementation should make motif dispatch a first-class runtime
operation rather than bolting a second ONNX call onto the current monolithic
thought graph. Only then can total-system marginal utility be measured fairly.

The two uploaded phone result files are byte-for-byte equivalent measurements
from the same benchmark run; treat them as one result, not two independent
replications.
