# Agent v1-A1 routing ceiling

**Date:** 2026-09-26  
**Commit tested:** `1cc2481380ef8086c401c2eea2dd4f65a7a8dff7`  
**Workflow run:** `36263698180`  
**Status:** first diagnostic complete; replication running

## Why this test exists

The preceding capacity sweep found no reliable advantage from simply training a 64-cell sparse ecology instead of a 16-cell sparse ecology.

That result confounded:

```text
stored representational capacity
vs
ability to allocate/train that capacity
```

Sparse-expert literature independently documents under-trained experts and routing imbalance as failure modes, so the confound is real.

## Diagnostic

The experiment compared:

```text
learned16
learned64

privileged-structured16
privileged-structured64
```

All variants execute only top-4 cells.

The privileged structured route assigns each visible family to a deterministic four-cell coalition. It is evaluator machinery, not a proposed agent mechanism and not a claim of globally optimal routing.

With 16 cells there are four disjoint coalitions.

With 64 cells there are sixteen.

As family diversity grows, the smaller bank must share the same coalitions across more unrelated hidden dynamics.

## First result — three paired seeds

### Learned routing

```text
families   learned64 - learned16
8          +0.02911
16         +0.00179
32         +0.00564
64         +0.00059
```

The learned 64-cell ecology did not beat learned 16 on mean loss at any family count.

### Structured 64 vs structured 16

```text
families   structured64 - structured16   wins
8          -0.00025                       2/3
16         -0.02056                       3/3
32         -0.01335                       3/3
64         -0.00640                       2/3
```

That appears to expose useful additional capacity when allocation is supplied.

However, structured16 itself was often worse than learned16. Therefore **structured64 vs structured16 is not the cleanest capacity comparison**; the fixed partition can handicap the small model.

### Cleaner comparison: structured64 vs learned16

Derived paired means:

```text
8 families    structured64 - learned16 ≈ +0.00905
16 families                           ≈ -0.00702
32 families                           ≈ -0.00837
64 families                           ≈ -0.00743
```

This has the crossover shape the previous sweep did not:

```text
low diversity:
    extra allocated capacity does not help

higher diversity:
    allocated 64-cell capacity beats the learned 16-cell baseline
```

At the same time, learned64 remains unable to realize that advantage.

## Current interpretation

The strongest surviving explanation is now:

> The substrate contains useful extra capacity, but exposing all 64 cells to learned routing/training from the start makes that capacity difficult to allocate and mature.

This is exactly the failure mode that could give dormant reserve cells a purpose:

```text
keep unnecessary capacity out of competition
→ mature a small ecology first
→ introduce new capacity only under persistent pressure
→ probation it before permanent retention
```

But three pairs and one deterministic partition are not enough to unlock A2 by themselves.

## Gate

Run an independent replication with more paired seeds and report **structured64 directly against learned16**, not only against structured16.

If the 16/32/64-family crossover survives, A2 reserve recruitment is unblocked as an experimental mechanism.

If it does not, reserve recruitment remains blocked.
