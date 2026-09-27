# Agent v1-A1 selective isolation result

**Date:** 2026-09-27  
**Commit tested:** `8673a1ff87858da4cac1a08973d873d0154ec5a5`  
**Workflow run:** `36345908050`  
**Status:** complete — routing frequency is not a sufficient maturity signal

## Question

Does protecting the four private cells most used by old-family anchors improve the stability/plasticity tradeoff relative to protecting four random or least-used cells?

## Triggered destructive transitions

```text
fixed16:   12 / 21 screened checkpoints
sparse64:   9 / 21 screened checkpoints
```

Only these transitions ran the matched protection branches.

## Fixed-16

```text
intervention         mean protection   mean learning cost   positive protection
all private          +0.00358          +0.00978             9/12
old-used top4        +0.00109          -0.00017             7/12
random4              +0.00144          +0.00037             7/12
old-used bottom4     -0.00029          -0.00312             4/12
```

Paired differences:

```text
top4 - random protection = -0.000355
top4 - bottom protection = +0.001374
top4 learning cost - all-private learning cost = -0.009950
```

Top4 beat random on 6/12 events. Median top4-random protection was slightly negative.

## Sparse-64

```text
intervention         mean protection   mean learning cost   positive protection
all private          +0.00061          +0.00408             6/9
old-used top4        +0.00011          +0.00062             6/9
random4              +0.00042          -0.00049             5/9
old-used bottom4     ~0                ~0                   2/9
```

Paired differences:

```text
top4 - random protection = -0.000310
top4 - bottom protection = +0.000110
top4 learning cost - all-private learning cost = -0.003457
```

Top4 beat random on 4/9 events. Median top4-random protection was approximately zero.

## Interpretation

The useful part survives:

> Freezing only four private rows preserves far more new-learning ability than freezing every private row.

But the proposed identity signal fails:

> High routing frequency does not identify private cells whose protection is more valuable than a matched random set.

Therefore do **not** promote a rule such as:

```text
high usage -> mature -> protect
```

The result does not falsify selective isolation in general, because Agent v0 already demonstrated that activation frequency and causal importance can differ.

## Next gate

Reuse the validated Agent v0 execution-lesion intervention.

For old-family anchors, rank each cell by:

```text
causal_damage(cell)
=
held_out_loss_with_cell_execution_lesioned
-
baseline_held_out_loss
```

Use a disjoint diagnostic stream for lesion ranking and keep the protection evaluation stream unchanged.

Then compare:

```text
freeze causal-top4
freeze usage-top4
freeze random4
freeze causal-bottom4
freeze all-private
```

If causal-top4 still does not beat random or usage controls, simple cell-level maturity/protection is not earning promotion.
