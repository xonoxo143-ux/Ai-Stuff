# Agent v1-A1 causal-cell isolation diagnostic

**Date:** 2026-09-27  
**Status:** implementation experiment

## Why this follows the selective-isolation result

The previous experiment rejected routing frequency as a sufficient signal of which old cells deserve protection.

Agent v0 already established a stronger measurement: execution lesions can reveal stable causal specialization even when activation statistics alone are insufficient.

This experiment therefore asks:

> Does protecting cells that are causally necessary for old-family behavior improve the stability/plasticity tradeoff?

## Causal ranking

At a destructive checkpoint, evaluate the old-family anchor set on a **separate diagnostic stream**.

For each cell `c`:

```text
score_c
=
mean_old_families(
    loss(execution lesion c)
    -
    baseline loss
)
```

The execution lesion is exactly the v0 intervention:

- preserve the router's original top-k decision;
- if the lesioned cell is selected, prevent its private-state update;
- zero its public message;
- do not allow the router to compensate by selecting another cell.

This measures causal contribution of the executed computation.

## Data separation

```text
stream 0 = training
stream 1 = protection / forgetting evaluation
stream 2 = causal lesion ranking
```

Causal cell selection therefore cannot overfit the examples used to score protection.

## Branches

Only when the matched baseline next-family block produces positive mean old-family damage:

```text
freeze_all_private
freeze_causal_top4
freeze_usage_top4
freeze_random4
freeze_causal_bottom4
```

Execution remains unchanged in every branch. Only learning of selected private parameter rows is frozen.

## Primary test

The desired signature is:

```text
protection(causal_top4)
    >
protection(random4)

and preferably

protection(causal_top4)
    >
protection(usage_top4)
```

while:

```text
learning_cost(causal_top4)
    <<
learning_cost(all_private)
```

## Interpretation

### Causal-top4 wins

Cell-level mature structure is a viable abstraction. The next developmental test can ask how an online agent estimates/protects that structure without evaluator lesions.

### Causal-top4 ~= random

Selective protection works mainly through generic plasticity reduction. Do not build a cell-maturity mechanism from these results.

### Causal-top4 ~= usage-top4, both > random

Routing frequency is sufficient after all; the previous result was underpowered/noisy.

### All-private dominates and selective sets fail

Destructive updates are distributed enough that four-cell protection is too coarse or too small.

## Original idea anchor

This remains a diagnostic of the existing Agent v1 developmental-ecology thesis:

> learn which computational organization should persist, which should remain plastic, and whether structural changes repay their cost.

No outcome automatically promotes reserve recruitment, adaptive plasticity, or any other mechanism.
