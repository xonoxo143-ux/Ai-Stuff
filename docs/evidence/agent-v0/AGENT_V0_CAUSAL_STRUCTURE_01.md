# Agent v0 — Result 04: causal specialization and interaction motifs

**Date:** 2026-09-25  
**Model:** agent-ecology-v0  
**Method:** preserve routing decisions, lesion selected cells' private update + public message

## Why this test

Routing frequency is correlation. Before treating learned cells or recurring coalitions
as reusable structure, the project needs evidence that their executed computation
causally matters.

The test keeps the router's decision fixed. When a cell is lesioned, it remains
"selected" but:

- its private recurrent state is not updated;
- its public message is suppressed.

The rest of the selected coalition executes normally.

The analysis was repeated on three independently generated held-out evaluation sets
(seeds 29, 71, 113), each forcing operation combinations withheld during training.

## Stable individual causal roles

Mean increase in MAE when each cell is execution-lesioned:

| cell | mean ΔMAE | interpretation from strongest operation effects |
|---:|---:|---|
| **7** | **+0.725** | especially SQUARE, ABS, NEG |
| **3** | **+0.417** | especially NEG, MUL |
| 10 | +0.194 | ADD / SQUARE |
| 12 | +0.175 | strongly SQUARE |
| 9 | +0.169 | SQUARE / ADD |
| 8 | +0.137 | strongly SUB |
| 1 | +0.107 | SQUARE / HALF / SET |
| 4/6/15 | ~+0.05 | smaller but repeatable effects |
| 11/13 | ~+0.002–0.004 | near-neutral in this evaluation |
| **2** | **−0.011** | removing it slightly improved average performance |

The ranking is stable across fresh datasets. Cells 7 and 3 are not merely frequently
routed; removing their actual computation causes large, operation-structured damage.

This is evidence of causal specialization, although not necessarily monosemantic
specialization. One cell can participate in several related computations.

## Stable pair interaction

Cheap proposal stage: rank pairs by baseline coactivation frequency.

Expensive validation stage: lesion both cells together and compare pair damage with
the sum of individual lesion damages.

For pair **(1, 10)**:

| seed | interaction synergy ΔMAE |
|---:|---:|
| 29 | +0.165 |
| 71 | +0.145 |
| 113 | +0.149 |

Mean: **+0.153**, SD ≈ **0.009**.

The pair's mean joint damage is about **+0.454 MAE**, materially larger than the
damage predicted by adding its two individual effects.

Pair **(1, 14)** is weaker but also stable:

- mean interaction synergy ≈ **+0.060 MAE**
- all three evaluation seeds positive.

Several other pairs are near-additive or sub-additive, including strongly negative
interaction values for some pairs involving cell 7. Therefore coactivation alone is
not enough to infer a useful motif.

## Decision

The primary v1.9 interaction-motif hypothesis survives its first learned-substrate
causal test.

The useful persistent unit cannot safely be assumed to be only an individual cell.
At least one recurring pair, (1,10), shows a stable super-additive causal effect
across fresh evaluation sets.

This is still a controlled toy substrate. It does **not** establish that the same
phenomenon scales to language or broad cognition.

## Engineering consequence

Do not hand-label cells as skills and do not promote every frequent coalition.

Carry forward the existing rule:

```text
cheap coactivation / compression screen
        ↓
causal intervention
        ↓
provisional motif
        ↓
joint probation
        ↓
promotion only if it pays total-system rent
```

The next experiment should treat (1,10) as the first **provisional learned motif**
and attempt to compile its joint computation into a cheaper composite implementation.
The original two-cell route remains the teacher/fallback. Promotion succeeds only if
the composite preserves behavior while reducing real execution cost.
