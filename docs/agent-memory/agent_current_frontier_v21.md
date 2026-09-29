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

## Next gate

**Transfer / learning-to-learn.**

Test a genuinely new sixth family.

Compare:

1. fresh core;
2. current shared factor core adapted to the new family;
3. explicit reusable-computation / compositional meta-learning baseline.

Measure zero-shot behavior and examples/updates to a fixed OOD target.

The result must be large enough to matter. Example heuristic:

\`\`\`text
2000 → 1700 examples   stop / low leverage
2000 → 500             interesting
2000 → 100             major
strong zero/few-shot   major
\`\`\`

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
