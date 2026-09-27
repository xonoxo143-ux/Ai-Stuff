# Agent v1-A1 one-step interference localization

**Date:** 2026-09-27  
**Status:** implementation experiment

## Question

The direct interference diagnostic established two facts:

1. old-family competence can degrade during sequential learning;
2. sparse64 often forgets less than fixed16, but it also learns each new family less strongly.

The next question is not yet "which remedy should we build?"

It is:

> Which parameter subsystem is responsible for the backward damage / stability tradeoff?

## Causal intervention

Train the ordinary sequential lifetime.

At selected checkpoints, before learning the next family, clone:

- model parameters;
- recurrent state;
- optimizer state.

From that exact checkpoint run five one-family branches:

```text
baseline        all parameters trainable
freeze_private  private recurrent cell computation frozen
freeze_router   signatures / router projection frozen
freeze_workspace communication/workspace machinery frozen
freeze_shared   event encoder + output/shared remainder frozen
```

All branches receive exactly the same next-family examples and optimizer history.

For the old-family anchor set:

```text
damage
=
mean(post_next_family_loss - pre_next_family_loss)
```

For the new family:

```text
learning_gain
=
pre_next_family_loss - post_next_family_loss
```

Relative to the all-trainable branch:

```text
protection_g
=
damage_baseline - damage_freeze_g
```

Positive protection means freezing group `g` causally prevented backward damage.

```text
learning_cost_g
=
learning_gain_baseline - learning_gain_freeze_g
```

Positive learning cost means the protection was purchased by reducing adaptation to the new family.

## Initial scope

Use the strongest direct-forgetting regime:

```text
64 families
fixed16 and sparse64
3 paired seeds
top-4 active
20 training examples/family
16 held-out evaluation examples
checkpoints after families 7, 15, 31, 47
old-family anchors: early / quartile / midpoint / recent
```

This is a localization experiment, not a production mechanism.

## Interpretation

### Freeze-private strongly protects old skills

Private recurrent weights are a main overwrite channel.

Then candidate remedies such as selective plasticity, reserve isolation, or parameter protection become worth testing.

### Freeze-router strongly protects

Routing drift is moving old inputs onto incompatible computation.

Then reserve growth alone is unlikely to solve the problem; routing stability needs attention.

### Freeze-workspace or freeze-shared strongly protects

The bottleneck is shared machinery.

More private cells are not the primary solution.

### Every freeze protects only by killing new learning

The observed 64-cell advantage may simply be a generic stability/plasticity shift rather than useful structural isolation.

In that case we need a mechanism that improves the Pareto frontier, not merely one that slows learning.

## Original idea anchor

No result here automatically replaces the Agent v1 developmental-ecology plan.

The original goal remains lifetime self-reorganization under sparse active compute and finite economic budget. This experiment exists to identify the pressure and location that any developmental mechanism must actually solve.
