# Agent Adaptive Reasoning v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Context

Effect-addressed retrieval could often find useful operations, but myopic selection failed because locally helpful operations could destroy future reachability.

A future-reachability oracle gave a large capability jump but was too expensive for ordinary inference.

This experiment asked whether structured future representations or conditional escalation could recover useful parts of that gain.

## Test A — quasimetric-like temporal distance

A state encoder was trained from multi-step developmental graph distances.

Directed distance was constrained by construction using a positive asymmetric latent difference.

Fresh deep tasks:

```text
myopic selector        13.5%
quasimetric selector   20.5%
```

The structured model helped but stayed below the high-leverage threshold and increased active candidate-selection cost.

Decision: do not tune.

## Test B — perfect adaptive-compute upper bound

A diagnostic metacontroller escalated to bounded future search only when the myopic candidate was not future-reachable and another retrieved candidate was.

Small sample:

```text
cheap-only                  20%
adaptive upper bound        40%
escalation fraction         ~25%
```

This is not implementable as-is because determining whether escalation is needed used the oracle itself.

It establishes an upper bound worth pursuing: deep reasoning need not run on every decision.

## Test C — learned escalation trigger

Cheap features:
- current target error;
- immediate improvement;
- best-vs-second candidate margin;
- address-distance margin;
- count/spread of apparently improving candidates.

A small logistic controller learned whether to invoke the expensive search.

Fresh small sample:

```text
cheap-only       16%
learned trigger  24%
perfect trigger  24%
```

Cost allocation:

```text
learned escalation  ~39% of decisions
perfect escalation  ~19%
```

The learned trigger is not promoted: sample size is small, capability delta is below 20 points, and it over-computes relative to the upper bound.

## Surviving result

Conditional computation remains promising because the oracle upper bound shows a large capability/cost separation.

The next gate should not optimize the trigger in isolation.

Instead test whether costly successful searches can be **compiled into durable reusable capabilities**, making future related problems cheaper.

That would make self-improvement measurable as declining active compute for preserved/increased capability.
