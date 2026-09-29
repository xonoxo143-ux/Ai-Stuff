# Agent Research Synthesis — Integrated Possibility Model

**Date:** 2026-09-29  
**Status:** LIVING RESEARCH MODULE — PROJECT INFERENCE  
**Pair:** `AGENT_RESEARCH_FINDINGS.md`

## Purpose

This file answers a different question from FINDINGS:

> **When the external findings are linked together with our own experiments, what architecture or mechanism appears possible — and how does that belief change when we test it?**

This is allowed to hypothesize.

It must **never disguise synthesis as established science**.

Inputs:

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

## Current integrated model

### S1. Reusable computation probably needs to be learned as reusable computation

The external literature repeatedly succeeds when training encourages decomposition, reusable mechanisms, task inference, or routing.

Our own transfer experiment did **not** recover strong reusable computation simply by:

```text
train one shared core on five tasks
→ freeze it
→ add a tiny adapter
→ expect unseen composition
```

That suggests a stronger hypothesis:

> reusable operations may need to become identifiable/specialized **during learning**, rather than being extracted after ordinary multitask training.

**Confidence:** medium-high.

### S2. Factorized relational representation is useful, but the current shared processor is not enough

Our flat→factor change produced the largest cognitive-core gain so far:

```text
23.9% OOD → 59.8% OOD
```

So explicit relational organization earned its place.

But Cognitive Transfer v0 showed:

```text
ordinary transfer task-6 IID   96.0%
ordinary transfer task-6 OOD   40.5%
```

The system can fit the new composition but does not reliably extrapolate it.

Working synthesis:

> keep explicit relational/entity structure, but do not assume one undifferentiated message-passing processor will become a compositional reasoning engine by scale or fine-tuning alone.

**Confidence:** high.

### S3. Recurrent depth is an execution resource, not the missing architecture

Our core improved strongly from one to four recurrent steps and then saturated.

External work also shows useful reusable recurrent dynamics.

Therefore recurrence remains valuable as:

- iterative execution;
- working-state evolution;
- variable compute;
- a substrate in which reusable motifs may live.

But recurrence alone did not solve transfer or systematic composition.

**Confidence:** high.

### S4. Global full fine-tuning is incompatible with the developmental goal

Cognitive Transfer v0 reduced old-task OOD from about:

```text
69.7% → 7.1%
```

while adapting to task 6.

That makes ordinary whole-core fine-tuning unacceptable as the main mechanism for a continually developing agent.

External modular/continual-learning work independently points toward local modules, task-conditioned composition, parameter isolation, or inference over reusable pieces.

**Confidence:** very high.

### S5. The strongest current possibility is an operator system, not another monolithic core

Linking the evidence produces this candidate:

```text
structured world / entity state
          ↓
task/context inference
          ↓
learned routing / sequencing
          ↓
reusable learned operators
          ↓
iterative execution / working state
          ↓
result
```

The operators do not need to be symbolic rules. They may be:

- small recurrent dynamical motifs;
- learned message-passing functions;
- low-rank components;
- specialized neural modules;
- other bounded learned transformations.

The critical property is not their implementation. It is that **the same operation can be selected and recomposed in a new context without rewriting the entire system**.

**Confidence:** medium. This is a synthesis, not yet a project result.

## What changed over our tests

### Stage A — recurrent developmental ecology

Earlier work suggested that repeated local computation, specialization, sparse execution, and developmental structure could matter.

Useful pieces survived, but no evidence justified making the entire chatbot one homogeneous recurrent-cell ecology.

**Revision:** preserve local/developmental ideas; drop architecture religion.

### Stage B — language organs separated from cognition

From-scratch language tests showed different architectures winning perception and production.

**Revision:** language interface and cognition need not share one architecture.

### Stage C — factor organization produced a step change

Flat representation failed badly relative to factorized relational organization.

**Revision:** internal organization/inductive bias became a primary axis.

### Stage D — recurrent thought helped, then saturated

More repeated execution unlocked capabilities, especially memory, but gains largely saturated near four steps.

**Revision:** allocate thought when useful; do not confuse deeper recurrence with better general reasoning.

### Stage E — shared-core transfer gate failed the high-leverage test

Ordinary transfer improved task-6 OOD from 28.0% to 40.5%, but:

- zero-shot transfer was weak;
- frozen-how adaptation fell below fresh training;
- OOD remained poor despite 96% IID;
- full fine-tuning catastrophically forgot old tasks.

**Old synthesis weakened:** “a shared multitask processor may already contain a frozen general HOW that a tiny adapter can expose.”

**New synthesis:** reusable computation likely has to be **formed and addressed explicitly during training**, and composition/routing itself must be learned and tested OOD.

## Current proposed next discriminating experiment

Do not build a large new agent yet.

Compare the current factor core against a small **operator-composition core** designed to test the synthesis directly.

The candidate should separate:

```text
representation/state
operator bank
router/sequencer
execution loop
```

Training should expose primitive operations and some compositions while withholding other compositions.

The decisive tests are:

1. unseen operator combinations;
2. longer composition depth than training;
3. transfer learning speed;
4. old-skill retention;
5. ability to add a new operator without globally rewriting old ones.

### Kill condition

If explicit learned operators/routing do not produce a **large** OOD or transfer advantage over the factor-core baseline, do not keep polishing modularity because it is fashionable.

### Success condition

A result becomes architecturally important if it gives something like:

- ~20+ OOD points;
- several-fold reduction in adaptation updates;
- strong unseen composition with little/no parameter update;
- substantially better retention while adding capabilities;
- a qualitatively absent capability.

## Research-to-build promotion rule

A research idea moves through four states:

```text
EXTERNAL FINDING
→ SYNTHESIS / POSSIBILITY
→ EXPERIMENTAL HYPOTHESIS
→ SURVIVING BUILD DECISION
```

FINDINGS owns state 1.

This document owns states 2–3.

`AGENT_CURRENT.md` owns state 4.

This prevents an exciting paper, or an exciting inference, from silently becoming architecture.

## Evolution log format

When a meaningful test changes the model, append one compact record:

```text
DATE / TEST
Prior synthesis:
Prediction:
Result:
What survived:
What failed:
Revised synthesis:
Next discriminating question:
```

Do not erase failed reasoning. Compress it after it has taught us something.

## Current synthesis frontier

The present best hypothesis is:

> General compositional reuse may require learned **operations that remain individually addressable**, plus learned **routing/sequencing** that can recombine them over structured state, while plasticity is localized enough to avoid destroying old operations.

The next job of research is to find the strongest existing implementations and failure modes of that idea.

The next job of experimentation is to try to kill it cheaply.
