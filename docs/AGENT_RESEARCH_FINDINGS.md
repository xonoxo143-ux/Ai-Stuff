# Agent Research Findings — Scientific Frontier

**Date:** 2026-09-29  
**Status:** LIVING RESEARCH MODULE — EXTERNAL EVIDENCE  
**Pair:** `AGENT_RESEARCH_SYNTHESIS.md`

## Purpose

This file answers one question:

> **What does the external scientific literature currently support that is relevant to building this agent?**

It does **not** contain our architecture preferences, project conclusions, or speculation. Those belong in `AGENT_RESEARCH_SYNTHESIS.md`.

A dedicated research chat should normally load **this file and SYNTHESIS together**.

## Update rule

For each research question:

1. search exact and neighboring terminology;
2. prefer recent primary work plus canonical precedent;
3. record effect direction, conditions, and failure modes;
4. distinguish demonstrated results from author interpretation;
5. update the current frontier rather than accumulating redundant summaries;
6. keep a short change log when the literature changes materially.

The target is not “all papers.” It is the **best current map of what is known, what is uncertain, and what remains open**.

## Current frontier

### F1. Systematic compositional generalization remains a real difficulty

Modern neural systems can fit familiar task distributions extremely well while failing to recombine known operations under new compositions or distribution shifts.

A growing line of work improves systematicity by making compositional structure part of the learning problem rather than expecting ordinary end-to-end training to discover it automatically.

**Current status:** strong evidence that training objective and representational organization matter; no single generally accepted solution across domains.

### F2. Modularity is promising, but modules do not automatically specialize usefully

Modular deep learning separates computation, routing, and often parameter updates. Reviews and controlled experiments report advantages for transfer, reduced interference, and systematic generalization in some settings.

However, merely imposing modules does not guarantee that learned components align with reusable task structure. Successful compositional generalization depends on discovering or inducing the right decomposition and routing.

**Current status:** modularity is a serious mechanism class, not a solved recipe.

### F3. Reusable computation can emerge inside recurrent networks

Multitask recurrent networks can develop recurring **dynamical motifs** that implement computations reused across tasks. In controlled experiments, these motifs can support transfer and show localized causal roles under lesions.

This provides evidence that reusable computation need not be symbolic or hand-coded; it can exist as learned dynamics.

**Current status:** demonstrated in controlled multitask settings; open question how reliably such motifs can be discovered, addressed, and recomposed in broader agents.

### F4. Separating “what computation?” from “how to perform it” can support fast reuse

Recent compositional meta-learning work explicitly separates task/context inference from reusable computation.

Two related approaches show that:

- structured task inference can identify combinations of reusable computations with very few examples and sometimes without parameter updates;
- a separate context/"what" system can compose reusable low-rank recurrent components in a "how" system, supporting forward transfer, continual learning, and unseen task compositions in controlled families.

**Current status:** compelling controlled evidence for separation of task inference from execution; generality to open-ended tasks is not established.

### F5. Competition plus composition can encourage independent mechanisms

Work on modular world models shows that competitive learning signals can encourage mechanisms to specialize, after which learned mechanisms can be recomposed in new environments with improved adaptation efficiency.

**Current status:** evidence that *how modules are trained* may matter as much as having modules.

### F6. The frontier is increasingly about learned decomposition + learned routing

Across modular learning, compositional meta-learning, world models, and recurrent dynamics, a common pattern is emerging:

```text
discover reusable computation
        +
represent task/context structure
        +
select / route / sequence reusable pieces
        +
limit destructive global updates
```

The literature does **not** establish that this combination is sufficient for general intelligence. It does make it a stronger research direction than expecting generic full-network fine-tuning to yield systematic reuse by itself.

## Important limitations of the evidence

Most positive results above use controlled task families where:

- primitive operations are repeated across tasks;
- compositional structure exists by construction;
- train/test distributions are carefully defined;
- task complexity is far below open-ended conversation and reasoning.

Therefore:

> success on these benchmarks is evidence about mechanisms, not evidence that the complete agent problem is solved.

The key unresolved question is whether useful decompositions can be learned **without already knowing the correct task vocabulary**.

## Current open research questions

1. How can reusable operations be discovered rather than specified?
2. How should routing/sequencing be learned for unseen compositions?
3. What representations preserve variable identity and role binding across compositions?
4. Can new operations be added without global catastrophic forgetting?
5. Can modular execution remain efficient rather than becoming routing overhead?
6. Which mechanisms extrapolate to greater depth/length rather than only new IID combinations?
7. How can these mechanisms connect to language perception and production without turning language itself into the hidden cognitive core?

## Key current references

1. Laura N. Driscoll, Krishna V. Shenoy, David Sussillo (2024), *Nature Neuroscience*, 78 citations at refresh: **Flexible multitask computation in recurrent networks utilizes shared dynamical motifs**  
   https://consensus.app/papers/flexible-multitask-computation-in-recurrent-networks-driscoll-shenoy/efaaebd2282c51979bce6983d67c6dc3/?utm_source=chatgpt

2. Jonas Pfeiffer, Sebastian Ruder, Ivan Vulic, E. Ponti (2023), arXiv, 119 citations at refresh: **Modular Deep Learning**  
   https://consensus.app/papers/modular-deep-learning-pfeiffer-ruder/a8b57a21263d5675bf4ca34322404bae/?utm_source=chatgpt

3. Haozhe Shan, Minni Sun, Lea Duncker (2025), arXiv, 10 citations at refresh: **Separating the what and how of compositional computation to enable reuse and continual learning**  
   https://consensus.app/papers/separating-the-what-and-how-of-compositional-computation-shan-sun/f181b7774aa557baa339bb36a6b9fd4f/?utm_source=chatgpt

4. Simon Schug et al. (2023), arXiv, 31 citations at refresh: **Discovering modular solutions that generalize compositionally**  
   https://consensus.app/papers/discovering-modular-solutions-that-generalize-schug-kobayashi/b84919576d4255c6b3cf9408ed75fad7/?utm_source=chatgpt

5. Anson Lei, Frederik Nolte, B. Schölkopf, Ingmar Posner (2024), arXiv, 4 citations at refresh: **Compete and Compose: Learning Independent Mechanisms for Modular World Models**  
   https://consensus.app/papers/compete-and-compose-learning-independent-mechanisms-for-lei-nolte/02f41a52eaa555aea8a7bb99a52eeaa3/?utm_source=chatgpt

6. Jacob J. W. Bakermans, Pablo Tano, Reidar Riveland, Charles Findling, Alexandre Pouget (2025), arXiv, 5 citations at refresh: **Compositional meta-learning through probabilistic task inference**  
   https://consensus.app/papers/compositional-metalearning-through-probabilistic-task-bakermans-tano/56ca958841e95f37a3a8a1077f12d251/?utm_source=chatgpt

## Search vocabulary

Keep expanding this as terminology evolves:

- systematic compositional generalization
- modular deep learning
- modular meta-learning
- compositional meta-learning
- neural algorithmic reasoning
- processor transfer
- learned routing
- independent mechanisms
- dynamical motifs
- variable binding
- role-filler representation
- task inference
- program induction
- continual compositional learning
- adaptive computation / recurrent depth

## Change log

### 2026-09-29 — initial modular research frontier

Migrated the useful role of the old terminology map into a stricter evidence-only document and refreshed the active compositional-generalization frontier with academic search.

Future entries should record only **material changes in what the external evidence supports**.
