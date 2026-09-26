# Agent v1-A1 replication 01 — no demonstrated capacity pressure

**Date:** 2026-09-26  
**Commit tested:** `53922ce88bf4c8b3129a558f1060e7701400cba9`  
**Workflow run:** `36258781786`  
**Pairs:** 5  
**World seeds:** 91–95  
**Model seeds:** 1700–1704  
**Result:** the single-seed sparse-64 advantage did not replicate

## Aggregate paired result

Mean loss deltas:

```text
sparse64 - fixed16 = +0.00703
dense64  - fixed16 = +0.01007
dense64  - sparse64 = +0.00305
```

Lower is better.

Win counts:

```text
sparse64 beat fixed16: 1 / 5
dense64 beat fixed16:  1 / 5
sparse64 beat dense64: 2 / 5
```

The present world therefore does **not** establish that 16 cells are capacity-limited.

## Per-pair results

| Pair | fixed16 | sparse64 | dense64 | sparse64 - fixed16 |
|---:|---:|---:|---:|---:|
| 0 | 0.70498 | 0.69596 | 0.70941 | -0.00902 |
| 1 | 0.67484 | 0.68680 | 0.68544 | +0.01196 |
| 2 | 0.71302 | 0.71314 | 0.70924 | +0.00012 |
| 3 | 0.72017 | 0.74288 | 0.74019 | +0.02271 |
| 4 | 0.75125 | 0.76061 | 0.77034 | +0.00936 |

## Mean sparse64 - fixed16 by regime

```text
foundation              +0.02054
family_expansion_a      +0.00739
interaction_a           +0.00131
recombination_a         +0.01359
return_with_decoy       +0.00941
family_expansion_b      -0.00086
mixed_return            +0.00232
```

Only `family_expansion_b` shows a tiny mean advantage for sparse64, far too small to support a developmental-capacity claim.

## Interpretation

The earlier one-seed result was not stable.

This does **not** falsify sparse storage or reserve recruitment in general. It falsifies the narrower assumption that the current eight-family lifetime creates enough representational pressure for extra stored cells to earn their existence.

There are at least two plausible reasons:

1. the 16-cell ecology simply has enough capacity for this world;
2. 64 trainable cells dilute routing/optimization enough that extra capacity cannot become useful within the same lifetime budget.

Both matter to Agent v1.

If (1) dominates, reserve recruitment has nothing useful to do.

If (2) dominates, starting with a small mature ecology and unlocking capacity only when needed may itself be valuable — but that must be demonstrated rather than assumed.

## Decision

**A2 reserve recruitment remains blocked.**

The next gate is a capacity-pressure audit. Vary environmental diversity/complexity while holding active compute narrow and identify a region where:

- fixed16 begins to saturate or interfere;
- additional stored capacity has reproducible marginal value;
- dense activation is not automatically the solution.

Only then should the learned reserve trigger be tested.

## Research alignment

Dynamic expansion in continual learning is typically motivated by exhausted capacity, concept drift, or interference, but expansion also creates complexity and resource costs. Recent streaming work explicitly tries to detect drift and add capacity only when necessary rather than expanding on every change.

Agent v1 should preserve the same discipline while remaining task-free: expansion must be triggered by evidence internal to the agent/runtime, not privileged evaluator task boundaries.
