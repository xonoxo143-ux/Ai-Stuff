# Agent Research Synthesis — Integrated Possibility Model

**Date:** 2026-09-29  
**Status:** LIVING RESEARCH MODULE — PROJECT INFERENCE  
**Pair:** `AGENT_RESEARCH_FINDINGS.md`

## Purpose

This file answers:

> **When the external findings are linked together with our own experiments, what architecture or mechanism appears possible — and how does that belief change when we test it?**

This file is allowed to hypothesize.

It must **never disguise synthesis as established science**.

```text
external literature
        ↓
AGENT_RESEARCH_FINDINGS.md
        +
our immutable experiment/result records
        ↓
this synthesis
        ↓
discriminating experiment
        ↓
AGENT_CURRENT.md only if the mechanism survives
```

A dedicated research chat should normally load **FINDINGS + SYNTHESIS together**.

---

## Current integrated model

### S1. The missing thing is probably not “a better monolithic core”

Our largest cognitive gain came from changing internal organization:

```text
flat MLP          23.9% OOD
factor one-pass   59.8% OOD
```

But the shared factor processor later showed:

```text
task-6 transfer IID   96.0%
task-6 transfer OOD   40.5%
```

It can fit a new composition but does not reliably extrapolate it.

External research independently keeps finding that systematic reuse depends on decomposition, specialization, binding, routing, and the training distribution.

**Current synthesis:**

> Keep a structured relational state, but stop expecting one undifferentiated learned processor to become a general compositional engine merely through multitask exposure.

**Confidence:** high.

---

### S2. Reusable computation probably has to become identifiable during learning

Our failed frozen-HOW experiment assumed that ordinary multitask training had already embedded reusable computation in a form that a tiny adapter could access.

That assumption failed:

```text
fresh final OOD        28.0%
frozen-how final OOD   21.0%
```

The literature gives a coherent explanation: reusable components often appear only when the training regime **forces specialization/reuse** through compositional curricula, routing pressure, competition, predictive structure, low-rank componentization, or explicit task inference.

**Revised synthesis:**

> Do not train a generic processor first and search for modules afterward. Train the system under conditions where reusable computation is useful during acquisition.

**Confidence:** high.

---

### S3. There are four distinct problems that must not be collapsed into “modularity”

The research frontier separates:

```text
1. DECOMPOSITION
   What reusable computations exist?

2. BINDING / STATE
   What entities, variables and roles are those computations acting on?

3. ROUTING / SEQUENCING
   Which computation acts next, and where?

4. EXECUTION / PLASTICITY
   How is the selected computation executed repeatedly without rewriting everything else?
```

A model can succeed at one and fail at another.

Our previous transfer experiment mostly tested whether useful decomposition already existed inside a shared processor. It did **not** independently test binding or routing.

**Current synthesis:**

> Future tests should isolate these variables rather than comparing vaguely “modular” versus “non-modular” architectures.

**Confidence:** very high.

---

### S4. The factor graph is currently our best candidate for the binding/state layer

The factor representation gave a step-change gain and naturally preserves:

- entities;
- relations;
- event/query roles;
- shared identity;
- local message paths.

Recent variable-binding work shows that even generic neural architectures can learn addressable binding mechanisms, but our factor representation already supplies an explicit relational scaffold that has paid rent experimentally.

**Current synthesis:**

> For the next gate, hold the factor-state representation fixed. Do not change representation and execution simultaneously.

This lets us ask whether the failure lives in the processor/routing layer.

**Confidence:** high.

---

### S5. Routing is now the strongest new candidate bottleneck

The research refresh changed this substantially.

Multiple independent lines report that successful composition depends not just on having reusable pieces but on learning **which piece to use, on which state, in which order**.

That matches our failure pattern:

```text
96% IID
40.5% OOD
```

A shared processor can memorize/fit the composed task, but it does not necessarily learn a reusable execution sequence.

**Current synthesis:**

> The next core should explicitly represent an execution path rather than forcing one processor to implicitly emulate every operation.

**Confidence:** medium-high.

---

### S6. Recurrent depth remains useful, but as an executor

