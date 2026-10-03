# Agent documentation index

**Date:** 2026-10-03
**Purpose:** stable map of modular Agent project context and documentation layout.

## Living modules

### Build / project state

**`AGENT_CURRENT.md`**

What the project currently believes, what has survived testing, current architecture, demotions, and next build gate.

Load this for a **build chat**.

### Research pair

**`AGENT_RESEARCH_FINDINGS.md`**

External evidence only: scientific literature, limitations, open questions, terminology, and sources.

**`AGENT_RESEARCH_SYNTHESIS.md`**

Project inference: what may be possible when external findings are combined with project experiments, how the model changed after tests, and what experiment should discriminate it next.

Load **both** for a **research chat**.

## Physical layout

`docs/` keeps living modules and files whose paths are consumed directly by workflows or project machinery.
`docs/evidence/` contains immutable or completed experimental evidence, grouped by project phase:
- `developmental/` — developmental construction, reasoning, grounding, uncertainty, dialogue, and related experiments.
- `language/` — completed language-organ/perception/real-text/screen results.
- `agent-v0/` — Agent v0 causal, motif, phone, and closeout evidence.
- `agent-v1/` — completed Agent v1 replication evidence that is not path-bound.
- `whole-agent/` — whole-agent chatbot and closure results.

`docs/compute/` contains compute-backend notes such as Floot and Hugging Face Jobs.

`docs/app/` contains Android/workbench/build/signing/device-run documentation.

`docs/history/` contains deprecated or superseded design/reference documents retained for provenance.

`docs/agent-memory/` remains historical compatibility material.

Some immutable evidence remains directly under `docs/` because GitHub workflows address those exact paths. Do not move those files merely for visual consistency.

## Modular chat recipes

```text
BUILD
AGENT_CURRENT.md

RESEARCH
AGENT_RESEARCH_FINDINGS.md
+ AGENT_RESEARCH_SYNTHESIS.md

ONE EXPERIMENT
AGENT_CURRENT.md
+ relevant immutable result file under evidence/ or a workflow-bound root path
FULL PROJECT
AGENT_CURRENT.md
+ AGENT_RESEARCH_FINDINGS.md
+ AGENT_RESEARCH_SYNTHESIS.md
+ result files only when deeper evidence is needed
```

Each living module is written to remain understandable on its own, while the three compose cleanly.

## Result records

Completed experiments keep durable result/spec files when the technical detail is worth preserving. These are evidence, not competing state documents.

Representative records:
- `AGENT_COGNITIVE_CORE_V0.md` — workflow-bound root evidence.
- `AGENT_COGNITIVE_TRANSFER_V0.md` — workflow-bound root evidence.
- `evidence/language/AGENT_LANGUAGE_REAL_TEXT_RESULT_01.md`
- `evidence/language/AGENT_LANGUAGE_PERCEPTION_RESULT_02.md`
- `AGENT_LANGUAGE_ROUNDTRIP_V0.md` — workflow-bound root evidence.
- `evidence/language/AGENT_LANGUAGE_ORGAN_RESULT_01.md`
- `evidence/agent-v1/AGENT_V1_A1_UPDATE_REVERSION_REPLICATION.md`
- `AGENT_V1_A1_UPDATE_PREDICTORS.md` — workflow-bound root evidence.
- `evidence/agent-v0/AGENT_V0_CLOSEOUT.md`

Result files should normally be immutable except for factual corrections.

## Historical / compatibility pointers

- `history/AGENT_RESEARCH_TERMINOLOGY_MAP.md` — deprecated pointer to the research pair.
- `history/AGENT_MEMORY_RETRIEVAL_V0.md` — retained older retrieval baseline.
- `history/AGENT_V0_SPEC.md` — retained Agent v0 implementation specification.
- `agent-memory/agent_current_frontier_v21.md` — deprecated pointer to `AGENT_CURRENT.md`.
- old notebooks, evidence/decision ledgers, and historical specs remain reference material only.
## Compute and application documentation

Compute backends:
- `compute/AGENT_FLOOT_LAB.md`
- `compute/AGENT_HF_JOBS.md`

Application/build material:
- `app/ARCHITECTURE.md`
- `app/BUILD.md`
- `app/ANDROID_SIGNING.md`
- `app/FIRST_AGENT_RUN.md`
- `app/FIRST_DEVICE_RUN.md`
- `app/WORKBENCH_V0.md`

`app/ARCHITECTURE.md` is Android AI Workbench/app architecture, not Agent cognition.

## Authority boundaries

There is deliberately no single global authority for every kind of statement:

```text
project/build truth       → AGENT_CURRENT.md
external scientific truth → AGENT_RESEARCH_FINDINGS.md
project synthesis         → AGENT_RESEARCH_SYNTHESIS.md
exact experiment evidence → relevant immutable result file
```

When a synthesis conflicts with an experiment, the experiment wins.

When a project decision conflicts with a newer project experiment, update `AGENT_CURRENT.md`.

When newer literature changes the external frontier, update FINDINGS first; do not silently rewrite the build.

Physical location does not change authority. Moving a historical/result file into a category directory is organizational only.
