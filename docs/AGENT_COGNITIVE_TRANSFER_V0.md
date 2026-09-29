# Agent Cognitive Transfer v0

**Date:** 2026-09-29  
**Status:** ACTIVE EXPERIMENT  
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

## Next move

Only if transfer is large:

1. localize what transferred;
2. stress symbol/encoding/depth changes;
3. test old-task retention;
4. connect the surviving mechanism back to language for turn-to-turn task switching.
