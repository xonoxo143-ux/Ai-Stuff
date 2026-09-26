# Agent v1-A — Developmental Ecology Experiment

**Date:** 2026-09-26  
**Status:** implementation started  
**Branch:** `experiment/agent-v1-developmental-ecology`  
**Ancestor:** Agent v0 closeout `95294947949eb120f37e4019c4f725c1f863988c`

## 1. Lineage

Agent v1 is a direct continuation of the validated Agent v0 model in this repository.

Do not reconstruct v0 from prose. Reuse the code and tests under `agent-model/` and treat the closeout commit above as the frozen ancestor.

The v0 evidence carried forward is:

- sparse top-k execution produced real wall-clock savings;
- recurrent thought performed useful work but extra untrained depth caused drift;
- learned cells showed reproducible causal specialization under lesion;
- useful computation could belong to cell interactions;
- one interaction motif could be compiled into a smaller, faster reusable computation;
- local motif speedup was not enough to justify whole-system promotion automatically.

## 2. V1 question

> Can an initially sparse recurrent agent improve its own computational anatomy over a long lifetime, while structural changes remain causally and economically accountable?

The first implementation target is:

```text
16 mature recurrent cells
+
48 dormant reserve cells
=
64-cell maximum substrate
```

The 16+48 split is an experimental starting point, not an architectural law.

## 3. Build order

V1 is deliberately gated.

### V1-A0 — deterministic lifetime world

Build and validate:

- a reproducible nonstationary procedural lifetime;
- hidden evaluator-only regime metadata;
- random-access deterministic replay;
- exact checkpoint/resume identity;
- evaluator traces that never enter the agent input;
- CI tests for determinism and schedule behavior.

No reserve recruitment belongs in A0.

### V1-A1 — fixed controls

Run the v0 recurrent substrate in the lifetime world as:

1. fixed 16-cell sparse ecology;
2. fixed 64-cell sparse ecology;
3. dense 64-cell reference where practical.

Use paired world seeds and identical experience schedules.

The purpose is to determine whether the world creates an actual developmental pressure rather than assuming it does.

### V1-A2 — reserve recruitment

Only after A0/A1 are trustworthy:

- start with 16 mature cells and 48 dormant reserves;
- let repeated unresolved structure create a provisional recruitment opportunity;
- train the recruit under a bounded window;
- probation it on separate experience;
- retain or recycle it.

Zero recruitment must remain a legal outcome. Automatically filling all 48 reserve slots is a likely failure.

### V1-A3 — causal challenge

Add:

- lesions;
- forced activation/suppression;
- pair/coalition interventions;
- replacement tests.

Correlation with difficult examples is not enough. A retained recruit must make a causal contribution.

### V1-A4 — motif discovery and joint probation

Only after reserve development works:

```text
cheap structural screen
→ causal shortlist
→ provisional motif ecology
→ joint probation
→ prune dispensable structure
→ compile only if total-system economics improve
```

### V1-A5 — full developmental stress test

Initial target: roughly 100,000 sequential experiences over multiple paired seeds.

Measure development over time, not only final score.

## 4. A0 lifetime world

The A0 generator preserves the v0 register-machine event schema so the existing recurrent model can enter the world without an input rewrite.

The evaluator changes hidden target dynamics across seven phases:

| Lifetime fraction | Hidden regime | Main pressure |
|---|---|---|
| 0–10% | base | establish baseline |
| 10–25% | gain-add | changed operation semantics |
| 25–40% | mul-neg interaction | order-sensitive pair effect |
| 40–55% | gain + mul-neg | recombination of learned rules |
| 55–70% | base + frequent decoy | old regime returns with misleading recurrence |
| 70–85% | square-half interaction | new order-sensitive rule |
| 85–100% | gain + square-half | old rule returns in a new composition |

Regime identity and rule names are evaluator metadata only. They are not appended to the event tensor.

The world is deterministic per `(seed, experience_index)`. This makes checkpoint/resume and paired-control comparison exact without depending on global RNG state.

## 5. A0 pass conditions

A0 passes only if:

- the same seed and index reproduce bit-identical event/target tensors;
- random access matches sequential iteration;
- checkpoint resume identifies the same next experience;
- hidden regime labels do not change the public event schema;
- recurring and recombined phases appear at the intended lifetime regions;
- CI reproduces the same evaluator trace twice.

## 6. Controls and accounting

The core comparison after A0 is:

```text
FIXED-16
FIXED-SPARSE-64
DENSE-64
DEVELOPMENTAL-16+48
FROZEN-STRUCTURE EVALUATION
```

The developmental agent is charged for development.

Track:

- prediction/action error;
- adaptation after regime changes;
- recovery when old regimes return;
- active cells per thought;
- recurrence depth;
- routing cost;
- structural-learning cost;
- reserve awakenings / retention / recycling;
- lesion-defined specialization;
- motif recognition/dispatch cost;
- cumulative developmental compute;
- real wall-clock runtime.

Primary economic quantity:

```text
net developmental value
=
future quality/runtime gain
-
extra developmental cost
```

A structural learner that never repays its developmental cost has not met the efficiency goal.

## 7. Kill / redesign conditions

Redesign rather than protect v1 if repeated controlled runs show:

- developmental 16+48 does not beat the appropriate fixed control after development cost;
- reserve recruitment merely fills available capacity;
- sparse dispatch loses its real hardware advantage;
- specialization is not reproducible under causal challenge;
- promoted structures become irreversible clutter;
- old regimes cannot be recovered without raw replay;
- a hidden central meta-controller grows into the real cognition.

## 8. Current frontier

The current commit implements **V1-A0 only**.

Do not add reserve recruitment until deterministic lifetime generation, replay, checkpoint identity, and evaluator isolation have passed CI.
