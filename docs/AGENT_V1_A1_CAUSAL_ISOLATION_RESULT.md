# Agent v1-A1 causal-cell isolation result

**Date:** 2026-09-27  
**Commit tested:** `3756a3b20dc44da094c5d26fe4edccd97531188a`  
**Workflow run:** `36346323884`  
**Status:** complete — old-task execution importance does not identify the main destructive update channel

## Primary result

### Fixed-16

```text
intervention          mean protection   mean learning cost   positive protection
all private           +0.003142         +0.006559            6/6
causal top4           +0.000681         +0.001403            6/6
usage top4            +0.001441         +0.002339            6/6
random4               +0.000914         +0.000934            5/6
causal bottom4        +0.002198         +0.004774            6/6
```

Causal-top4 beat random in 3/6 events and usage-top4 in 1/6.

### Sparse-64

```text
intervention          mean protection   mean learning cost   positive protection
all private           +0.002054         +0.004359            4/6
causal top4           +0.000970         +0.001816            5/6
usage top4            +0.000362         +0.001620            4/6
random4               +0.000858         +0.000297            3/6
causal bottom4        +0.000116         +0.001837            3/6
```

Causal-top4 beat random in 4/6 events and usage-top4 in 3/6.

The sparse64 causal-top4 advantage is too small and inconsistent to promote a cell-maturity mechanism.

## Concentration audit

The failure is not explained by causal importance being uniformly diffuse.

Among destructive events, the four highest positive execution-lesion scores captured:

```text
fixed16:  mean 90.6% of positive lesion-damage mass
sparse64: mean 76.4% of positive lesion-damage mass
```

Yet causal-top4 freezing recovered only:

```text
fixed16:  ~21.7% of all-private protection
sparse64: ~47.3% of all-private protection
```

Therefore:

> The cells most causally important for executing an old skill are not necessarily the cells whose parameter changes cause that skill to be forgotten.

This rejects the simple rule:

```text
execution importance -> maturity -> protect
```

## Next diagnostic

Measure destructive **updates**, not old execution importance.

After a next-family block that damages old skills:

1. keep the exact pre-block private-cell parameters;
2. keep the exact post-block trained model;
3. restore one private cell's parameter rows at a time from post to pre;
4. measure how much old-family loss is repaired.

For cell `c`:

```text
update_damage_score[c]
=
old_loss(post)
-
old_loss(post with cell c's private update reverted)
```

Positive means that cell's parameter update causally contributed to forgetting.

Rank on a diagnostic held-out stream and evaluate top-k reversion on the untouched protection stream.

This is post-hoc localization, not a deployable learning rule.