Our own depth probe:

```text
1 step   38.1%
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
```

External work also supports iterative execution, but the strongest recent OOD results combine recurrence with structured latent state, algorithmic supervision, task inference, or error correction.

**Current synthesis:**

> Recurrence is a clock/execution resource. The interesting question is **what operation is repeated or selected at each step**, not whether recurrence exists.

**Confidence:** high.

---

### S7. Global full fine-tuning is incompatible with the developmental goal

Our transfer result:

```text
old-task OOD before transfer   69.7%
old-task OOD after transfer     7.1%
loss                           62.6 points
```

This is decisive.

A developing agent cannot use global full-network adaptation as its default way to add a skill.

The external literature's modular, task-inference, local-component and parameter-isolation mechanisms all attack this same problem from different directions.

**Current synthesis:**

> Long-lived capability should reside in reusable components whose selection/composition can change faster than the components themselves.

**Confidence:** very high.

---

### S8. The strongest current architecture possibility is now a four-layer cognitive loop

Not a final architecture — a research hypothesis:

```text
STRUCTURED STATE / BINDINGS
(factor/entity graph)
          ↓
CONTROL / TASK INFERENCE
(what needs to happen?)
          ↓
ROUTER / SEQUENCER
(which learned operation acts next?)
          ↓
OPERATOR BANK
(reusable learned transformations)
          ↓
ITERATIVE EXECUTION
(update state and repeat)
          ↺
```

The operators may be:

- small message-passing networks;
- recurrent dynamical motifs;
- low-rank learned transformations;
- specialized subnetworks;
- other bounded learned functions.

They do **not** need to be symbolic rules.

The defining property is:

> an operation remains individually addressable enough to be reused in a novel execution sequence without globally rewriting the network.

**Confidence:** medium.

---

## What changed over the project

### Stage A — developmental recurrent ecology

Early experiments showed that sparse execution, shallow recurrence, specialization and local developmental structure can matter.

**Revision:** keep those mechanisms as options; do not force the whole agent into one cell ecology.

### Stage B — language separated from cognition

Different architectures won perception and production.

**Revision:** language organs and cognition may be separate learned systems.

### Stage C — relational organization produced the first large cognitive jump

Factor organization massively beat a flat core.

**Revision:** representational inductive bias became a primary architectural variable.

### Stage D — more thought helped, then saturated

Repeated computation unlocked some capabilities but mostly saturated around four steps.

**Revision:** recurrence is conditional compute, not general intelligence by itself.

### Stage E — shared-core transfer failed

The shared processor showed modest transfer, weak zero-shot composition, poor OOD extrapolation and catastrophic forgetting.

**Old hypothesis weakened:**

> ordinary multitask learning may create a hidden general HOW that can be frozen and cheaply redeployed.

**Revised hypothesis:**

> reusable computation probably needs to be made identifiable **during training**, and composition requires learned binding/routing rather than a tiny adapter over a generic frozen processor.

### Stage F — 2026-09-29 research refresh

The literature review split the vague idea of “modularity” into four independently testable mechanisms:

```text
decomposition
binding/state
routing/sequencing
execution/plasticity
```

It also elevated two constraints:

- training coverage/distribution can determine whether apparent composition is genuine;
- successful modularity requires functional specialization, not just structural separation.

**Revision:**

> The next experiment should hold state representation fixed and isolate whether explicit reusable operators + sequencing solve the failure.

---

## Next experimental hypothesis

### Hypothesis H1 — explicit reusable operators can beat a shared processor on unseen composition

Hold constant:

- factor/entity state representation;
- task families;
- parameter budget as closely as practical;
- training/evaluation budgets.

Change only the execution organization.

#### Baseline A — shared factor processor

Current Cognitive Core v0 style:

```text
state → same processor → state → same processor → ...
```

#### Diagnostic B — oracle-routed operator bank

Use several learned operator modules, but provide the correct operator identity/sequence during training **and evaluation**.

Purpose:

> establish whether explicit decomposition has enough representational/execution capacity to solve the held-out compositions at all.

This is an **upper-bound diagnostic**, not a candidate final agent.

