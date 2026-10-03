# Agent v0 — Result 07: six-seed causal replication

**Date:** 2026-09-26  
**Model:** agent-ecology-v0

This repeats the execution-lesion analysis on six fresh evaluation datasets
(seeds 31, 37, 41, 43, 47, 53).

## Individual cells

The main causal ranking is stable.

| cell | mean ΔMAE | SD | positive runs |
|---:|---:|---:|---:|
| **7** | **+0.7311** | 0.0656 | 6/6 |
| **3** | **+0.4113** | 0.0832 | 6/6 |
| 10 | +0.2217 | 0.0100 | 6/6 |
| 12 | +0.1742 | 0.0278 | 6/6 |
| 9 | +0.1738 | 0.0276 | 6/6 |
| 8 | +0.1394 | 0.0179 | 6/6 |
| 1 | +0.0979 | 0.0209 | 6/6 |
| 4 | +0.0595 | 0.0071 | 6/6 |

This strengthens the earlier conclusion that the cells are not merely correlated
routing labels. Several have stable causal roles under fresh program samples.

## Pair interaction replication

The strongest stable interaction remains cells **(1,10)**:

```text
mean interaction synergy: +0.17362 MAE
SD:                       0.00935
positive:                 6 / 6
mean coactivations:       1010 per replication
```

Per-seed interaction synergy:

```text
+0.17754
+0.17838
+0.15901
+0.16289
+0.17883
+0.18505
```

Pair (1,14) is also stable but much weaker:

```text
mean synergy: +0.05552
positive: 6 / 6
```

Other recurring pairs are weaker and some change sign across datasets.

## Decision

The (1,10) motif is no longer supported by only one fortunate evaluation sample.
Its super-additive causal effect is stable across all six new replications in
addition to the earlier confirmation datasets.

That justifies advancing the already-compiled (1,10) implementation to physical
hardware probation.

No other pair should be promoted merely because it coactivates frequently.
