# Agent Decision Ledger

**Version:** 2.2  
**Date:** 2026-09-29  
**Role:** authoritative record of current commitments, demotions, and open architectural variables.

## Current commitments

### D-001 — Chatbot first
The first integrated Agent product is a conversational system.

### D-002 — Capability is the common organizational unit
Capabilities may have heterogeneous private implementations but expose bounded public contracts.

### D-003 — No architecture religion
Transformer, recurrence, SSMs, symbolic machinery, bytes/tokens, tools and learned modules are experimental variables.

### D-004 — Separate memory types
Keep active, episodic, semantic/world, and capability memory conceptually distinct.

### D-005 — Sparse activation is a measured target
Prefer store-broadly/activate-narrowly only where real wall-clock economics support it.

### D-006 — Development is multi-timescale
Fast cognition, medium contextual organization, and slow structural/parametric development are distinct.

### D-007 — Structural changes must pay rent
Quality, transfer, latency, memory movement, storage, development and maintenance cost all count.

### D-008 — Expensive training may teach cheap thinking
Training may over-compute when it produces cheaper reliable runtime pathways.

### D-009 — Periodic whole-system integration is mandatory
Synthetic experiments guide components; surviving mechanisms must periodically enter the actual chatbot.

### D-010 — Build the primary language machinery ourselves
The main path trains its own language perception/production rather than importing a pretrained LLM as the cognitive core.

Pretrained LLMs remain controls/reference systems.

### D-011 — Optimize for high-leverage progress
Do not spend long cycles polishing small positive effects.

A new branch should normally plausibly offer at least one of:

- ~20+ percentage points on a meaningful capability metric;
- ~2× real efficiency;
- a previously absent capability;
- strong OOD/transfer/generalization;
- a major reduction in examples/updates needed to acquire a capability.

These are triage heuristics, not rigid laws. Smaller gains can be evidence without becoming a research program.

### D-012 — Literature before expensive builds
Before a costly experiment:

1. search the question in our wording;
2. search adjacent terminology;
3. search the mechanism rather than only the objective;
4. inspect recent work and canonical precedents;
5. inspect known failures/ablations;
6. identify the strongest relevant baseline;
7. build only the unresolved discriminating experiment.

Maintain terminology mappings in \`AGENT_RESEARCH_TERMINOLOGY_MAP.md\`.

### D-013 — Factor-graph organization is the current cognitive baseline
The large replicated gain was:

\`\`\`text
flat OOD 23.9%
→ factor one-pass OOD 59.8%
\`\`\`

Retain shared symbol/entity nodes with role-typed fact/query connections as the current baseline until a higher-leverage replacement wins.

### D-014 — Recurrent thought is selective, not automatically maximal
Repeated computation can unlock capabilities, but current results saturate near four steps on this benchmark.

Use extra thought depth only where it measurably earns value. Do not assume more recurrent steps are better.

## Current strong hypotheses

### H-001 — Useful cognition benefits from explicit relational organization
Persistent entity/symbol identity plus structured message passing is currently much stronger than flattening the same information.

### H-002 — Shared computation may become valuable through transfer
The next critical question is not whether one core can multitask, but whether previous tasks make a genuinely new task dramatically cheaper to learn.

### H-003 — Perception and production can specialize
Current evidence favors BiGRU for controlled perception and GRU for small real-text production. They need not share a substrate.

### H-004 — Plasticity may itself need routing
The system may need to decide what may change, how quickly, where experience is stored, and when transient adaptation consolidates.

### H-005 — Useful cognition may be relational/compositional
Reusable computation may reside in capabilities, interaction motifs, factor-graph operations, or composable low-rank/recurrent components.

## Demoted / rejected simple claims

### R-001 — "Avoid Transformers"
Rejected.

### R-002 — "The recurrent cell ecology must become the whole chatbot"
Rejected.

### R-003 — "Usage identifies mature cells"
Rejected.

### R-004 — "Old-task lesion importance identifies safe plasticity"
Rejected.

### R-005 — "Simple one-shot gradient/importance scores predict destructive updates"
Rejected as a sufficient rule.

### R-006 — "More static capacity automatically solves development"
Rejected.

### R-007 — "Compression alone justifies promotion"
Rejected.

### R-008 — "Input reinjection is necessary for the cognitive core"
Not supported in the replicated v0 gate. No-reinjection slightly outperformed reinjection in aggregate OOD.

### R-009 — "Slot-query attention improves the BiGRU perception baseline"
Rejected by three-seed replication.

### R-010 — "More thought steps are always better"
Rejected. Current OOD performance saturates around four-to-six recurrent steps.

## Open decisions

- representation for open-domain non-language state;
- transfer mechanism for genuinely new task families;
- whether explicit WHAT/HOW decomposition beats ordinary shared-core fine-tuning;
- exact language perception/production architectures at larger scale;
- learned vs structured entity/factor construction from natural language;
- memory implementation outside controlled associative-memory tasks;
- capability granularity/routing;
- adaptive stopping/escalation;
- online plasticity mechanism;
- physical placement/cache strategy;
- end-to-end dialogue curriculum;
- whether the final system meets target-hardware quality/cost constraints.
