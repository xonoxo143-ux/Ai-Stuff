# Agent v1-A1 routing-capacity replication

**Date:** 2026-09-26  
**Status:** running

Independent paired replication of the routing-ceiling result.

## Configuration

```text
family counts: 8, 16, 32, 64
world seeds: 701–706
paired controls:
    learned16
    learned64
    privileged-structured16
    privileged-structured64

active compute: top-4
experiences per family: 20
```

Primary quantity:

```text
privileged-structured64 loss
-
learned16 loss
```

Expected pattern if developmental allocation has a real target:

```text
8 families:     no reliable advantage
16/32/64:       privileged 64 becomes reliably useful
learned 64:     fails to capture some or all of that advantage
```

This is a diagnostic use of privileged routing only. The autonomous v1 agent must eventually infer recruitment/allocation from its own traces and prediction failures.
