# Agent Cognitive Core v0

**Date:** 2026-09-29  
**Status:** REPLICATED BASELINE / TRANSFER GATE NEXT  
**Workflow:** \`36612931106\`

## Goal

Test whether one learned non-language processor can perform multiple kinds of cognition and generalize beyond training sizes/combinations.

No pretrained LLM is used.

\`\`\`text
language perception
→ non-language state
→ COGNITIVE CORE
→ new non-language state
→ language production
\`\`\`

## Shared representation

Every family uses the same slot schema and bounded answer vocabulary.

Families:

1. transitive directed relations;
2. ordered mutable state;
3. graph reachability;
4. rule induction;
5. associative key/value memory.

IID/OOD generators have exact oracle checks.

## Why v0 uses a factor graph

Earlier local formulations failed or were inefficient:

- dense all-pairs slot MLP: too slow for its value;
- recurrent all-slot attention: transitive relation specialist stayed at chance;
- same-symbol slot adjacency: still stayed at chance.

The useful change was to make shared entity/symbol identity explicit and persistent.

Current organization:

\`\`\`text
fact / event / query slots
        ↕ role-typed messages
persistent symbol/entity nodes
\`\`\`

The same weights are reused across families and recurrent thought steps.

## Rigorous three-seed result

400 mixed updates:

\`\`\`text
model                         IID mean   OOD mean   train time
flat MLP                        40.5%      23.9%       3.7 s
factor one-pass                 77.3%      59.8%       7.6 s
factor recurrent                80.6%      64.6%      26.0 s
factor recurrent, no reinject   81.6%      65.8%      25.6 s
\`\`\`

### What matters

The large architectural gain is:

\`\`\`text
flat 23.9% OOD
→ factor one-pass 59.8% OOD
\`\`\`

This is the main reason the factor graph survives.

The average recurrence gain:

\`\`\`text
59.8% → 64.6%
\`\`\`

is real but too small relative to ~3.4× training time to justify a long recurrence-tuning campaign.

Input reinjection did not help and is demoted.

## Thought depth

Same trained recurrent model:

\`\`\`text
depth   OOD mean
1       38.1%
2       51.2%
4       62.0%
6       63.0%
8       62.8%
\`\`\`

Memory:

\`\`\`text
1       10.2%
2       52.0%
4       99.6%
6      100.0%
\`\`\`

So recurrent computation can unlock a capability, but extra thought saturates.

Current rule:

> pay for additional thought only until it stops buying capability.

This question overlaps strongly with the literature on recurrent depth, looped networks/Transformers, iterative refinement and adaptive computation. Future work should begin from that literature rather than reproving the basic effect.

## Specialist ceilings

\`\`\`text
family      specialist OOD
relation        98.5%
rule            97.3%
memory         100.0%
graph           45.5%
state           20.5%
\`\`\`

Approximate shared recurrent result:

\`\`\`text
relation        88.7%
rule            65.8%
memory          99.7%
graph           46.2%
state           22.8%
\`\`\`

The largest actionable shared-vs-specialist gap is rule induction.

Graph/state are currently poor targets for shared-core optimization because the specialists also fail to extrapolate strongly.

## High-leverage interpretation

Worth keeping:

- factor-graph entity organization;
- a bounded amount of recurrent thought where it unlocks capability.

Not worth a dedicated optimization campaign right now:

- input reinjection;
- 6/8 steps versus ~4;
- squeezing a few extra mean OOD points from recurrent tuning.

## Next experiment: transfer, not tuning

The next question:

> Did the shared core learn reusable computation, or merely learn five tasks at once?

Use a genuinely held-out sixth family and compare:

### A — fresh
Random core learns task 6 from scratch.

### B — ordinary transfer
Current shared factor core is pretrained on the existing families, then adapted to task 6.

### C — explicit reusable-computation baseline
A mechanism that separates/recomposes **what computation is required** from **how computation is implemented**.

Measure:

- zero-shot accuracy;
- OOD accuracy;
- examples/updates to fixed target;
- retained old-task performance;
- wall-clock adaptation cost.

The desired result is a step change in learning efficiency, not a small fine-tuning advantage.

Working leverage heuristic:

\`\`\`text
2000 → 1700 examples   low leverage
2000 → 500             interesting
2000 → 100             major
strong zero/few-shot   major
\`\`\`

## Relevant research vocabulary

Before building the transfer gate, search:

- meta-learning / learning-to-learn;
- compositional meta-learning;
- modular meta-learning;
- reusable computation;
- skill composition;
- continual compositional learning;
- low-rank task composition;
- task inference;
- systematic generalization.

See \`AGENT_RESEARCH_TERMINOLOGY_MAP.md\`.

## Kill condition

If ordinary pretraining or explicit compositional machinery provides only a small sample-efficiency gain on a genuinely new family, do not keep scaling this core on the assumption that general intelligence will emerge from more of the same.
