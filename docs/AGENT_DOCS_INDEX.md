# Agent documentation index

**Date:** 2026-09-28  
**Purpose:** make the Agent line searchable without forcing readers to reconstruct chronology from dozens of experiment files.

## Read order

### 1. Current answer

**`AGENT_CURRENT.md`**

Authoritative current architecture, evidence summary, open decisions, and active frontier.

Start here after any gap in context.

### 2. Product/integration target

**`AGENT_V1_CHATBOT_ANCHOR.md`**

Defines chatbot-first integration and the relationship between language machinery, the capability ecology, and optional future game/sensor interfaces.

### 3. Current developmental experiment

**`AGENT_V1_A1_UPDATE_PREDICTORS.md`**

Current test of prospective destructive-update predictors.

### 4. Latest replicated mechanistic evidence

**`AGENT_V1_A1_UPDATE_REVERSION_REPLICATION.md`**

Fresh-seed evidence that forgetting is disproportionately attributable to a small subset of private-cell updates.

### 5. Agent v1 experimental lineage

**`AGENT_V1_A_SPEC.md`**

Historical baseline specification for V1-A. Useful for original gates and controls, but its embedded "current frontier" text is not authoritative.

Then consult the individual `AGENT_V1_A1_*.md` result/spec files for exact experimental provenance.

### 6. Agent v0 evidence

**`AGENT_V0_CLOSEOUT.md`**

Start here for the frozen v0 evidence carried into v1.

The remaining `AGENT_V0_*.md` files contain individual experiments.

## Infrastructure docs

These are compute/test infrastructure, not cognitive architecture:

- `AGENT_FLOOT_LAB.md`
- `AGENT_HF_JOBS.md`

## Unrelated/sibling architecture docs in this repository

**`ARCHITECTURE.md`** describes the Android AI Workbench/app architecture. It is not the Agent cognition architecture.

Do not infer Agent architecture from generic repository documents without checking scope.

## Document status convention

Use these meanings when adding/updating Agent docs:

```text
CURRENT
authoritative current orientation

ACTIVE EXPERIMENT
a live hypothesis under test

RESULT
durable evidence from a completed experiment

HISTORICAL SPEC
the plan at a point in time; useful provenance, not current status

SUPERSEDED
kept only because the failure/history matters
```

## Search rule

When search returns multiple plausible "current" answers:

1. prefer `AGENT_CURRENT.md`;
2. then prefer the newest RESULT relevant to the question;
3. then use active experiment specs;
4. treat older specs/plans as historical unless explicitly re-promoted.

The long architecture notebook in the persistent Library remains the deep conceptual record. Its new front-page snapshot should be treated the same way: current snapshot first, numbered historical sections second.
