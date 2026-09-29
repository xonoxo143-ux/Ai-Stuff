# Agent documentation index

**Date:** 2026-09-29  
**Purpose:** stable map of the Agent research record.

## One living document

**`AGENT_CURRENT.md`** is the only living source of project state.

It contains:

- current architecture;
- strongest surviving evidence;
- rejected/demoted directions;
- research/build rules;
- current unresolved question;
- exact next gate.

After each meaningful cycle, update **this file only** for project state.

## Result records

Completed experiments keep their own durable result/spec files when the technical detail is worth preserving. These are evidence, not competing current-state documents.

Important current records include:

- `AGENT_COGNITIVE_CORE_V0.md`
- `AGENT_COGNITIVE_TRANSFER_V0.md`
- `AGENT_LANGUAGE_REAL_TEXT_RESULT_01.md`
- `AGENT_LANGUAGE_PERCEPTION_RESULT_02.md`
- `AGENT_LANGUAGE_ROUNDTRIP_V0.md`
- `AGENT_LANGUAGE_ORGAN_RESULT_01.md`
- `AGENT_V1_A1_UPDATE_REVERSION_REPLICATION.md`
- `AGENT_V1_A1_UPDATE_PREDICTORS.md`
- `AGENT_V0_CLOSEOUT.md`

Completed result files should normally be immutable except for factual corrections.

## Reference / history

These may help explain prior reasoning but are **not** maintained as current truth:

- `AGENT_RESEARCH_TERMINOLOGY_MAP.md`
- `agent-memory/agent_current_frontier_v21.md` — deprecated pointer only;
- historical specs, notebooks, evidence/decision ledgers, and archives.

## Infrastructure

Execution/test infrastructure, not cognitive architecture:

- `AGENT_FLOOT_LAB.md`
- `AGENT_HF_JOBS.md`

`ARCHITECTURE.md` describes the Android AI Workbench/app architecture, not Agent cognition.

## Conflict rule

When anything disagrees:

1. `AGENT_CURRENT.md`;
2. the newest directly relevant completed result;
3. older reference/history.

## Recovery rule

```text
AGENT_CURRENT.md
→ only open linked evidence if needed
→ continue from its next gate
```

Do not reconstruct current state by merging old summaries.
