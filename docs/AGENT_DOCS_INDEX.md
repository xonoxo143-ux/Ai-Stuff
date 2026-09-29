# Agent documentation index

**Date:** 2026-09-29  
**Purpose:** stable map of modular Agent project context.

## Living modules

### Build / project state

**`AGENT_CURRENT.md`**

What the project currently believes, what has survived testing, current architecture, demotions, and next build gate.

Load this for a **build chat**.

### Research pair

**`AGENT_RESEARCH_FINDINGS.md`**

External evidence only: what the scientific literature currently supports, limitations, open questions, terminology, and sources.

**`AGENT_RESEARCH_SYNTHESIS.md`**

Our integrated inference: what may be possible when the external findings are combined with our own experiments, how that model changed after tests, and what experiment should discriminate it next.

Load **both** for a **research chat**.

## Modular chat recipes

```text
BUILD
AGENT_CURRENT.md

RESEARCH
AGENT_RESEARCH_FINDINGS.md
+ AGENT_RESEARCH_SYNTHESIS.md

ONE EXPERIMENT
AGENT_CURRENT.md
+ relevant immutable result file

FULL PROJECT
AGENT_CURRENT.md
+ AGENT_RESEARCH_FINDINGS.md
+ AGENT_RESEARCH_SYNTHESIS.md
+ result files only when deeper evidence is needed
```

Each living module is written to remain understandable on its own, while the three compose cleanly.

## Result records

Completed experiments keep durable result/spec files when the technical detail is worth preserving. These are evidence, not competing state documents.

Important records include:

- `AGENT_COGNITIVE_CORE_V0.md`
- `AGENT_COGNITIVE_TRANSFER_V0.md`
- `AGENT_LANGUAGE_REAL_TEXT_RESULT_01.md`
- `AGENT_LANGUAGE_PERCEPTION_RESULT_02.md`
- `AGENT_LANGUAGE_ROUNDTRIP_V0.md`
- `AGENT_LANGUAGE_ORGAN_RESULT_01.md`
- `AGENT_V1_A1_UPDATE_REVERSION_REPLICATION.md`
- `AGENT_V1_A1_UPDATE_PREDICTORS.md`
- `AGENT_V0_CLOSEOUT.md`

Result files should normally be immutable except for factual corrections.

## Historical / compatibility pointers

- `AGENT_RESEARCH_TERMINOLOGY_MAP.md` — deprecated pointer to the research pair.
- `agent-memory/agent_current_frontier_v21.md` — deprecated pointer to `AGENT_CURRENT.md`.
- old notebooks, evidence/decision ledgers, and historical specs remain reference material only.

## Infrastructure

- `AGENT_FLOOT_LAB.md`
- `AGENT_HF_JOBS.md`

`ARCHITECTURE.md` is Android AI Workbench/app architecture, not Agent cognition.

## Authority boundaries

There is deliberately no single global authority for every kind of statement:

```text
project/build truth       → AGENT_CURRENT.md
external scientific truth → AGENT_RESEARCH_FINDINGS.md
project synthesis         → AGENT_RESEARCH_SYNTHESIS.md
exact experiment evidence → relevant RESULT file
```

When a synthesis conflicts with an experiment, the experiment wins.

When a project decision conflicts with a newer project experiment, update `AGENT_CURRENT.md`.

When newer literature changes the external frontier, update FINDINGS first; do not silently rewrite the build.
