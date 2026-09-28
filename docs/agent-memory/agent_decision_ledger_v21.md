# Agent Decision Ledger

**Version:** 2.1  
**Date:** 2026-09-28  
**Role:** authoritative record of current commitments, demotions, and open architectural variables.

## Current commitments

### D-001 — Chatbot first
The first integrated Agent product is a conversational system.

Sensors, games, robotics, and other embodiments remain optional later interfaces.

### D-002 — Capability is the common organizational unit
Capabilities may have heterogeneous private implementations but expose bounded public contracts.

### D-003 — No architecture religion
Do not assume:
- Transformer required or forbidden;
- tokens required or forbidden;
- SSM/recurrent core required;
- modules must be neural or symbolic;
- routing must be central or distributed.

These are experimental variables.

### D-004 — Separate memory types
Keep distinct:
- active state;
- episodic memory;
- semantic/world memory;
- capability memory.

Facts should usually enter episodic/semantic memory before parametric capability change.

### D-005 — Sparse activation is a measured target
Prefer `store broadly, activate narrowly` only where real wall-clock economics support it.

### D-006 — Development is multi-timescale
Fast cognition, medium contextual organization, and slow structural/parametric development are distinct.

### D-007 — Structural changes must pay rent
Promotion/compilation/recruitment must include:
- quality;
- latency;
- routing/recognition;
- memory movement;
- storage;
- developmental cost;
- maintenance cost.

### D-008 — Expensive training may teach cheap thinking
Training can over-compute if it produces cheaper reliable runtime pathways.

### D-009 — Periodic whole-system integration is mandatory
Synthetic experiments may guide components, but surviving mechanisms must periodically be assembled into the actual chatbot.

### D-010 — Build the primary language organ ourselves
The main Agent construction path trains its own language machinery rather than importing a pretrained LLM as the presumed cognitive core.

Pretrained LLMs remain allowed as:
- controls;
- reference quality/runtime baselines;
- temporary diagnostic instruments.

The goal is not architectural purity. The goal is to prevent an imported model from silently supplying most cognition while the Agent architecture becomes decorative.

The language organ must expose a bounded non-language conditioning interface so cognition can live outside language machinery.

---

## Current strong hypotheses

### H-001 — Heterogeneous capability ecology
The best system is likely to combine:
- strong language machinery;
- persistent recurrent/SSM continuity where useful;
- sparse/addressable memory;
- exact tools/code;
- learned specialists;
- capability-level sparse composition;
- multi-timescale developmental control.

### H-002 — Capability-scale sparsity is more promising than universal low-level sparsity
Sparse routing may be most valuable at thought/task/capability scale, while internal modules may use whatever dense/sparse computation suits them.

### H-003 — Attention and persistent state are complementary
Attention is a strong candidate for precise relational access; recurrent/SSM state is a strong candidate for cheap continuity.

### H-004 — Plasticity may itself need routing
The system may need to decide not only what computes, but:
- what may change;
- how quickly;
- which memory receives an experience;
- when transient adaptation becomes consolidated capability.

### H-005 — Useful cognition may be relational
Interaction motifs/coalitions can be first-class reusable computational objects.

---

## Demoted / rejected simple claims

### R-001 — "Avoid Transformers"
Rejected. Transformer use is an experimental variable.

### R-002 — "The recurrent cell ecology must become the whole chatbot"
Rejected. Agent v1 cells are a developmental test substrate, not the presumed final language substrate.

### R-003 — "Usage identifies mature cells"
Rejected simple rule.

### R-004 — "Old-task lesion importance identifies safe plasticity"
Rejected simple rule.

### R-005 — "Simple one-shot gradient/importance scores predict destructive updates"
Currently rejected as a sufficient rule.

### R-006 — "More static capacity automatically solves development"
Rejected.

### R-007 — "Compression alone justifies promotion"
Rejected. Utility/probation is required.

---

## Open decisions

- exact from-scratch language-organ architecture;
- Transformer/SSM/recurrent mix inside that organ;
- token/byte/patch representation;
- memory implementation;
- capability granularity;
- routing method;
- workspace format and bandwidth;
- stopping/escalation mechanism;
- online plasticity mechanism;
- reserve recruitment rule;
- motif promotion thresholds;
- physical placement/cache strategy;
- training curriculum;
- end-to-end integration boundary;
- whether sparse architecture beats compact conventional baselines on target hardware.