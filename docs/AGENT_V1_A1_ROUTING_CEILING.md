# Agent v1-A1 routing ceiling

**Date:** 2026-09-26  
**Status:** running

## Question

The capacity sweep found no reliable advantage from increasing the learned ecology from 16 to 64 cells.

That result confounds two effects:

```text
stored representational capacity
vs
ability to route/train that capacity
```

Sparse-expert literature independently warns that poor routing can leave experts under-trained, so this is a real confound rather than a project-specific excuse.

## Diagnostic design

Compare:

```text
learned16
learned64

oracle16
oracle64
```

All sparse variants still execute top-4 cells.

For oracle routing, evaluator-visible family identity is assigned to a deterministic four-cell coalition.

With 16 cells there are four disjoint coalitions.

With 64 cells there are sixteen.

As family count rises, oracle16 is therefore forced to reuse the same cell coalitions across unrelated hidden dynamics much more often than oracle64.

The oracle route is privileged evaluator machinery and is **not** a candidate agent architecture.

## Interpretation matrix

### oracle64 improves, learned64 does not

Extra capacity is useful, but learned allocation/training is the bottleneck.

That would strengthen the case for developmental reserves: keep excess capacity dormant and mature it only when needed.

### neither oracle64 nor learned64 improves

Current cells are not capacity-limited under this benchmark. Reserve recruitment remains unjustified.

### both improve

The prior learned-routing sweep was underpowered/noisy; replicate before A2.

### learned64 improves but oracle64 does not

The fixed oracle partition is a poor diagnostic; do not infer a capacity result from it.

## Gate

Do not implement learned reserve recruitment until this diagnostic and replication are interpretable.
