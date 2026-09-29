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

## Strategic scope correction — whole-agent objective

The compositional-OOD work produced useful causal information, but it began to dominate the research agenda beyond its role in the actual project.

The project target is not:

> maximize performance on synthetic compositional reasoning.

It is:

> build a self-contained, from-scratch conversational agent that can move across topics, remember, reason, retrieve knowledge, and generate each response from its own learned machinery.

Current whole-agent audit shows larger missing capabilities than the latest cognition benchmark:

1. the from-scratch perception/cognition/production stack is not yet closed into the runtime;
2. the language/semantic interface is still bounded/toy-scale;
3. broad knowledge acquisition/retrieval is not integrated with the homegrown language system;
4. multi-turn topic switching and thread resumption are not yet demonstrated by the homegrown stack.

Therefore:

> compositional generalization remains an important diagnostic stress test, but it is **not currently the primary research target**.

The research loop should now prefer questions whose answers plausibly unlock the whole conversational system: from-scratch language/state interfaces, memory-conditioned generation, broad knowledge access without a pretrained LLM, and integrated multi-turn control.

Research on isolated cognition should regain priority only when a whole-agent failure points back to it.

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

### S5. Routing was not the immediate bottleneck we thought it might be

The research refresh elevated routing because many successful compositional systems explicitly select and sequence reusable computation.

Operator Routing Gate v0 then supplied the correct semantic decomposition and route directly.

Result:

```text
shared factor core      43.7% IID   27.0% OOD
oracle operator core    95.8% IID   41.2% OOD
```

The oracle route massively improved fitting but only added **14.2 OOD points**, below the high-leverage gate.

**Revised synthesis:**

> Routing matters in the general problem, but it is not the next bottleneck in this benchmark. Even with the route solved, the learned operators do not extrapolate strongly to longer execution depth.

The immediate question becomes whether the operation learned on short chains is an actual reusable algorithm or a short-horizon approximation.

**Confidence:** high.

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

### S8. The four-layer loop remains a possibility, but the operator layer is now the weak link

The broad decomposition remains conceptually useful:

```text
STRUCTURED STATE / BINDINGS
          ↓
CONTROL / TASK INFERENCE
          ↓
ROUTER / SEQUENCER
          ↓
REUSABLE LEARNED OPERATIONS
          ↓
ITERATIVE EXECUTION
          ↺
```

But Operator Routing Gate v0 prevents us from treating this as the next architecture to build.

Supplying the operator boundaries and sequence produced near-solved IID fitting while OOD stayed weak. Therefore the unresolved issue is more basic:

> Can a learned operation preserve the same semantics when it must execute for more steps, on longer paths, or under new bindings?

Until that is demonstrated, an operator bank risks becoming a collection of specialized short-horizon functions rather than reusable cognition.

**Confidence in the broad loop:** medium-low.

**Confidence that depth-generalizing operator semantics are the next research target:** high.

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

## Completed hypothesis H1 — oracle operator decomposition

H1 asked whether explicit reusable operators could produce a large OOD advantage over a shared processor when the route was supplied.

Rigorous three-seed result:

```text
                         IID      OOD
shared factor core      43.7%    27.0%
oracle operator core    95.8%    41.2%

OOD delta                       +14.2 points
required gate                   +20.0 points
```

**H1 failed the high-leverage gate.**

The architecture clearly improves optimization/sample acquisition on the training distribution, but it does not solve depth extrapolation.

Per the precommitted decision rule:

- learned routing is not built next;
- automatic operator discovery is not built next;
- the positive IID result is retained as evidence, not promoted into architecture.

## Next research hypothesis — depth-invariant learned operations

The next cycle returns to research before another build.

Working question:

> What mechanism makes a learned computation behave like the **same operation at depth 5 as at depth 1**, rather than learning a short-chain approximation?

Candidate mechanism families to research, not yet adopt:

- algorithmic alignment / neural algorithmic reasoning;
- recurrent processors trained on execution traces or intermediate invariants;
- stable variable/entity binding across repeated updates;
- equivariant or state-machine-like transition structure;
- training distributions that force length extrapolation rather than finite coverage;
- error-correcting / anchored latent execution.

The next experiment should change **one** of these while holding decomposition and route fixed, so the failure remains interpretable.
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

### 2026-09-29 — after Operator Routing Gate v0

**Prior synthesis:** explicit decomposition plus an oracle route should reveal whether routing/decomposition was the main obstacle to compositional OOD.

**Prediction:** if operatorization was the missing organization, the oracle arm should beat the shared core by at least 20 OOD points.

**Result:** oracle operators reached 95.8% IID but only 41.2% OOD versus 27.0% OOD for the shared core; +14.2 points, below gate.

**What survived:** explicit decomposition strongly improves learnability/fitting; factor state remains useful.

**What failed:** the claim that decomposition/routing is sufficient for strong compositional extrapolation.

**Revised synthesis:** the learned operation itself lacks robust depth/length invariance. Routing is demoted as the immediate bottleneck.

**Next discriminating question:** what training/representation constraint makes a learned operator execute an invariant rule over longer trajectories?

---
## Current synthesis frontier

The present best hypothesis is narrower than before:

> Structured state and modular control may still be useful, but **reusable cognition requires learned operations whose semantics remain stable across execution depth, path length, and binding changes**. Decomposition and routing cannot compensate for operators that only approximate short training trajectories.

The next job is research, not architecture expansion:

> identify the strongest demonstrated mechanisms for **depth/length-generalizing learned execution**, then design one cheap test that can distinguish a genuinely invariant operator from a short-horizon heuristic.
