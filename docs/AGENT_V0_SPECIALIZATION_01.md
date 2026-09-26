# Agent v0 — Learned specialization and interaction screen

**Date:** 2026-09-26  
**Model:** `agent-ecology-v0`  
**Purpose:** determine whether the learned capability cells are merely routed
differently or whether individual cells and cell pairs make distinct causal
contributions.

## Method

The model is evaluated on 512 programs containing operation pairs withheld during
training.

For a lesion, routing is left unchanged. If a lesioned cell is selected:

- its private state update is suppressed;
- its public message is zeroed;
- the router is **not** allowed to replace it with another cell.

This isolates the causal value of the computation executed by that cell under the
existing policy.

For pair screening, frequently coactivated pairs are lesioned together. Pair
interaction is:

```text
interaction synergy
= damage(pair) - damage(cell A) - damage(cell B)
```

Positive values indicate a joint effect larger than the two independent lesion
effects would predict.

## Baseline

Forced-recombination MAE on this analysis set:

```text
0.26779
```

## Routing specialization

Several cells are already strongly specialized by operation.

| Cell | Dominant recruitment |
|---:|---|
| 2 | SUB ~90.1% |
| 6 | ADD ~94.4% |
| 12 | SQUARE ~91.6% |
| 13 | ABS ~79.5%, SUB ~19.8% |
| 4 | ADD ~74.2% |
| 15 | ADD ~68.5%, SQUARE ~31.5% |
| 1 | SET ~60.0%, HALF ~39.3% |
| 0 | ABS ~53.1%, SUB ~32.5% |
| 7 | SQUARE / NEG / ABS / MUL |
| 3 | NEG / MUL / HALF / SQUARE |

So the learned ecology has not collapsed into sixteen interchangeable recurrent
units. Some cells are narrow specialists and others participate across related
operation families.

## Single-cell causal damage

Largest MAE increases when executed computation is suppressed:

| Cell | Δ MAE | Strongest affected operations |
|---:|---:|---|
| 7 | +0.7003 | SQUARE, ABS, NEG, SUB |
| 3 | +0.4113 | NEG, MUL, SUB, ADD |
| 10 | +0.1777 | ADD, SQUARE, ABS |
| 9 | +0.1745 | SQUARE, ADD, MUL |
| 12 | +0.1479 | SQUARE |
| 8 | +0.1170 | SUB, MUL, NEG |
| 1 | +0.0954 | SQUARE, HALF, SET |
| 4 | +0.0483 | SQUARE, ADD |

Cells 0, 2, and 5 have slightly negative aggregate single-lesion deltas on this
dataset. That does **not** mean they are useless: the same cells can matter in
specific contexts, and routing was frozen during lesion. It does mean the current
ecology contains some redundancy or locally counterproductive computation worth
challenging later.

## Pair interactions

The strongest positive interaction found was:

```text
cells 1 + 10
coactivations: 2016
single-damage sum: +0.2731 MAE
pair damage:       +0.4385 MAE
interaction:       +0.1654 MAE
```

This is substantially more than additive and is our first learned-model candidate
for an economically meaningful interaction motif.

Other positive interactions include:

- cells 1 + 14: +0.0648 interaction MAE
- cells 0 + 7: +0.0360
- cells 0 + 5: +0.0282
- cells 1 + 9: +0.0265
- cells 3 + 5: +0.0257

The most damaging pair overall was 3 + 7, but its interaction term is negative:
their joint lesion is highly destructive while less than the sum of their
individual damage. That looks more like overlapping/redundant causal support than
a super-additive motif.

## Interpretation

The first learned model now shows all three of the following:

1. **routing specialization** — cells are recruited nonuniformly by operation;
2. **causal specialization** — suppressing particular selected cells damages
   behavior in operation-specific ways;
3. **non-additive cell interaction** — at least one frequently coactive pair has
   a materially super-additive causal contribution.

This is stronger than simply observing different activation patterns.

It is still one model and one analysis dataset. Before promoting any interaction
motif, the candidate must survive fresh-data replication.

## Next test

Run the same causal screen across multiple independent evaluation seeds and
measure whether:

- cell specialization rankings remain stable;
- the 1+10 interaction remains positive;
- candidate motifs recur under new program samples;
- negative/near-zero single-cell lesions are reproducible.

Only stable candidates proceed to exact motif probation or distillation.
