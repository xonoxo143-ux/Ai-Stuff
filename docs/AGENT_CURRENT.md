# Agent — Current Architecture and Frontier

**Date:** 2026-09-29  
**Status:** authoritative current orientation  
**Branch:** \`experiment/agent-v1-developmental-ecology\`

> If another Agent document disagrees with this file about the current direction, treat that document as historical unless this file explicitly re-promotes it.

## 0. Documentation contract

This is the **only living project-state/build document**.

Research is deliberately separated into a paired module:

- `AGENT_RESEARCH_FINDINGS.md` — **what the external scientific literature currently supports**;
- `AGENT_RESEARCH_SYNTHESIS.md` — **what we infer may be possible when those findings are linked with our experiments**, including how that synthesis changes after tests.

The boundary is strict: external evidence belongs in FINDINGS; project inference belongs in SYNTHESIS; adopted build decisions belong here.

After a meaningful build cycle:

1. update `AGENT_CURRENT.md` with the new project truth, decision, and next gate;
2. create one experiment/result document only when durable technical detail is worth preserving;
3. update SYNTHESIS if the result changes the integrated hypothesis;
4. update FINDINGS only when the literature frontier itself changes.

Completed experiment/result documents are immutable evidence except for factual corrections.

Do **not** maintain a second build frontier, duplicate current-state summary, evidence ledger, or decision ledger in parallel.

`AGENT_DOCS_INDEX.md` is a stable module map, not a per-cycle status file.

Modular recovery:

```text
build chat      → AGENT_CURRENT.md
research chat   → AGENT_RESEARCH_FINDINGS.md + AGENT_RESEARCH_SYNTHESIS.md
experiment chat → AGENT_CURRENT.md + the relevant result file
full project    → all three living modules + result files only as needed
```

## 1. Task anchor

Build an intelligent local conversational agent from scratch, with a finished runnable system no larger than roughly 32 GB.

A pretrained LLM may be used only as a control/reference system. It must not silently supply the intelligence we are trying to build.

Short form:

\`\`\`text
STORE BROADLY
ACTIVATE NARROWLY
DEVELOP SELECTIVELY
\`\`\`

The first integrated embodiment is a chatbot.

## 2. Current architecture

The strongest current path is no longer "pick one monolithic language model."

\`\`\`text
English / bytes
      ↓
language perception
(current baseline: BiGRU)
      ↓
bounded non-language state
      ↓
general cognitive core
(current baseline: factor-graph processor)
      ↓
bounded non-language state
      ↓
language production
(current baseline: GRU)
      ↓
English / bytes
\`\`\`

Memory, tools, retrieval, persistent state, development and specialist capabilities are attached around this core as they earn a measurable role.

The language organs and cognitive core do not have to share one architecture.

## 3. Language evidence

### Production

Random-init raw-byte real-text replication on the same bounded TinyStories curriculum, 800 updates, three seeds:

\`\`\`text
GRU          800,640 params   mean 1.640 bits/byte
Transformer  927,872 params   mean 2.567 bits/byte
\`\`\`

All three GRU runs produced recognizable but repetitive English. The Transformer trained faster but remained substantially worse at the same update budget.

Current production baseline: **GRU**.

### Perception

Controlled English-bytes → structured-state task, three seeds:

\`\`\`text
BiGRU          72.0% exact state   91.6% slot accuracy
Transformer    36.5% exact state   77.9% slot accuracy
GRU            36.3% exact state   75.9% slot accuracy
\`\`\`

A slot-query attentive BiGRU refinement fell to 64.6% exact and was rejected.

Current perception baseline: **plain BiGRU**.

### Closed language loop

Controlled held-out paraphrases:

\`\`\`text
English
→ BiGRU perception
→ 16-d semantic state
→ GRU production
→ canonical English
\`\`\`

Three-seed result:

\`\`\`text
perception exact state      70.3%
oracle state → sentence    100.0%
hard predicted state        70.3% exact sentence
soft predicted state        67.5% exact sentence
hard byte accuracy          98.65%
soft byte accuracy          98.70%
\`\`\`

When perception is correct, the controlled state bridge and producer add essentially no extra exact-sequence loss. The bottleneck in this probe is perception.

## 4. Cognitive Core v0 — replicated result

The first useful non-language core uses a common factor-graph representation:

\`\`\`text
fact / event / query slots
        ↕ role-typed messages
persistent shared symbol/entity nodes
\`\`\`

The same processor and answer vocabulary are used across:

- transitive relations;
- ordered mutable state;
- graph reachability;
- rule induction;
- associative memory.

Rigorous three-seed CI, 400 mixed updates:

\`\`\`text
model                         mean OOD   mean IID   train time
flat MLP                        23.9%      40.5%       3.7 s
factor one-pass                 59.8%      77.3%       7.6 s
factor recurrent                64.6%      80.6%      26.0 s
factor recurrent, no reinject   65.8%      81.6%      25.6 s
\`\`\`

The **large result** is the representation/organization change:

> flat 23.9% OOD → factor one-pass 59.8% OOD, with far fewer parameters.

That is high-leverage enough to guide architecture.

The average recurrence gain is much smaller:

> 59.8% → 64.6% OOD for roughly 3.4× training time.

Do not spend a long research cycle polishing that aggregate gain.

Input reinjection did not pay rent and is currently demoted.

## 5. Thought depth

The same trained recurrent core evaluated at different recurrent depths:

\`\`\`text
1 step   38.1% OOD mean
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
\`\`\`

Memory is the clearest capability unlock:

\`\`\`text
1 step   10.2%
2 steps  52.0%
4 steps  99.6%
6 steps 100.0%
\`\`\`

Interpretation:

- repeated computation can unlock capabilities;
- most value in this benchmark is obtained by about four steps;
- extra depth after saturation should not be paid for automatically.

This connects directly to the literature on **recurrent depth / looped networks / adaptive computation**, so future work should use that literature rather than rediscover the basic phenomenon.

## 6. Specialist ceilings

The same recurrent processor trained separately by task family:

\`\`\`text
family      specialist OOD
relation        98.5%
rule            97.3%
memory         100.0%
graph           45.5%
state           20.5%
\`\`\`

The shared recurrent core is approximately:

\`\`\`text
relation        88.7%
rule            65.8%
memory          99.7%
graph           46.2%
state           22.8%
\`\`\`

Implications:

- memory is effectively solved in this controlled benchmark;
- graph/state are limited even for specialists, so they are poor places for shared-core tuning until the task/representation is reconsidered;
- relation is reasonably close to specialist performance;
- rule induction has the largest meaningful shared-vs-specialist gap.

## 7. High-leverage experimental rule

The project now optimizes **progress per unit effort**, not the number of positive experiments.

A new branch should normally earn continued work by plausibly producing at least one of:

- roughly **20+ percentage points** of capability improvement on a meaningful metric;
- roughly **2× or greater** real efficiency improvement;
- a previously absent capability;
- strong OOD/transfer/generalization that changes what the system can do;
- a large reduction in examples or updates needed to acquire a new capability.

Smaller gains may be recorded as evidence, but normally do not earn another optimization cycle.

The thresholds are triage heuristics, not laws. The standard is: **does this materially move us toward the intelligent conversational agent?**

## 8. Literature-before-build rule

Before an expensive experimental branch:

\`\`\`text
state the question
→ search our wording
→ search neighboring terminology
→ search mechanism names
→ search recent work + canonical precedents
→ search known failure modes / ablations
→ identify the strongest relevant baseline
→ build only the unresolved discriminating test
\`\`\`

Use \`AGENT_RESEARCH_TERMINOLOGY_MAP.md\` as a reference when useful. New active terminology belongs here or in the experiment result that introduced it; the map no longer requires routine synchronization.

Important current mappings include:

- "think longer with the same brain" → recurrent depth, looped networks/Transformers, adaptive computation, iterative refinement;
- "reuse learned computation on new tasks" → compositional meta-learning, learning-to-learn, modular skill composition, what/how separation;
- "facts/entities connected by shared identity" → factor graphs, graph networks, message passing, relational inductive bias;
- "same processor across problem families" → neural algorithmic reasoning, shared processors, systematic/generalization benchmarks.

## 9. Transfer gate — completed

Cognitive Transfer v0 tested a genuinely new sixth family:

```text
relation traversal
→ associative memory lookup
→ inferred rule transformation
```

Three-seed result after 1024 task-6 updates:

```text
arm                    final IID   final OOD
fresh                     55.5%       28.0%
ordinary transfer          96.0%       40.5%
frozen-how adapter         23.3%       21.0%
```

Zero-shot task-6 OOD from the pretrained core was only **8.7%**.

Ordinary full fine-tuning improved task-6 OOD by **12.5 points** over fresh training, but this is below the project's high-leverage threshold and did not produce strong compositional extrapolation.

More importantly, old-family OOD fell from **69.7% to about 7.1%** after ordinary task-6 fine-tuning: a **62.6-point loss**.

The frozen-how adapter used only **1,095 trainable parameters**, but finished below the fresh baseline.

Interpretation:

- some ordinary transfer exists;
- it is not large enough to justify another tuning cycle;
- the current frozen reusable-"how" hypothesis failed this test;
- full fine-tuning catastrophically forgets old capabilities;
- 96.0% IID versus 40.5% OOD for ordinary transfer points to a compositional/algorithmic generalization failure rather than simple inability to fit task 6.

### Next high-information gate

Do **not** localize or optimize the small transfer effect yet.

Research first:

> What mechanism gives strong compositional OOD generalization when familiar operations must be chained in a genuinely new way?

Primary neighboring terms:

- systematic compositional generalization;
- neural algorithmic reasoning / processor transfer;
- modular neural networks and modular meta-learning;
- program induction / learned execution;
- variable binding / role-filler representations;
- task/operator graphs and learned operator sequencing.

The next build must compare a materially stronger compositional mechanism against the current factor-core baseline.

## 10. Current demotions / stopped branches

Do not keep rescuing these without new evidence:

- fixed-patch byte RNN;
- slot-query attentive BiGRU;
- input reinjection in Cognitive Core v0;
- simple one-shot destructive-update importance scores;
- static capacity as a solution to development;
- extra recurrent depth past the observed saturation point;
- small aggregate recurrence gains as a reason for prolonged tuning;
- frozen-how adaptation on Cognitive Transfer v0;
- ordinary full fine-tuning as a lifelong-learning solution.

## 11. Non-negotiable evaluation rule

Architectural elegance does not count.

A mechanism survives only if the whole-system gain justifies:

- quality;
- OOD/transfer ability;
- wall-clock cost;
- memory movement;
- routing/recognition overhead;
- storage;
- developmental cost;
- maintenance/research cost.

> Structural changes must pay rent — and the rent should usually be large enough to matter.
