# Agent Evidence Ledger

**Version:** 2.2  
**Date:** 2026-09-29  
**Role:** authoritative summary of what experiments currently support or reject.

## Status vocabulary

- **SUPPORTED** — reproduced strongly enough to guide design.
- **PROMISING** — signal exists but needs broader replication/integration.
- **WEAK / MIXED** — inconsistent or too small to guide architecture.
- **REJECTED SIMPLE RULE** — tested formulation failed; related richer mechanisms remain possible.
- **OPEN** — not yet established.

## Developmental evidence

### E-V0-001 — Sparse execution can save real runtime
**Status:** SUPPORTED

Agent v0 demonstrated real wall-clock savings from sparse top-k execution relative to dense execution.

### E-V0-002 — Shallow recurrent thought can be useful
**Status:** SUPPORTED

Shallow recurrence improved prediction in the tested regime while excess untrained depth degraded it.

### E-V0-003 — Learned cells can acquire causal specialization
**Status:** SUPPORTED

Lesion tests found reproducible cell-specific causal effects.

### E-V0-004 — Useful computation can be relational
**Status:** SUPPORTED

Pair interventions found useful interaction/synergy effects not assignable cleanly to isolated cells.

### E-V0-005 — Useful motifs can be compiled but must pay rent
**Status:** SUPPORTED LOCALLY

A validated pair motif was compiled to a smaller/faster computation, but whole-agent savings were too small for promotion.

### E-V1-001 — Larger static capacity is not automatically better
**Status:** SUPPORTED NEGATIVE RESULT

Early v1 sweeps found no simple robust capacity crossover.

### E-V1-002 — Sequential lifetime learning creates measurable interference
**Status:** SUPPORTED

Blocked-family lifelong training produced measurable forgetting/retention effects.

### E-V1-003 — Private recurrent updates can cause forgetting
**Status:** SUPPORTED

Freezing private recurrent weights reduced old-task damage on sampled destructive transitions.

### E-V1-004 — Usage is not maturity
**Status:** REJECTED SIMPLE RULE

High-use cells were not reliably the cells that deserved protection.

### E-V1-005 — Execution importance is not update danger
**Status:** REJECTED SIMPLE RULE

Old-task lesion importance did not reliably identify updates that later caused forgetting.

### E-V1-006 — Destructive updates are localized post hoc
**Status:** SUPPORTED / REPLICATED

Fresh-seed top-4 reversion captured about 95%+ of positive destructive-attribution mass in both fixed16 and sparse64 conditions.

### E-V1-007 — Simple prospective per-cell predictors are weak
**Status:** REJECTED SIMPLE RULE / MIXED

Gradient magnitude, usage×gradient, sensitivity×gradient and old/new conflict all showed near-zero rank correlation with true destructive-update attribution.

## Language evidence

### E-LANG-001 — Tiny byte models show architecture-specific tradeoffs
**Status:** SUPPORTED IN SYNTHETIC BENCHMARK

Five-seed ~130k-150k parameter comparison:

