# Agent Operator Routing Gate v0

**Date:** 2026-09-29  
**Status:** RESULT — HIGH-LEVERAGE GATE FAILED  
**Source hypothesis:** `AGENT_RESEARCH_SYNTHESIS.md`

## Question

> Does explicit operator decomposition produce a **large compositional-OOD gain** over the current shared factor processor when representation, parameter count, execution depth and training budget are controlled?

This is an **upper-bound diagnostic**.

It does not claim that a real agent will receive oracle operator labels.

## Why this gate comes first

The literature refresh separated four problems:

```text
decomposition
binding/state
routing/sequencing
execution/plasticity
```

Testing automatic module discovery and learned routing at the same time would make failure ambiguous.

So v0 deliberately supplies the semantic decomposition and execution route.

If even this oracle upper bound does not provide a large OOD gain, do not spend another cycle trying to learn the route.

## Task

Use the existing Cognitive Transfer v0 held-out family:

```text
relation traversal
→ memory lookup
→ inferred rule transform
```

Train on chain length 1–2.

Test OOD on chain length 3–5.

## Arms

### A — shared factor processor

```text
FactorGraphCore
dim = 64
8 recurrent steps
no input reinjection
```

### B — oracle-routed operator bank

Shared:

- slot encoder;
- symbol/entity state;
- query/answer readout.

Separate learned execution operators:

1. relation phase;
2. memory phase;
3. rule phase.

Fixed oracle execution schedule:

```text
relation ×5
memory   ×2
rule     ×1
```

Rows outside the active semantic phase do not update during that phase.

This is intentionally favorable to the decomposition hypothesis.

## Parameter control

The operator core uses dimension 40 so total parameter count is within 1% of the dim-64 shared factor baseline.

Both arms use eight execution steps.

## Training

Three seeds:

```text
11, 22, 33
```

Same IID task-6 data distribution, optimizer, batch size and update budget.

Checkpoints:

```text
0, 128, 256, 512, 768, 1024
```

Primary outputs:

- IID accuracy;
- OOD accuracy;
- learning curve;
- final OOD delta;
- parameter count;
- wall time.

## High-leverage gate

Pass only if:

```text
mean oracle OOD - mean shared OOD >= 20 percentage points
```

A smaller positive effect is recorded but does not earn a learned-routing branch.

## Interpretation

```text
oracle ≈ shared
→ explicit operator decomposition is not enough
→ kill this branch before routing work

oracle >> shared
→ decomposition has real capacity value
→ next isolate learned routing

oracle high IID, weak OOD
→ decomposition fits the task but does not solve extrapolation
→ kill or redesign the state/operator interface

oracle strong OOD
→ learned routing becomes the next gate
```

## Local screen that triggered CI

A reduced parameter-matched local screen was used only as a cheap triage step:

```text
1024 updates, one seed, reduced dimensions/batch

shared screen   19.7% IID   22.0% OOD
oracle screen   60.3% IID   36.3% OOD
```

The shared screen was much weaker than the canonical full-size baseline, so these numbers are **not project evidence**.

They only justified paying for the rigorous three-seed run.


## Rigorous result

Workflow run: `36635945973`  
Artifact: `Agent-Operator-Routing-Gate-V0`  
Seeds: 11, 22, 33

Parameter control:

```text
shared factor processor   104,928 params
oracle operator core      104,632 params
difference                    296 params (~0.28%)
```

Three-seed mean after 1024 updates:

```text
                         IID      OOD
shared factor core      43.7%    27.0%
oracle operator core    95.8%    41.2%
```

Mean OOD delta:

```text
+14.2 percentage points
```

Precommitted pass threshold:

```text
+20.0 percentage points
```

**Gate: FAIL.**

Per-seed final OOD deltas:

```text
seed 11   +20.5 points
seed 22    +5.5 points
seed 33   +16.5 points
```

The direction is positive but not robust enough or large enough to pass the project gate.

## Interpretation

The oracle decomposition makes the task dramatically easier to **fit**:

```text
43.7% IID → 95.8% IID
```

but the same architectural help produces only:

```text
27.0% OOD → 41.2% OOD
```

on longer relation chains.

So the key failure is not that the network cannot represent or optimize the three-phase composition.

It can.

The failure is that learned execution inside the supplied phases still does not extrapolate strongly enough to greater composition depth.

Because the route was already supplied by the benchmark, **learned routing is not the next bottleneck to test**.

## Decision

Per the precommitted kill rule:

- do **not** build the learned-router branch;
- do **not** optimize this oracle operator core for a few extra points;
- retain the result that explicit decomposition strongly improves fitting/sample acquisition;
- do not promote the operator-bank architecture into `AGENT_CURRENT.md` as a surviving core.

The next research question moves one level inward:

> What makes a learned operation itself extrapolate across **depth/length** once decomposition and routing are already correct?

Research should focus on algorithmic alignment, recurrent/iterative operators with depth invariance, variable/binding stability, and training objectives that force execution rules rather than short-chain heuristics.