#### Candidate C — learned-routed operator bank

Same learned operators, but the router/sequencer must infer the next operator from task/state context.

Purpose:

> test whether routing can generalize to withheld operation sequences.

### Why use an oracle arm?

Because otherwise a failure is ambiguous:

```text
operator architecture failed
OR
router failed
OR
operators never specialized
```

The oracle arm separates those.

If B cannot produce a large gain, stop. There is little reason to invest in automatic module discovery/routing.

If B succeeds but C fails, routing is the bottleneck.

If B and C succeed, we have earned the next test: **remove explicit operator supervision and ask whether specialization can emerge automatically**.

---

## Training/evaluation design

Train on primitive operations plus selected compositions.

Withhold:

1. specific operator combinations;
2. longer sequence lengths;
3. some role/entity permutations.

Evaluate separately:

```text
IID known compositions
OOD unseen combinations
OOD longer depth
OOD binding permutations
old-task retention
adaptation cost for one new operator
```

The benchmark must prevent trivial coverage leakage.

---

## High-leverage gate

The candidate does **not** survive for a small positive result.

Strong evidence would be at least one of:

- ~20+ OOD points over the shared factor baseline;
- strong unseen composition at near-IID accuracy;
- several-fold fewer updates for a new composition;
- near-zero adaptation for a novel sequence of known operators;
- adding one new operator without materially degrading old ones.

### Kill conditions

Stop the branch if:

- oracle operator decomposition barely beats the shared core;
- learned routing collapses to memorized sequence templates;
- performance disappears under longer composition depth;
- binding permutations break the model;
- routing overhead erases the capability/efficiency gain.

---

## If H1 passes

Only then test **automatic operator discovery**.

Candidate training signals from the literature:

- competition / winner-take-most allocation;
- modular routing pressure;
- predictive/self-supervised dynamics;
- compositional meta-training;
- compound examples containing reusable pieces;
- slow operator weights + faster routing/context learning.

The key question becomes:

> Can the system discover the operator vocabulary itself instead of being told what the reusable pieces are?

---

## Research-to-build promotion rule

```text
EXTERNAL FINDING
→ SYNTHESIS / POSSIBILITY
→ EXPERIMENTAL HYPOTHESIS
→ SURVIVING BUILD DECISION
```

FINDINGS owns external science.

This document owns synthesis and experimental hypotheses.

`AGENT_CURRENT.md` changes only after experimental survival.

---

## Evolution log

### 2026-09-29 — after Cognitive Transfer v0

**Prior synthesis:** a shared multitask factor processor might contain reusable computation accessible by cheap adaptation.

**Prediction:** frozen-HOW adaptation should substantially beat learning task 6 from scratch.

**Result:** frozen-HOW underperformed fresh training; ordinary fine-tuning gave only modest OOD transfer and destroyed old-task performance.

**What survived:** factor state organization; recurrence as useful compute.

**What failed:** hidden reusable-HOW assumption; global fine-tuning as developmental mechanism.

**Revised synthesis:** reusable computation must likely become more identifiable/specialized during training.

### 2026-09-29 — after research phase 1

**Prior synthesis:** build an operator-composition core.

**New evidence:** modularity itself is insufficient; literature separates specialization, binding, routing, training coverage and iterative execution. Routing and task inference repeatedly appear as explicit mechanisms.

**What survived:** operator-system direction.

**What changed:** the next experiment must not confound operator representation with routing or automatic module discovery.

**Revised synthesis:** first establish an oracle-decomposition upper bound, then test learned routing, then — only if both pass — test automatic discovery.

**Next discriminating question:**

> Does explicit operator decomposition produce a large compositional-OOD gain over the current shared factor processor, and if so, can a learned router recover most of that gain?

---

## Current synthesis frontier

The present best hypothesis is:

> A general cognitive core may be better modeled as **structured bound state + reusable learned operations + learned routing/sequencing + iterative execution**, with slower plasticity in operations than in control/routing.

The immediate goal is **not** to believe this architecture.

The immediate goal is to build the cheapest experiment capable of killing it.