\`\`\`text
GRU          2.002 bits/byte   5/5 validation wins
Transformer  2.606
fixed patch  3.381
\`\`\`

The Transformer trained much faster; the fixed-patch formulation was dropped.

### E-LANG-002 — Bounded non-language state can drive compositional language
**Status:** SUPPORTED IN SYNTHETIC BENCHMARK

Across three seeds, both GRU and Transformer producers generated all 64 held-out structured semantic combinations exactly.

### E-LANG-003 — BiGRU leads controlled language perception
**Status:** SUPPORTED IN CONTROLLED SYNTHETIC BENCHMARK

Three-seed means:

\`\`\`text
BiGRU          72.0% exact   91.6% slot accuracy
Transformer    36.5% exact   77.9%
GRU            36.3% exact   75.9%
\`\`\`

### E-LANG-004 — Sub-million raw-byte GRU learns recognizable real English cheaply
**Status:** SUPPORTED ON BOUNDED REAL-TEXT CURRICULUM

Three-seed TinyStories replication, random initialization, 800 updates:

\`\`\`text
GRU          mean 1.640 bits/byte
Transformer  mean 2.567 bits/byte
\`\`\`

All three GRU samples were recognizably English but repetitive. Transformer samples remained substantially more malformed at the same update budget.

Design consequence:
- GRU is the current production baseline;
- do not confuse recognizable surface language with open-domain conversational intelligence.

### E-LANG-005 — Slot-query attention did not improve BiGRU perception
**Status:** REJECTED SIMPLE REFINEMENT

\`\`\`text
plain BiGRU       72.0% exact
attentive BiGRU   64.6%
\`\`\`

### E-LANG-006 — Controlled language→state→language junction adds little loss
**Status:** SUPPORTED IN CONTROLLED SYNTHETIC BENCHMARK

Three-seed closed loop:

\`\`\`text
perception exact state      70.3%
oracle state output        100.0%
hard predicted-state output 70.3%
soft predicted-state output 67.5%
\`\`\`

The hard-state roundtrip exact rate equals perception exactness. When perception recovers the correct state, the bridge and trained producer are effectively lossless on this controlled task.

## Cognitive-core evidence

### E-COG-001 — Factor-graph organization produces a large OOD gain
**Status:** SUPPORTED / REPLICATED

Three-seed, 400 mixed updates:

\`\`\`text
flat MLP OOD          23.9%
factor one-pass OOD   59.8%
\`\`\`

The factor model also uses far fewer parameters (~105k vs ~380k).

Design consequence:

> Explicit persistent symbol/entity identity with role-typed fact/query connections is the current high-leverage cognitive representation baseline.

### E-COG-002 — Aggregate recurrence gain is real but modest relative to cost
**Status:** SUPPORTED / LOW-TO-MEDIUM LEVERAGE

\`\`\`text
factor one-pass     59.8% OOD   ~7.6 s
factor recurrent    64.6% OOD   ~26.0 s
\`\`\`

Do not launch a long tuning campaign around the aggregate +4.8 point gain.

### E-COG-003 — Repeated thought can unlock specific capabilities
**Status:** SUPPORTED / REPLICATED

Same trained recurrent model, OOD mean:

\`\`\`text
1 step   38.1%
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
\`\`\`

Associative memory:

\`\`\`text
1 step   10.2%
2 steps  52.0%
4 steps  99.6%
6 steps 100.0%
\`\`\`

Design consequence:
- recurrent depth should be treated as selective computation;
- current benchmark mostly saturates around four steps.

### E-COG-004 — Input reinjection did not pay rent
**Status:** REJECTED SIMPLE ASSUMPTION

\`\`\`text
recurrent + reinjection     64.6% OOD
recurrent no reinjection    65.8% OOD
\`\`\`

Do not preserve input reinjection as a default architectural requirement.

### E-COG-005 — Specialist ceilings localize the remaining useful gaps
**Status:** SUPPORTED / REPLICATED

Recurrent specialists:

\`\`\`text
relation   98.5% OOD
rule       97.3%
memory    100.0%
graph      45.5%
state      20.5%
\`\`\`

Approximate shared recurrent OOD:

\`\`\`text
relation   88.7%
rule       65.8%
memory     99.7%
graph      46.2%
state      22.8%
\`\`\`

Interpretation:
- memory is effectively at its specialist ceiling;
- graph/state are weak even in specialists and should not drive shared-core tuning;
- rule induction is the largest meaningful shared-vs-specialist gap;
- the next high-value question is transfer, not another architecture micro-tweak.

## Architectural evidence

### E-ARCH-001 — One substrate is not required
**Status:** ARCHITECTURAL SYNTHESIS

Current evidence supports treating perception, cognition, production, memory and exact capabilities as separable mechanisms connected by bounded contracts.

### E-ARCH-002 — Whole-system utility dominates local elegance
**Status:** SUPPORTED DESIGN RULE

Local improvement is insufficient when recognition, routing, runtime, memory, maintenance or research cost overwhelms the gain.

### E-ARCH-003 — Research leverage is now an explicit evaluation dimension
**Status:** PROCESS RULE

A positive result does not automatically earn another cycle.

Prefer experiments that plausibly yield step changes: large capability gains, ≥2× efficiency, new abilities, strong transfer/OOD behavior, or much faster acquisition of new skills.
