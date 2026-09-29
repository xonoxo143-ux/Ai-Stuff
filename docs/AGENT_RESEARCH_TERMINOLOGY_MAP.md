# Agent Research Terminology Map

**Date:** 2026-09-29  
**Status:** CURRENT RESEARCH GUIDE  
**Purpose:** translate our informal questions into neighboring research vocabulary before expensive experiments.

## Rule

Before a substantial new branch:

\`\`\`text
our question
→ exact phrasing
→ adjacent terminology
→ mechanism names
→ newest relevant work
→ canonical precedent
→ negative results / ablations
→ strongest baseline
→ unresolved experiment only
\`\`\`

Do not assume our wording is the wording used in the literature.

## 1. "Can the same brain think longer?"

Search:

- recurrent depth;
- depth recurrence;
- looped Transformers / looped networks;
- Universal Transformer;
- iterative refinement;
- adaptive computation time;
- learned halting / ponder;
- test-time compute scaling;
- recurrent inference.

Recent useful references:

- **DeepLoop: Depth Scaling for Looped Transformers** — arXiv:2607.13491. Studies stability/scaling when the same Transformer blocks are repeatedly reused across depth.
- **Adaptive Depth in Looped Transformers: Diagnosing Learned Halting Gates and Trajectory Readouts** — arXiv:2607.20519. Separates recurrent trajectory formation from exit/readout quality.
- **Looped SSMs: Depth-Recurrence and Input Reshaping for Time Series Classification** — arXiv:2605.16048. Shows depth recurrence is a distinct design axis from sequence recurrence.

Project implication:

Our 1→2→4-step gains are not a new category of phenomenon. The unresolved questions are **when extra thought is useful, how it should stop, and whether it transfers across capabilities**.

## 2. "Can previous skills make a new task dramatically faster to learn?"

Search:

- meta-learning;
- learning-to-learn;
- few-shot adaptation;
- forward transfer;
- compositional meta-learning;
- modular meta-learning;
- skill composition;
- continual compositional learning;
- reusable computation;
- task inference;
- systematic generalization.

Recent useful references:

- **Separating the what and how of compositional computation to enable reuse and continual learning** — arXiv:2510.20709. Uses a two-system view: infer *what* computation is required and reuse components implementing *how* to perform it; reports forward/backward transfer and fast generalization to unseen task compositions.
- **Compositional meta-learning through probabilistic task inference** — arXiv:2510.01858. Represents tasks as structured combinations of reusable computations and performs fast task inference from minimal examples.
- **Meta-Learning to Compositionally Generalize** — arXiv:2106.04252. Uses meta-learning objectives targeted at compositional OOD generalization.

Project implication:

The next transfer experiment should include an explicit reusable-computation/compositional baseline, not only "pretrained shared core vs fresh core."

## 3. "Can one processor solve many algorithmic/reasoning families?"

Search:

- neural algorithmic reasoning;
- generalist neural algorithmic reasoning;
- shared processor;
- algorithmic extrapolation;
- graph neural networks;
- processor transfer;
- size generalization;
- systematic extrapolation.

Useful precedent:

- **A Generalist Neural Algorithmic Learner** — arXiv:2209.11142. Studies one shared processor across diverse algorithms and emphasizes out-of-distribution/size generalization.

Project implication:

IID multitask accuracy is weak evidence. Depth/size/composition extrapolation and transfer are primary metrics.

## 4. "How should facts/entities connect internally?"

Search:

- factor graphs;
- message passing neural networks;
- graph networks;
- relational inductive bias;
- entity-centric representation;
- object-centric representation;
- hypergraphs;
- relational reasoning.

Project implication:

Our large flat→factor gain makes representational organization a high-leverage axis. Future alternatives should beat the factor baseline by a material amount rather than adding decorative complexity.

## 5. "How should internal memory survive while computation repeats?"

Search:

- recurrent memory;
- memory-augmented neural networks;
- fast weights;
- external memory;
- associative memory;
- state-space memory;
- test-time memory;
- working memory;
- gated memory.

Project implication:

Associative memory is already near ceiling in Cognitive Core v0. Do not optimize memory on the current toy task. Use harder memory problems only when they expose a meaningful failure in the integrated agent.

## 6. "How should the agent decide when to stop thinking?"

Search:

- adaptive computation time;
- learned halting;
- ponder cost;
- dynamic depth;
- early exit;
- confidence-based stopping;
- trajectory readout;
- test-time compute allocation.

Project implication:

Current v0 saturates near four steps. A stopping mechanism is only worth building if it saves substantial runtime while preserving capability on mixed-difficulty inputs.

## 7. "How can learning avoid destroying old skills?"

Search:

- continual learning;
- catastrophic forgetting;
- interference;
- parameter isolation;
- orthogonal gradients;
- modular continual learning;
- sparse plasticity;
- synaptic consolidation;
- gradient conflict;
- task-conditioned plasticity.

Project implication:

Our old result already rejects simple one-shot scalar cell importance predictors. Search for mechanisms operating at trajectory, component, routing, or task-composition level before returning to that branch.

## 8. Literature triage

For each question, record:

1. terminology aliases;
2. strongest recent mechanism;
3. canonical older mechanism;
4. reported effect size, not just direction;
5. compute/parameter cost;
6. failure modes;
7. whether the result transfers to our setting;
8. the smallest remaining unresolved experiment.

A literature result can save an experiment in two ways:

- it gives us a stronger mechanism to test;
- it shows that our planned experiment would only rediscover a well-established small effect.

Both count as progress.
