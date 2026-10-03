# Agent v0 — Phone Result 02: recurrence and context

**Date:** 2026-09-25  
**Device result:** stable-signed Agent v0 build  
**Model:** 16 cells, top-4 active, state width 96, 3 trained recurrent thoughts/event

## Recurrence result

The depth sweep is decisive enough to keep the current recurrent design, but not to
treat "more thought" as automatically better.

| thought depth | MAE |
|---:|---:|
| 1 | 0.8262 |
| 2 | 0.3100 |
| **3** | **0.1852** |
| 4 | 0.5937 |
| 6 | 1.0302 |

The model was trained with three recurrent thought steps. On-device performance
improves sharply from one to three steps and then degrades sharply beyond the
trained depth.

This establishes two useful facts:

1. recurrent internal computation is doing real task work; one pass is not enough;
2. recurrence is not monotonic "extra intelligence". The learned dynamics have a
   useful horizon and then drift/overthink outside the trained regime.

Do **not** add arbitrary extra thought steps. Adaptive depth will eventually need
training that explicitly makes stopping/depth part of the objective.

## Routing result

All 16 cells were used across every tested depth.

Mean first-to-last selected-cell overlap within an external event:

- depth 2: 0.900
- depth 3: 0.873
- depth 4: 0.807
- depth 6: 0.749

So recurrent thought is not merely rerunning an absolutely fixed coalition.
Longer recurrence increasingly changes the selected set. However, the accuracy
curve shows that reconfiguration beyond the trained horizon is harmful.

Same-operation routing across different preceding contexts is partly but not
uniformly context-sensitive. Examples at the first thought:

- SET Jaccard ≈ 0.63
- SQUARE ≈ 0.54–0.66 depending on depth
- HALF ≈ 0.64–0.87
- MUL ≈ 0.61–0.64
- ADD ≈ 0.78–0.91
- NEG ≈ 0.91–1.00
- ABS ≈ 0.91–1.00

Interpretation: routing is strongly operation-sensitive and also context-sensitive
for some operations, but several unary operations are close to fixed specialist
coalitions. This is neither a failure nor proof of ideal modularity; the task may
simply permit a stable specialist for those operations.

## Hardware timing

The fresh-process quick test had a 21.26 ms first thought, demonstrating a
significant initialization/cold-start cost.

Across the larger depth benchmark, per-thought medians were roughly 0.66–0.88 ms
after the runtime was active. Means were noisier because of several millisecond
outliers.

Therefore use medians/warm measurements for execution economics and measure cold
start separately.

## Decision

**Keep three-step recurrence for this trained model.**

Do not redesign routing yet.

The next experiment is a matched semantic sparse-vs-dense hardware comparison:

- exact same weights;
- exact same top-4 routing decisions;
- exact same committed private states and public messages;
- sparse backend computes only selected cells;
- dense reference backend computes all 16 cell candidates and then commits only
  the same selected four.

This isolates the question the architecture actually cares about:

> Does activating only a fraction of stored capability save real runtime on this
> phone, or does gather/scatter and poor locality erase the theoretical gain?
