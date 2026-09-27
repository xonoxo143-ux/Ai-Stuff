# Agent v1-A1 direct interference diagnostic

**Date:** 2026-09-27  
**Status:** frozen diagnostic; no architectural remedy included  
**Branch:** `experiment/agent-v1-developmental-ecology`

## Original idea anchor

This experiment does **not** replace Agent v1's trunk.

The standing project question remains:

> Can a sparse recurrent agent reorganize its computational anatomy over a lifetime so later cognition becomes more capable and/or cheaper, while structural changes remain causally and economically accountable?

Still retained:

- sparse top-k execution;
- persistent private recurrent cell state;
- a larger stored-capability budget than the active budget;
- developmental specialization;
- causal challenge and probation;
- reversible promotion / retirement / recycling;
- motifs only after the base developmental mechanism earns them;
- real wall-clock economics.

The current 16-mature + 48-reserve design remains a **candidate developmental mechanism**, not a discarded idea and not yet an established requirement.

The purpose of this diagnostic is narrower:

> Determine whether sequential learning actually produces measurable destructive interference, and whether a larger sparse cell bank reduces it.

No reserve recruitment, adaptive plasticity, privileged routing, replay, or motif mechanism is permitted in this experiment.

## Why this test comes next

The fixed-capacity and routing-ceiling experiments did not establish a robust average-loss advantage for 64 stored cells.

A weak late mixed-return signal suggested that the relevant pressure may be retention rather than instantaneous capacity.

Before designing a remedy, measure that pressure directly.

## Measurement basis

The diagnostic follows standard continual-learning measurement ideas rather than inventing a project-specific score:

- Lopez-Paz & Ranzato, *Gradient Episodic Memory for Continual Learning* (2017), arXiv:1706.08840: repeatedly evaluate old tasks through the stream and form a task-by-time performance matrix; report backward transfer.
- Chaudhry et al., *Riemannian Walk for Incremental Learning* (ECCV 2018): distinguish forgetting from inability to learn new material.
- Li et al., *Theory on Mixture-of-Experts in Continual Learning* (2024), arXiv:2406.16437: more experts can require more optimization and need not automatically improve continual-learning performance.
- Guo et al., *Stable Routing for Mixture-of-Experts in Class-Incremental Learning* (2026), arXiv:2605.17571: expert expansion can perturb old routing, so capacity and routing stability must not be conflated.

## Stream

Use the same hidden recurrent family dynamics as the capacity-pressure world, but present families as explicit sequential blocks:

```text
family 0: 20 one-pass training experiences
evaluate family 0

family 1: 20 one-pass training experiences
evaluate families 0,1

family 2: 20 one-pass training experiences
evaluate families 0,1,2

...

family F-1
evaluate all learned families
```

Training and evaluation samples use deterministic disjoint streams.

Evaluation is **cold**: each held-out family probe starts from a fresh recurrent state. This intentionally measures knowledge retained in learned parameters/structure rather than short-lived numerical state carried from the immediately preceding experience.

## Controls

```text
fixed16:   16 stored cells, top-4 active
sparse64:  64 stored cells, top-4 active
```

Everything else is paired:

- world seed;
- model seed;
- family order;
- experiences per family;
- evaluation examples;
- recurrence depth;
- optimizer settings.

No dense-64 control is needed for the primary forgetting question; prior work already established that dense activation is not automatically better and it would add compute without resolving this diagnostic.

## Primary loss matrix

Let

```text
L[i,j]
```

be held-out loss on family `j` immediately after completing training block `i`.

Only entries with `j <= i` are evaluated.

For family `j`:

```text
postlearn_j = L[j,j]

best_after_learning_j
    = min_i>=j L[i,j]

final_j
    = L[F-1,j]

forgetting_j
    = final_j - best_after_learning_j

retention_delta_j
    = final_j - postlearn_j
```

Positive forgetting / retention delta is bad.

Loss-form backward transfer is:

```text
BWT_loss
    = mean_j<F-1 (postlearn_j - final_j)
```

so negative `BWT_loss` indicates forgetting, matching the usual interpretation of negative backward transfer.

## New-family learning

Before training family `j`, measure:

```text
prelearn_j
```

Then:

```text
learning_gain_j
    = prelearn_j - postlearn_j
```

This prevents a "retentive" model that simply fails to learn new families from looking good.

This is not a full intransigence metric against a joint-training oracle; it is a deliberately cheap first diagnostic.

## Structural traces

For every family block record:

1. cell usage distribution during training;
2. per-cell private-parameter update norm during that block;
3. parameter-update norm grouped into:
   - private recurrent cell computation,
   - router/signatures,
   - workspace communication,
   - input/output shared machinery.

For old family `i`, define future routing collision:

```text
collision_i
    = mean_j>i sum_c min(usage_i[c], usage_j[c])
```

and later update exposure:

```text
exposure_i
    = mean_j>i dot(
        usage_i,
        normalize(cell_update_norm_j)
      )
```

Then test whether either predicts `forgetting_i`.

These are correlational diagnostics only; causal lesions come later if a signal exists.

## Initial sweep

```text
family counts: 16, 32, 64
paired seeds: 3
train experiences/family: 20
held-out eval experiences/family/checkpoint: 16
sequence length: 4
thought steps: 2
active cells: 4
```

## Decision table

### Little forgetting in both systems

```text
forgetting16 ≈ forgetting64 ≈ 0
```

Do not build an anti-forgetting mechanism. Either the substrate/world does not create the proposed pressure or another developmental pressure must be found.

### 16 forgets materially more than 64

```text
forgetting16 > forgetting64
```

Extra sparse structural capacity has a retention role. Then localize whether the benefit comes from reduced cell collisions, parameter isolation, routing, or shared machinery before choosing reserve recruitment/plasticity as the remedy.

### Both forget similarly

```text
forgetting16 ≈ forgetting64 > 0
```

Private cell-bank size is probably not the dominant bottleneck. Test shared machinery and routing drift before adding cells.

### 64 learns new families worse

If lower forgetting is accompanied by much smaller learning gain, treat it as a stability/plasticity trade-off rather than a success.

## Promotion rule

This diagnostic can change the next experiment, but it cannot silently replace the original Agent v1 goal.

A candidate mechanism changes the trunk only after it explains a measured failure better than competing explanations and survives paired tests.
