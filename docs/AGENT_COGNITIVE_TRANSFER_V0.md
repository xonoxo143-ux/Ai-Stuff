# Agent Cognitive Transfer v0

**Date:** 2026-09-29  
**Status:** RESULT / HIGH-LEVERAGE TRANSFER GATE FAILED  
**Question:** did Cognitive Core v0 learn reusable computation, or merely five tasks at once?

## Literature gate

Before implementation, the transfer question was searched under:

- meta-learning / learning-to-learn;
- compositional meta-learning;
- probabilistic task inference;
- reusable computation;
- what/how decomposition;
- neural algorithmic transfer.

The closest recent precedents are:

- Shan, Minni & Duncker, NeurIPS 2025: **Separating the what and how of compositional computation to enable reuse and continual learning**. Their two-system architecture separates task/context inference ("what") from reusable low-rank recurrent computation ("how") and reports forward/backward transfer and fast generalization to unseen compositions.
- Bakermans et al. 2025: **Compositional meta-learning through probabilistic task inference**. New tasks are represented as combinations of reusable computations and can sometimes be inferred from very few examples rather than relearned through full parameter updates.
- Ibarz et al. 2022: **A Generalist Neural Algorithmic Learner**. A shared graph processor can incorporate multiple algorithmic skills, but multitask success alone is not evidence of fast transfer.

This experiment borrows the **separation principle**, not those task sets.

## Sixth family

The held-out family composes three computations that the existing benchmark trained separately:

\`\`\`text
directed relation traversal
        ↓
associative memory lookup
        ↓
inferred rule transformation
        ↓
answer
\`\`\`

Training task-6 examples use relation chains of length 1–2.

OOD task-6 examples use chains of length 3–5 and slightly more rule evidence.

The relation, memory and mapping row types/operators are the same ones already used by the original families. What is new is their **composition inside one problem**.

## Three arms

### A — fresh

Random factor core learns the sixth family from scratch.

### B — ordinary transfer

Factor core first trains on the original five families, then all parameters fine-tune on task 6.

### C — frozen-how transfer

The same pretrained factor processor is frozen.

Only a tiny task context/readout adapter is trained:

- one task-context vector;
- rank-8 query adapter;
- scalar gates over existing message pathways.

This is a deliberately cheap test of the "what/how" idea.

If C cannot exploit the frozen core, do not build a more elaborate modular system unless B first shows a large transfer signal.

## Learning curve

Measure OOD after:

\`\`\`text
0, 8, 16, 32, 64, 128, 256, 512, 1024 updates
\`\`\`

Also measure:

- zero-shot task-6 OOD;
- old-task OOD before transfer;
- old-task OOD after ordinary full fine-tuning;
- trainable parameter count for frozen-how.

## High-leverage gate

The core does not earn another tuning cycle for a small advantage.

Heuristic interpretation:

\`\`\`text
fresh 1000 updates → transfer 800
low leverage

fresh 1000 → transfer ~250
interesting

fresh 1000 → transfer ~50
major

strong zero-shot / near-zero-shot composition
major
\`\`\`

The exact threshold is secondary to the ratio and final OOD capability.

## Failure meanings

\`\`\`text
B ≈ A
→ multitask pretraining did not create useful transferable cognition

B >> A, C ≈ A
→ useful transfer exists, but it is distributed and requires broad plasticity

C >> A
→ frozen reusable "how" machinery exists and small task/context adaptation can redeploy it

all arms fail OOD
→ task/representation or core organization is inadequate; do not infer anything about transfer
\`\`\`

## Result — three seeds

Workflow run: `36628203554`  
Artifact: `Agent-Cognitive-Transfer-V0`

Mean results:

```text
                                 step 0 OOD   step 1024 IID   step 1024 OOD
fresh core                            5.5%           55.5%           28.0%
ordinary pretrained transfer          9.0%           96.0%           40.5%
frozen-how adapter                   10.3%           23.3%           21.0%
```

Additional measurements:

```text
mean pretrained old-task OOD              69.7%
mean old-task OOD after ordinary transfer  7.1%
mean old-task delta                       -62.6 points
mean zero-shot task-6 OOD                  8.7%
frozen-how trainable parameters            1,095
```

Only one ordinary-transfer seed reached 50% OOD, at 512 updates. No arm reached 70% OOD.

## Interpretation

The high-leverage gate is **not passed**.

Ordinary pretraining does help task-6 fitting:

```text
fresh final OOD      28.0%
ordinary transfer    40.5%
```

but the gain is modest relative to the project's threshold, highly incomplete on OOD composition, and purchased with catastrophic forgetting of the original five families.

The frozen-how arm does not show reusable computation that a tiny context/readout adapter can redeploy. Its final OOD is below the fresh baseline.

The strongest diagnostic is the IID/OOD split:

```text
ordinary transfer IID   96.0%
ordinary transfer OOD   40.5%
```

So the current core can learn the new composed training family but does not robustly extrapolate that composition to longer relation depth.

This means the experiment cannot support the claim that Cognitive Core v0 contains a generally reusable frozen "how" substrate. It also means ordinary full fine-tuning is not an acceptable lifelong-learning mechanism.

## Decision

Do **not** tune Cognitive Core v0 for incremental transfer gains.

Do **not** build a more elaborate frozen-how adapter on the assumption that this result was nearly successful.

Keep the factor-graph representation as a useful baseline because its earlier flat→factor gain remains large, but demote the current shared processor as a candidate for general compositional transfer.

## Next move

Return to the literature gate before another build.

The next high-information question is:

> What representation/execution mechanism produces strong **compositional OOD generalization** when already-learned operations must be chained in a new way?

Search especially:

- systematic compositional generalization;
- neural algorithmic reasoning and processor transfer;
- modular neural networks / modular meta-learning;
- program induction / learned execution;
- variable binding and role-filler representations;
- task/operator graphs;
- routing or sequencing of learned operators.

The next experiment should discriminate a materially stronger compositional mechanism from the current factor-core baseline. It should not be another small adapter or recurrence-tuning cycle.
