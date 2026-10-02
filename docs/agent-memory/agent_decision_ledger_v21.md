[Reading 99 lines from start (total: 99 lines, 0 remaining)]

# Agent Decision Ledger

Version: 2.4
Date: 2026-10-02
Role: active commitments and explicit demotions.
Current-state authority: ../AGENT_CURRENT.md

## Current commitments

### D-001 — Worker first
The first integrated product target is a generally capable worker agent.
Conversation is an interface, not the product boundary.

### D-002 — Build the deployed intelligence ourselves
The final learner is self-contained/homegrown. Pretrained models may be used
during development as teachers, critics, controls, or scientists.

### D-003 — No architecture religion
Transformers, recurrence, SSMs, Delta rules, symbolic components, bytes/tokens,
retrieval, tools, and learned modules remain experimental variables.

### D-004 — Structural changes must pay rent
Capability, transfer, compute, latency, memory, storage, maintenance, and
development cost all count.

### D-005 — Kaggle is the compute fabric
Substantive CPU work goes to Kaggle CPU. GPU work goes to Kaggle 2×T4.
The Optiplex is control/storage infrastructure, not a model-compute tier.
The phone is not an infrastructure dependency.
### D-006 — Optiplex is the durable control plane
The Optiplex owns persistent repos, credentials, manifests, scheduling,
retrieved results, logs, selected artifacts, and lightweight development
infrastructure. Python/pip/venv and similar server/dev tooling may be installed
as needed; that does not make the Optiplex a model-compute tier.

Storage policy:
- 2 TB Linux drive: canonical working state;
- 500 GB Toshiba USB: bulk/archive/backup and possible future worker home;
- 32 GB USB: reserved until a deliberate role is chosen.

### D-007 — Transformer is the performance baseline, not the destination
The parameter-matched causal byte Transformer currently defines the language
compute baseline. New sequence architectures must beat or complement it under
controlled evaluation.

### D-008 — Existing GRU/patch hybrid is demoted
Correcting the causal-alignment bug improved the model, but the corrected
hybrid lost decisively to the Transformer under a compute-normalized T4 gate.
Do not spend heavy training budget rescuing this implementation.

### D-009 — DeltaHybrid V1 is the mainline challenger
Build Gated-Delta-style recurrent/state blocks with occasional exact-attention
blocks. Initial comparison keeps raw bytes and other training variables fixed.

### D-010 — Causal execution equivalence is mandatory
Batch, streaming, and chunked execution must agree within defined numerical
tolerance before an autoregressive architecture receives serious training.
### D-011 — CPU correctness before GPU scale
Reference math, invariants, gradient checks, multi-seed CPU probes, and
long-context correctness run on Kaggle CPU before promoted T4 experiments.

### D-012 — Equal-step evidence is insufficient when throughput differs
Architecture promotion requires compute-normalized comparison in addition to
same-data/same-step controls.

### D-013 — Attention is allowed as exact access
The project is not trying to eliminate attention ideologically. The working
hypothesis is state-heavy computation for ordinary continuity plus occasional
attention/retrieval for precise access.

### D-014 — Persistent memory types remain distinct
Keep active neural state, episodic history, semantic/world memory, and durable
task/commitment state conceptually separate until evidence supports merging.

### D-015 — Development remains staged
Fast cognition, contextual organization, durable state, and slow
structural/parametric learning are distinct timescales.

### D-016 — Optiplex is a future weak-hardware deployment canary
Do not optimize the learner around the Optiplex now. After a model is mature
enough to deploy, use the Optiplex deliberately to test low-end commodity
hardware viability: memory footprint, startup latency, throughput, CPU load,
and whether the agent remains practically usable. This is a deployment gate,
not permission to shift substantive experiments away from Kaggle.

## Demoted / retired directions

- chatbot-first as the project objective;
- phone-first training or infrastructure;
- Optiplex as a substantive AI-compute tier;
- resuming the frozen V0 Phase-1 checkpoint;
- heavy training of the current GRU/patch hybrid;
- avoid-Transformers as a rule;
- pure recurrence must replace attention as a rule;
- architecture changes justified by elegance without controlled payoff.
## Open decisions

- exact Gated-Delta formulation for V1;
- efficient parallel/chunked training implementation;
- optimal recurrent-state : exact-attention ratio;
- whether DeltaHybrid V1 beats the Transformer per GPU-second;
- whether its advantage grows with context length;
- learned patching after the raw-byte architecture gate;
- external memory interface for the worker;
- persistent task-state representation;
- worker action ontology and training curriculum;
- deployment target for the mature worker;
- role, if any, for the reserved 32 GB USB device.
