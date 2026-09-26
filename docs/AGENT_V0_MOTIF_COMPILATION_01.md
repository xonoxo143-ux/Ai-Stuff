# Agent v0 — Result 05: first provisional motif compilation

**Date:** 2026-09-26  
**Candidate motif:** cells **(1,10)**  
**Teacher:** original two-cell computation under the learned router  
**Student:** compact learned composite replacing the pair boundary computation

## Why this test

The previous causal screen identified (1,10) as a recurring pair whose joint
execution mattered more than the sum of its individual effects.

That makes it a *provisional motif*, not yet a promoted primitive.

The next question is whether its joint computation can be represented more
cheaply without materially changing task behavior.

## Teacher boundary

For every thought where cells 1 and 10 are both selected, the compiler records:

- each cell's workspace read;
- current event embedding;
- each private state;
- each routing weight.

The student predicts:

- both private-state deltas;
- both weighted public messages.

The original route remains the teacher/fallback.

Training collection:

- 184,320 thought rows inspected;
- 41,229 rows contained the pair;
- motif frequency ≈ **22.4%** of collected thought rows;
- input width: 482;
- target width: 256.

## Results

Teacher pair private multiply estimate:

```text
172,032 multiplies / motif execution
```

| composite hidden | parameters | est. pair compute vs sources | task MAE | Δ task MAE vs teacher |
|---:|---:|---:|---:|---:|
| **64** | **47,552** | **27.5%** | **0.23286** | **+0.00063** |
| 96 | 71,200 | 41.2% | 0.23592 | +0.00369 |
| 128 | 94,848 | 54.9% | 0.23427 | +0.00204 |

Teacher task MAE on the same evaluation set:

```text
0.23223
```

The 64-hidden composite therefore preserves essentially all task quality in this
test while its estimated private-compute requirement is only about **27.5%** of
the two original source cells.

It was used on about **20.3%** of evaluation thought rows.

## Interpretation

This is the first end-to-end example of the developmental path the architecture
was designed around:

```text
learned cells
    ↓
recurring coalition
    ↓
causal validation
    ↓
provisional motif
    ↓
compiled cheaper implementation
```

The result is important because the composite was not hand-coded as an arithmetic
shortcut. It learned to approximate the *joint internal computation* exposed at
the pair boundary.

## Why it is not promoted yet

The current result is offline and uses one fresh evaluation seed.

Promotion still requires:

1. fresh-data replication;
2. quality probation across multiple held-out contexts;
3. real hardware timing;
4. total-system accounting, not multiply count alone;
5. fallback/reversion if the composite leaves its validated applicability region.

The 64-hidden variant is the current candidate because it is both the cheapest
tested implementation and the closest to teacher task quality.

## Current decision

Keep (1,10) as a **provisional learned motif**.

Do not yet replace the source pair globally.

First replicate the causal interaction and then package the 64-hidden composite
for real-device probation.
