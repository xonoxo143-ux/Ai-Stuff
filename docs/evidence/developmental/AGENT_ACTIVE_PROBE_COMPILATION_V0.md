# Agent Active-Probe Compilation v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can the developmental system detect when its evidence underdetermines a candidate procedure, acquire only a few discriminating observations, and thereby make self-authored compiled skills reliable?

## Setup

Bounded program hypothesis space:

```text
21,845 programs
4 executable base operations
maximum program depth 7
```

Each task begins with the same seven fixed probes used in Reasoning Amortization v0.

Loop:
1. retain every program consistent with current observations;
2. propose the shortest surviving program;
3. if surviving programs disagree on any candidate probe input, choose a high-disagreement input;
4. query the environment for that one output;
5. filter hypotheses;
6. repeat until remaining programs are behaviorally indistinguishable over the probe domain;
7. test the resulting skill across the full integer grid [-100, 100];
8. compile only correct identified skills.

The chosen query uses disagreement among hypotheses; it does not receive the hidden program identity.

## Three-seed result

### Seed 0
```text
fixed 7-probe generalization   95.0%
active-probe generalization   100.0%
mean extra probes               0.275
median extra probes             0
max extra probes                2
compiled fraction             100.0%
```

### Seed 100
```text
fixed 7-probe generalization   92.5%
active-probe generalization   100.0%
mean extra probes               0.450
median extra probes             0
max extra probes                2
compiled fraction             100.0%
```

### Seed 200
```text
fixed 7-probe generalization   95.0%
active-probe generalization   100.0%
mean extra probes               0.475
median extra probes             0
max extra probes                2
compiled fraction             100.0%
```

Initial seven probes left, on average, roughly 34–42 consistent syntactic programs per task, with maxima of 93–123. Most were behaviorally equivalent enough that no extra observation was needed; ambiguous cases were resolved with at most two additional queries.

## Novel-class result

Across 36 novel classes over the three seeds:

```text
false cache hits                       0
first-encounter generalization       100%
compiled after first encounter       100%
second-encounter cache hit           100%
second-encounter correctness         100%
```

## Interpretation

Positive toy-domain result:

> active evidence acquisition repaired the specification ambiguity that limited reliable reasoning compilation, at a very small query cost.

The developmental system can now:
- reason/search;
- propose executable code;
- recognize unresolved behavioral ambiguity;
- ask a discriminating question;
- reject whole families of wrong hypotheses from the answer;
- compile only after sufficient identification;
- reuse the resulting skill without search.

## Limitations

This is a finite bounded hypothesis space with an environment capable of answering behavioral probes.

It does not establish:
- general verification of arbitrary Python;
- proof of open-domain program correctness;
- learned question generation in a continuous space;
- safety of unrestricted self-modification;
- conversational intelligence.

## Next gate

Combine self-construction, falsification, cold storage, sparse addressing, conditional search, and compilation over one growing developmental lifetime.

The central metric becomes:

```text
total accumulated capability
------------------------------
active compute + active bytes touched
```

and how that ratio changes as the skill library grows.
