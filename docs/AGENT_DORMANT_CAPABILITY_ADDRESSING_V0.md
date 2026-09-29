# Agent Dormant Capability Addressing v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can stored computational capability grow by 10×–100× while active retrieval work, I/O and resident memory grow much more slowly?

## Local environment

Python standard library only. SQLite was used for the disk-backed variant. No pretrained model, GPU service, external vector database or ANN library was used.

## Test A — in-memory exact adaptive hierarchy

Store sizes:
- 128 modules
- 1,280 modules
- 12,800 modules

Each module had a 12-dimensional key. Queries were noisy variants of target keys.

Compared:
- exhaustive linear scan;
- flat hash buckets;
- balanced hierarchical metric search.

The final hierarchy used exact branch-and-bound rather than a fixed search budget. It continued only while an unexplored branch's distance lower bound could still beat the current best candidate.

### Moderate noise (0.18)

```text
N       mean inspected
128        17.47
1,280      32.58
12,800     49.70
```

100× storage produced ~2.85× inspection growth.

At 12,800 modules only ~0.39% of the store was inspected per query.

The hierarchy returned the same nearest module as exhaustive linear search on every validation query.

### Harder noise (0.28)

```text
N       mean inspected
128        19.53
1,280      42.67
12,800     98.03
```

100× storage produced ~5.02× inspection growth.

At 12,800 modules ~0.77% of the store was inspected per query.

### Failure found

The Python in-memory index itself scaled roughly linearly:

```text
128       ~0.09 MB
1,280     ~0.83 MB
12,800    ~8.93 MB
```

Therefore Test A did not satisfy the stronger 'small hot RAM' claim.

## Test B — disk-backed hierarchy + cold payload

Lower hierarchy nodes and keys were serialized into SQLite with the database cache explicitly capped to ~256 KiB and mmap disabled.

Capability payloads were stored in a separate disk file at 4 KiB/module.

The in-memory Python store/tree was destroyed before query-time measurement.

Three seeds were run at each scale.

### Moderate noise (0.18)

```text
cold-store growth             ~97.20×
module-inspection growth       ~2.57×
logical bytes/query growth     ~1.47×
payload bytes/query             4096 constant
target retrieval               100%
```

Mean logical bytes touched/query:
- 128 modules: ~5.88 KiB
- 1,280 modules: ~7.34 KiB
- 12,800 modules: ~8.67 KiB

Median local Python+SQLite query latency at 12,800 modules was ~0.48 ms averaged across the seed medians.

### Harder noise (0.28)

```text
module-inspection growth       ~4.85×
logical bytes/query growth     ~2.25×
payload bytes/query             4096 constant
target retrieval               100%
```

Mean logical bytes/query at 12,800 modules: ~13.60 KiB.

### RAM observation

Opening the disk-backed index produced 0–4 KiB measured VmRSS delta in these runs. This is a coarse process-level observation and does not establish physical-device cache residency. The important architectural fact is that the implementation does not materialize the module store or lower tree into Python objects at inference time.

## Interpretation

This is a positive isolated infrastructure result:

> stored bytes and active bytes touched can be strongly decoupled.

It is not yet a cognition result.

The experiment supplied privileged addresses: the query was already near the desired module key.

## Next gate

Replace arbitrary keys with functional/behavioral signatures produced by executing modules.

Given only:
- current state,
- desired outcome / task specification,
- learned experience,

the agent must construct a useful computational address and retrieve/compose modules without being told which module is relevant.

This tests whether 'what matters' can become an addressing principle rather than merely an index lookup.
