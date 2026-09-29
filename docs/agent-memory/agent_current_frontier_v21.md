# Agent Current Frontier

**Version:** 2.2  
**Date:** 2026-09-29  
**Role:** shortest current-state file. Update after every meaningful experiment cycle.

## Task

Build the intelligent conversational agent itself from scratch.

Pretrained LLMs are controls/reference systems, not the presumed cognitive core.

## Current stack

\`\`\`text
English / raw bytes
→ BiGRU perception
→ bounded non-language state
→ factor-graph cognitive core
→ bounded non-language state
→ GRU production
→ English / raw bytes
\`\`\`

Language and cognition remain separately replaceable only as experimental components of this same Agent project; the goal is the complete intelligent system.

## Durable language results

### Production
Three-seed bounded TinyStories replication, 800 updates:

\`\`\`text
GRU          mean 1.640 bits/byte
Transformer  mean 2.567 bits/byte
\`\`\`

GRU produced recognizable but repetitive English on all three seeds and is the current production baseline.

### Perception
Three-seed controlled semantic extraction:

\`\`\`text
BiGRU          72.0% exact state
Transformer    36.5%
GRU            36.3%
\`\`\`

Slot-query BiGRU refinement fell to 64.6% and is rejected.

### Closed loop
Three-seed controlled English → state → English:

\`\`\`text
perception exact               70.3%
oracle state → output         100.0%
hard predicted state → output 70.3%
soft predicted state → output 67.5%
\`\`\`

The controlled semantic bridge/producer adds essentially no extra exact loss when perception is correct.

## Cognitive Core v0 — replicated

Three-seed mixed-task OOD:

\`\`\`text
flat MLP                        23.9%
factor one-pass                 59.8%
factor recurrent                64.6%
factor recurrent, no reinject   65.8%
\`\`\`

The high-value result is the **factor-graph organization**, not the small aggregate recurrence gain.

Current interpretation:

- factor representation: keep;
- recurrence: useful selectively, especially where added thought unlocks a capability;
- input reinjection: demote;
- do not tune the current core for incremental gains.

Thought-depth OOD on the same trained recurrent core:

\`\`\`text
1 step   38.1%
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
\`\`\`

Memory specifically rises from 10.2% at one step to 99.6% at four.

## Specialist ceilings

\`\`\`text
relation   98.5% OOD
rule       97.3%
memory    100.0%
graph      45.5%
state      20.5%
\`\`\`

The shared core is already near the memory ceiling, reasonably close on relation, and leaves a large gap on rule induction. Graph/state remain weak even as specialists.

## Research-effort rule

Prioritize **step changes**.

Normally continue a branch only if it plausibly offers one of:

- ~20+ points on a meaningful capability metric;
- ~2× real efficiency;
- a new capability;
- strong OOD/transfer/generalization;
- a major reduction in examples/updates needed to learn something new.

Record smaller gains, but do not automatically spend another cycle optimizing them.

## Literature rule

Before expensive experiments:

\`\`\`text
question
→ exact-term search
→ adjacent terminology
→ mechanism search
→ recent + canonical literature
→ known failures/ablations
→ strongest relevant baseline
→ smallest unresolved experiment
\`\`\`

Use \`docs/AGENT_RESEARCH_TERMINOLOGY_MAP.md\` to translate our informal questions into research vocabulary.

## Transfer gate result

Cognitive Transfer v0 completed successfully across three seeds.

Held-out composition:

```text
relation traversal
→ memory lookup
→ inferred rule transform
```

At 1024 task-6 updates:

```text
fresh                 55.5% IID   28.0% OOD
ordinary transfer      96.0% IID   40.5% OOD
frozen-how             23.3% IID   21.0% OOD
```

Other key results:

```text
zero-shot task-6 OOD                 8.7%
old-task OOD before transfer        69.7%
old-task OOD after full fine-tuning  7.1%
old-task loss                       62.6 points
frozen-how trainable params         1,095
```

Decision:

- ordinary transfer is real but too small/incomplete to pass the high-leverage gate;
- the frozen reusable-"how" adapter failed;
- ordinary full fine-tuning catastrophically forgets old skills;
- current failure is dominated by compositional OOD generalization: ordinary transfer fits task 6 to 96% IID but reaches only 40.5% OOD.

Do not tune this core for another few points.

## Current next gate

Literature first, then one discriminating build around:

> **systematic compositional OOD generalization of already-learned operations**

Search neighboring mechanisms:

- neural algorithmic reasoning / processor transfer;
- modular neural networks / modular meta-learning;
- program induction / learned execution;
- variable binding / role-filler representations;
- task/operator graphs;
- learned sequencing/routing of reusable operators.

The next mechanism must beat the current factor-core baseline by enough to matter.

## Developmental track

Existing continual-learning evidence remains valid:

- forgetting is causally localized post hoc;
- simple prospective scalar predictors are weak.

Do not return to that track until a new mechanism or literature result offers a high-leverage test.

## Process

\`\`\`text
READ CURRENT DOCS
→ identify highest-leverage uncertainty
→ SEARCH literature and neighboring terminology
→ define a large-gain criterion
→ build smallest discriminating test
→ implement
→ compare against strong baselines
→ falsify / kill weak branches quickly
→ integrate only what materially survives
→ update frontier/evidence/decisions
\`\`\`

