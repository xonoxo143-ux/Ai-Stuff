# Agent documentation index

**Date:** 2026-09-29  
**Purpose:** make the Agent line searchable without reconstructing chronology from every experiment file.

## Read order

### 1. Current answer

**\`AGENT_CURRENT.md\`**

Authoritative current architecture, evidence summary, leverage rule, and next gate.

### 2. Short frontier

**\`agent-memory/agent_current_frontier_v21.md\`**

Compressed current state for fast cold-start recovery.

### 3. Current cognitive-core result

**\`AGENT_COGNITIVE_CORE_V0.md\`**

Replicated factor-graph core result, thought-depth evidence, specialist ceilings, and the next transfer gate.

### 4. Research terminology map

**\`AGENT_RESEARCH_TERMINOLOGY_MAP.md\`**

Maps our informal research questions onto literature terms such as recurrent depth, compositional meta-learning, neural algorithmic reasoning, factor graphs and adaptive computation.

Consult this **before expensive new branches**.

### 5. Language results

- \`AGENT_LANGUAGE_REAL_TEXT_RESULT_01.md\` — real-text from-scratch production baseline.
- \`AGENT_LANGUAGE_PERCEPTION_RESULT_02.md\` — rejected attentive-BiGRU refinement and current perception baseline.
- \`AGENT_LANGUAGE_ROUNDTRIP_V0.md\` — controlled English→state→English bridge result.
- \`AGENT_LANGUAGE_ORGAN_RESULT_01.md\` — early synthetic production comparison.

### 6. Developmental / continual-learning evidence

- \`AGENT_V1_A1_UPDATE_REVERSION_REPLICATION.md\` — post-hoc destructive-update localization.
- \`AGENT_V1_A1_UPDATE_PREDICTORS.md\` — weak simple prospective predictors.
- \`AGENT_V1_A_SPEC.md\` — historical v1-A specification.
- \`AGENT_V0_CLOSEOUT.md\` — frozen v0 evidence.

## Infrastructure docs

Compute/test infrastructure, not cognitive architecture:

- \`AGENT_FLOOT_LAB.md\`
- \`AGENT_HF_JOBS.md\`

## Unrelated/sibling repository docs

\`ARCHITECTURE.md\` describes the Android AI Workbench/app architecture, not the Agent cognition architecture.

## Document status convention

\`\`\`text
CURRENT
authoritative current orientation

ACTIVE EXPERIMENT
live hypothesis under test

RESULT / REPLICATED BASELINE
durable completed evidence

HISTORICAL SPEC
plan at a point in time

SUPERSEDED
retained because failure/history matters
\`\`\`

## Conflict rule

When documents disagree:

1. \`AGENT_CURRENT.md\`;
2. \`agent-memory/agent_current_frontier_v21.md\`;
3. newest relevant RESULT / REPLICATED BASELINE (currently including `AGENT_COGNITIVE_TRANSFER_V0.md`);
4. active experiment spec;
5. historical specs/archive.

## Research rule

Before adding a substantial new experiment document, check \`AGENT_RESEARCH_TERMINOLOGY_MAP.md\` and record which adjacent literature terms and baselines were searched.

The long architecture notebook remains deep historical/conceptual context, not the fastest current-state source.
