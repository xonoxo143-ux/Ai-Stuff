# Agent v1-A1 destructive-update reversion diagnostic

**Date:** 2026-09-27  
**Status:** implementation experiment

## Question

Private recurrent parameter changes causally contribute to forgetting, but neither routing usage nor old-skill execution lesions identify the responsible cells reliably.

The next question is:

> Are the destructive parameter updates themselves localized to a small set of private cells, and are those updates separable from useful new-family learning?

## Exact intervention

For each sampled lifetime checkpoint:

1. snapshot all private recurrent cell parameters before the next-family block;
2. train the next family normally;
3. if old-family held-out loss worsens, retain that post-training model;
4. on a separate diagnostic stream, revert one cell's private parameter rows from post-training values back to their pre-training values;
5. score how much old-family loss is repaired.

Private rows are:

```text
w_ih
w_hh
b_ih
b_hh
w_msg
b_msg
```

Router/workspace/shared parameters remain exactly at their post-training values.

## Per-cell score

```text
score[c]
=
mean_old_loss(post)
-
mean_old_loss(post with private row c reverted)
```

Positive means the update to cell `c` contributed to old-skill damage.

Scores are measured on stream 2.

## Independent evaluation

Protection is evaluated on stream 1, which is not used for ranking.

For widths:

```text
k = 1, 2, 4, 8, 16
plus 32 for sparse64
```

compare:

```text
revert top-k destructive updates
revert random-k private updates
revert bottom-k update scores
```

For each branch:

```text
protection
=
old_loss(post baseline)
-
old_loss(reverted)

learning_cost
=
new_loss(reverted)
-
new_loss(post baseline)
```

Positive protection is good.
Positive learning cost means the reverted update carried useful new-family learning.

## Same trajectories first

Initial run deliberately reuses:

```text
world seeds: 1501,1502,1503
model seed base: 16000
checkpoints after: 15,31,47,55
family count: 64
```

These are the exact settings from causal-cell isolation.

The baseline damaging transitions should therefore reproduce. This makes the experiment a mechanistic follow-up, not a new population estimate.

Any positive mechanism signal must later replicate on fresh seeds.

## Decision

### Top-k destructive reversion beats random-k

Forgetting is localized in identifiable private-cell updates.

Then inspect whether protection can be obtained with modest new-learning cost.

### Top-k protects but learning cost tracks protection closely

Old retention and new learning are carried by the same updates; this is a genuine stability/plasticity conflict, not merely bad cell selection.

### Top-k does not beat random-k on the independent stream

Per-cell destructive attribution is unstable or interactions dominate. Stop pursuing simple cell-row protection.

### Sparse64 has a better protection/learning-cost curve than fixed16

Extra sparse stored capacity may provide a real structural route around interference even though average acquisition is slower.

## Original idea anchor

The Agent v1 goal remains lifetime self-reorganization under sparse active compute and finite resources.

This diagnostic identifies what development would need to control; it is not itself the developmental mechanism.
