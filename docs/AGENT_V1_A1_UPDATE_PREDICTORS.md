# Agent v1-A1 prospective destructive-update predictor

**Date:** 2026-09-28  
**Status:** diagnostic experiment

## Why this is the next gate

Post-hoc destructive-update localization replicated.

The learner still cannot use that fact during life because the score is computed by:

1. applying a block of updates;
2. observing old-family damage;
3. reverting individual cell updates.

A real lifelong chatbot needs a signal available **before or during learning**.

This experiment asks:

> Which pre-update signal, if any, predicts the private-cell updates that later cause forgetting?

No candidate is promoted to architecture by this experiment.

## Literature-derived candidate families

The candidates are motivated by established continual-learning ideas:

- gradient conflict: new gradients can oppose old-task gradients;
- parameter importance: important parameters can be made less plastic;
- online/output sensitivity: importance can be estimated without requiring labels for every past observation.

The implementation uses these only as predictor classes.

## Data separation

```text
stream 0 = actual lifetime training
stream 1 = final protection / forgetting evaluation
stream 2 = old-knowledge predictor features
stream 3 = incoming-family predictor gradient
stream 4 = post-hoc destructive-update ground truth
```

No predictor is ranked on the same examples used for final protection measurement or post-hoc ground truth.

## Candidate cell scores

Let `g_new[c]` be the incoming-family private gradient for cell `c`.

### 1. New-gradient magnitude

```text
score_grad_norm[c] = ||g_new[c]||
```

This asks whether destructive cells are simply the cells receiving the strongest proposed update.

### 2. Usage × gradient magnitude

```text
score_usage_grad[c]
    = old_usage[c] * ||g_new[c]||
```

This is a deliberately simple local baseline.

### 3. Output-sensitivity × incoming gradient

MAS-like old importance is estimated from the absolute gradient of old outputs with respect to private parameters, without using old labels for the importance objective.

```text
score_output_sensitivity[c]
    = sum_p |d old_output_energy / d theta_p|
              * |g_new_p|
```

### 4. Supervised old-loss sensitivity × incoming gradient

Evaluator-only importance baseline:

```text
score_old_loss_sensitivity[c]
    = sum_p |g_old_p| * |g_new_p|
```

This uses old targets and is not assumed deployable.

### 5. Gradient-conflict oracle

First-order destructive interference estimate:

```text
score_conflict[c]
    = max(0, - g_old[c] dot g_new[c])
```

This also uses old examples and acts as an evaluator upper-bound candidate.

## Ground truth

Train the normal next-family block.

For each private cell, on stream 4:

```text
damage[c]
=
old_loss(post)
-
old_loss(post with cell c update reverted)
```

## Evaluation

For every predictor:

1. Spearman rank correlation with `damage[c]`;
2. overlap between predictor top-4 and destructive top-4;
3. revert predictor top-4 on stream 1;
4. compare old-skill protection against deterministic random-4;
5. record new-family learning cost.

The destructive-ground-truth top-4 is retained as a post-hoc ceiling.

## Decision

### A simple deployable predictor wins

If gradient magnitude, usage×gradient, or output-sensitivity predicts damage substantially better than random, test **prospective gating** next.

### Only evaluator/oracle predictors win

Then the architecture needs a persistent local trace or importance state that approximates information otherwise supplied by old examples.

Do not add replay automatically.

### Nothing predicts the ground truth

The post-hoc destructive effect may depend on nonlinear interactions or the whole block trajectory. A cell-local pre-update gate is then too simple.

## Chatbot relevance

For a lifelong chatbot, the desired mechanism eventually operates during conversational learning:

```text
experience arrives
→ estimate update risk locally
→ allow / attenuate / redirect learning
→ preserve useful old conversational competence
```

This diagnostic exists before language integration so the first chatbot does not immediately overwrite itself.
