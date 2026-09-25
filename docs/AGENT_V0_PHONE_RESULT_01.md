# Agent v0 — First Physical Hardware Result

**Date:** 2026-09-25  
**Model:** `agent-ecology-v0`  
**Status:** first learned ecology executed successfully on physical Android hardware.

## Hardware result

Model configuration:

- 16 learned capability cells
- 4 active cells per thought
- private state width 96
- 4 workspace slots
- 3 recurrent thoughts per external event
- 1,403,810 learned parameters

Observed phone result:

- program MAE: **0.251886**
- training-side forced-recombination MAE: **0.251754**
- total internal thoughts: 18
- total measured model latency: **12.746 ms**
- mean including first cold thought: **0.708 ms / thought**
- first cold thought: **3.983 ms**
- mean after removing first cold thought: **~0.516 ms / thought**

The close phone/training-side error is important: the Android ONNX path is numerically behaving like the exported learned model rather than introducing a meaningful deployment drift.

## Routing observations

The model did not route every operation through the same cells.

Representative top-4 recruitment:

```text
SET     1, 9, 10, 14
ADD     9, 4, 15, 6
SQUARE  7, 12, 3, 4
HALF    1, 3, 10, 14
NEG     3, 7, 5, 8
ABS     7, 5, 0, 13
```

Fourteen of sixteen cells appeared in this single six-event trace.

Within an external event, cell membership was usually stable across the three recurrent thoughts while routing weights shifted. This is evidence of learned routing structure, but **not yet evidence that recurrent re-recruitment is useful**.

The first result therefore exposes the next uncertainty cleanly:

> Does additional recurrent thought improve computation enough to pay for itself, and does routing respond meaningfully to context rather than merely operation identity?

## Interpretation

What this result establishes:

- the learned sparse recurrent ecology runs on the phone;
- private recurrent state survives across external events;
- sparse top-k routing executes correctly;
- routing is nontrivial and distributed across the cell library;
- real steady-state inference cost is currently sub-millisecond per thought for this small model;
- deployment numerics are consistent with offline evaluation.

What it does **not** establish:

- that three thoughts are better than one;
- that context-dependent routing is doing useful work;
- that sparse execution beats a dense matched-capacity baseline;
- that cell specialization is causal rather than correlated;
- that the current model scales;
- that the architecture beats a conventional recurrent baseline.

## Immediate next experiment

Do not redesign the model yet.

Use the same trained weights and same phone runtime to test thought depth and context sensitivity before changing architecture.

Run the same controlled programs at thought depths:

```text
1, 2, 3, 4, 6
```

Measure:

- MAE vs thought depth
- real latency vs thought depth
- cell usage
- within-event recruitment changes
- routing-weight changes
- same-operation routing across different preceding contexts

This isolates the value of recurrence without introducing a new model or new training run.

After that, the next hardware comparison should be sparse-vs-dense matched-capacity execution.
