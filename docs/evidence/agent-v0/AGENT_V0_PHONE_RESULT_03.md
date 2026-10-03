# Agent v0 — Phone Result 03: sparse vs dense hardware economics

**Date:** 2026-09-25  
**Model:** agent-ecology-v0  
**Device:** physical Android target  
**Comparison:** exact same learned weights, router decisions, committed state, and public messages

## Result

The sparse backend evaluated only the selected 4 of 16 capability cells.
The dense reference evaluated all 16 cell candidates and then committed the exact
same selected 4.

Semantic parity was exact across the measured run:

- maximum output absolute delta: **0**
- selected-cell mismatches: **0**
- maximum route-weight absolute delta: **0**

Measured thought latency:

| backend | mean | median | p90 | p95 |
|---|---:|---:|---:|---:|
| sparse top-4 | 0.985 ms | **0.732 ms** | 1.494 ms | 2.303 ms |
| dense all-16 | 1.645 ms | **1.304 ms** | 2.756 ms | 3.959 ms |

Dense / sparse:

- median ratio: **1.783×**
- mean ratio: **1.671×**

All **12/12 paired trials** had lower total runtime for sparse execution.

The median sparse path uses about **56.1%** of dense latency, a hardware saving of
about **43.9%** at identical behavior.

## Important nuance

The theoretical private-cell candidate-compute ratio is 4× because only 4/16 cells
execute. Real hardware speedup is ~1.8×, not 4×.

That gap is expected to contain costs which do not disappear with sparse private
computation:

- event encoding;
- all-cell routing/signature scoring;
- top-k;
- workspace reads/writes;
- message transport;
- tensor gather/scatter;
- ONNX invocation;
- memory/cache behavior.

This is precisely why the phone benchmark exists: mathematical sparsity is not
equivalent to wall-clock sparsity.

There was also an execution-order/thermal effect. Trials where sparse ran first
showed a larger dense/sparse ratio than trials where dense ran first, despite
alternating order. Therefore use the aggregate paired result rather than treating
any individual trial ratio as architecture truth.

## Decision

**Keep sparse activation.**

This is the first direct physical evidence for the project's central runtime
premise:

> much more stored capability can exist than is actively computed, and activating
> only the relevant subset can lower real runtime cost on the target phone.

The result does **not** yet establish scaling behavior, optimal sparsity, or that
the learned cells are causally meaningful specialists.

## Next question

Routing correlation is not enough. Before building structural promotion around
these cells, test whether individual cells and recurring cell pairs have causal
effects.

Next experiment:

1. preserve router decisions;
2. lesion a selected cell's private update and public message;
3. measure task degradation globally and per operation;
4. use cheap baseline coactivation to propose recurring cell pairs;
5. jointly lesion those pairs;
6. compare pair damage with the sum of individual damage.

A super-additive pair effect would be evidence that useful computation can belong
to a coalition rather than a single cell — directly relevant to the v1.9
interaction-motif hypothesis.
