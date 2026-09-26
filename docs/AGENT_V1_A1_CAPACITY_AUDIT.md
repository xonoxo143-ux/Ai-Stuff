# Agent v1-A1 capacity-pressure audit

**Date:** 2026-09-26  
**Commit tested:** `775369918dda7939ddb3d445aa6313eac2d54091`  
**Workflow run:** `36259235363`  
**Status:** complete — expected raw-capacity crossover not found

The controlled family-dynamics sweep tested:

```text
family count: 8, 16, 32, 64
controls: fixed16, sparse64, dense64
paired seeds: 3
active sparse budget: top-4
```

## Aggregate result

```text
families   sparse64-fixed16   sparse wins   dense64-fixed16
8          -0.01133           2/3           +0.02875
16         -0.00141           2/3           -0.00099
32         +0.00593           0/3           +0.00139
64         +0.00190           0/3           -0.00345
```

Lower is better.

Late mixed-return sparse64-fixed16 deltas:

```text
8    +0.00357
16   +0.01993
32   +0.00308
64   -0.00017
```

## Interpretation

The predicted crossover did not appear.

Increasing environmental diversity did not make the learned sparse-64 ecology progressively better than fixed-16.

This leaves two major explanations:

1. 16 recurrent cells are not representationally saturated by this benchmark;
2. additional cells could be useful, but larger learned routing/training makes that capacity difficult to allocate and mature.

The present sweep cannot distinguish those explanations because model size and routing/optimization difficulty change together.

## Decision

Reserve recruitment remains blocked.

The next gate is an evaluator-only routing ceiling:

```text
learned16 vs learned64
oracle16  vs oracle64
```

The oracle route assigns visible families to deterministic top-4 coalitions. It is not a proposed autonomous-agent mechanism. It exists only to remove routing quality from the raw-capacity question.

If oracle64 gains a diversity-dependent advantage while learned64 does not, the bottleneck is allocation/trainability.

If oracle64 also fails to gain, reserve capacity has not yet earned a role in this substrate.
