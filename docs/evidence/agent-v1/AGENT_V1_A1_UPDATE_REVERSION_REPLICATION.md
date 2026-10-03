# Agent v1-A1 destructive-update localization replication

**Date:** 2026-09-28  
**Commit tested:** `557b5378cbf0573168e784e2033f9d8acb777107`  
**Workflow run:** `36372003647`  
**Status:** replicated on six fresh world/model seeds

## Primary result

The post-hoc destructive-update signal replicated.

A private-cell update score was ranked on one diagnostic stream and top-k reversion was evaluated on an independent stream.

### Fixed-16

```text
k   top protection   random protection   top>random   positive score mass   learning cost
1   +0.002563        -0.000005           9/11         56.6%                 +0.004768
2   +0.003535        +0.000773           9/11         78.9%                 +0.006809
4   +0.004305        +0.000892          10/11         95.4%                 +0.009114
8   +0.004334        +0.002795          11/11         99.97%                +0.009544
```

### Sparse-64

```text
k   top protection   random protection   top>random   positive score mass   learning cost
1   +0.000312        +0.000022           9/12         59.6%                 +0.000048
2   +0.000540        +0.000020           8/12         81.7%                 +0.000083
4   +0.000762        +0.000085           8/12         96.9%                 +0.000733
8   +0.000973        +0.000020           8/12         99.97%                +0.000855
```

## Baseline destructive events

```text
fixed16:   11 / 24 checkpoints
sparse64:  12 / 24 checkpoints
```

Mean baseline old-family damage among triggered events:

```text
fixed16:   +0.01515
sparse64:  +0.00684
```

Mean new-family learning gain among those events:

```text
fixed16:   +0.03409
sparse64:  +0.03422
```

So sparse64 showed substantially lower old-family damage on this selected event set without a lower mean new-family learning gain.

At k=4:

```text
fixed16:
  protection = +0.004305
  learning cost = +0.009114

sparse64:
  protection = +0.000762
  learning cost = +0.000733
```

This is suggestive that the larger sparse bank may already sit on a better stability/plasticity tradeoff, but event composition differs and this is not yet a controlled frontier comparison.

## Strongest supported claim

> In this benchmark, forgetting caused by a new-family block is disproportionately attributable to a small subset of private-cell parameter updates, and those updates can be localized post hoc better than random on independent examples.

This claim now survived:

- initial three-seed study;
- six fresh-seed replication;
- independent ranking/evaluation streams.

## What is not established

The experiment does not tell the learner which updates are dangerous **before** they happen.

Post-hoc reversion is an evaluator tool, not a deployable developmental rule.

The next gate is therefore predictive:

> Can signals available before or during a proposed update predict the cells later identified as destructive?

Only a predictor that survives independent evaluation earns a prospective plasticity/gating experiment.
