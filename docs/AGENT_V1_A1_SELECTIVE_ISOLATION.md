# Agent v1-A1 selective private-cell isolation diagnostic

**Date:** 2026-09-27  
**Status:** implementation experiment

## Question

The subsystem localization experiment found that freezing **all** private recurrent cell parameters reduced old-skill damage on every sampled destructive transition, but often at a large new-learning cost.

The next test asks:

> Does it matter *which* private cells are protected?

This directly tests whether functional isolation can improve the stability/plasticity tradeoff.

## Experimental logic

At selected lifetime checkpoints:

1. evaluate a fixed set of old-family anchors;
2. measure which private cells those old families actually route through;
3. train the next family normally in a baseline branch;
4. only if that baseline branch causes positive mean old-family damage, run matched intervention branches from the exact same checkpoint.

The intervention branches are:

```text
baseline
freeze_all_private
freeze_old_top4
freeze_random4
freeze_old_bottom4
```

All branches keep normal execution routing. "Freeze" affects learning only.

### freeze_old_top4

Protect the four private cells most used by the old anchor families.

### freeze_random4

Protect four deterministic random private cells, chosen from outside the top-4 set when possible.

This controls for simply reducing the number of plastic cell rows.

### freeze_old_bottom4

Protect the four least-used private cells.

This tests whether protecting cells unrelated to old behavior has the same effect.

### freeze_all_private

Upper-bound stability intervention from the preceding experiment.

## Frozen-row intervention

Private-cell parameters are stacked by cell:

```text
w_ih, w_hh, b_ih, b_hh, w_msg, b_msg
```

A branch may freeze selected rows while leaving the rest of the tensor trainable.

Because AdamW momentum and decoupled weight decay can move a row even when its gradient is zero, the experiment restores the exact protected parameter rows after every optimizer step. This makes the intervention semantically exact for the branch.

## Damage trigger

No arbitrary architecture mechanism is introduced.

The expensive selective branches are run only when:

```text
baseline mean old-family damage > 0
```

The baseline branch is always measured.

This is not used to claim prevalence of forgetting; the previous full-stream diagnostic already established that. It is only a way to localize destructive transitions efficiently.

## Initial sweep

```text
family count: 64
controls: fixed16, sparse64
paired seeds: 1301,1302,1303
train examples/family: 20
held-out eval examples: 16
thought steps: 2
active cells: 4
checkpoints after families:
7,15,23,31,39,47,55
```

Old anchors at each checkpoint:

```text
first
25%
50%
75%
most recent
```

## Primary quantities

For intervention `g`:

```text
protection_g
=
damage_baseline - damage_g
```

and

```text
learning_cost_g
=
new_learning_gain_baseline - new_learning_gain_g
```

The desired signal is **not** simply maximum protection.

It is improvement of the stability/plasticity frontier:

```text
old_top4 protection > random/bottom protection
while
old_top4 learning cost << all-private learning cost
```

## Decision

### Old-top4 beats matched controls

Old useful computation is locally protectable.

If sparse64 also pays a smaller learning cost than fixed16, that is direct evidence for the original reserve/isolation intuition: protecting mature structure is easier when more uncommitted cells remain available.

### All-private works but top4 does not

Destructive updates are distributed across private computation. A simple cell-level maturity/reserve rule is too coarse.

### Random/bottom ~= old-top4

The benefit is generic reduction in plasticity, not preservation of causally relevant cell identity.

### No branch improves the tradeoff

Do not build selective protection. Return to router/workspace/shared mechanisms or revise the benchmark.

## Original idea anchor

The Agent v1 trunk remains:

> lifetime self-reorganization under sparse active compute, causal accountability, finite resources, and structural changes that must pay rent.

This diagnostic may support or reject one mechanism for achieving that goal. It does not redefine the goal.
