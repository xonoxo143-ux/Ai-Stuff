# Agent Operator Routing Gate v0

**Date:** 2026-09-29  
**Status:** ACTIVE EXPERIMENT  
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
