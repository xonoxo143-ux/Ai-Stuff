# Agent Evidence Ledger

**Version:** 2.1  
**Date:** 2026-09-28  
**Role:** authoritative summary of what experiments currently support or reject.

## Status vocabulary

- **SUPPORTED** — reproduced strongly enough to guide design.
- **PROMISING** — signal exists but needs broader replication/integration.
- **WEAK / MIXED** — inconsistent or too small to guide architecture.
- **REJECTED SIMPLE RULE** — tested formulation failed; related richer mechanisms remain possible.
- **OPEN** — not yet established.

---

## E-V0-001 — Sparse execution can save real runtime
**Status:** SUPPORTED

Agent v0 demonstrated real wall-clock savings from sparse top-k execution relative to dense execution in the tested recurrent ecology.

Design consequence:
- sparsity is worth keeping as a hardware-dependent target;
- theoretical FLOP sparsity is not enough—wall-clock measurement remains mandatory.

---

## E-V0-002 — Shallow recurrent thought can be useful
**Status:** SUPPORTED

In the tested regime, shallow recurrence improved prediction while excess untrained depth degraded it.

Design consequence:
- recurrence depth should be adaptive/validated rather than universally maximized.

---

## E-V0-003 — Learned cells can acquire causal specialization
**Status:** SUPPORTED

Lesion tests found reproducible cell-specific causal effects.

Design consequence:
- internal processes can specialize without a human taxonomy;
- specialization must be measured causally, not inferred from activation frequency.

---

## E-V0-004 — Useful computation can be relational
**Status:** SUPPORTED

Pair interventions found useful interaction/synergy effects that could not be assigned cleanly to isolated cells.

Design consequence:
- reusable structure may be a capability **or an interaction motif**.

---

## E-V0-005 — Useful motifs can be compiled
**Status:** SUPPORTED LOCALLY

One validated pair motif was compiled into a smaller/faster computation.

But the whole-agent expected saving was too small to justify automatic promotion.

Design consequence:
- local speedup is insufficient;
- promotion must use total-system economics.

---

## E-V1-001 — Larger static capacity is not automatically better
**Status:** SUPPORTED NEGATIVE RESULT

Fixed sparse-64 and dense-64 did not produce a clean robust capacity crossover over fixed-16 across the early v1 capacity sweeps.

Design consequence:
- reserve recruitment cannot be justified merely by "more cells should help";
- development must earn a benefit beyond owning capacity.

---

## E-V1-002 — Sequential lifetime learning creates measurable interference
**Status:** SUPPORTED

Blocked-family lifelong training produced measurable forgetting/retention effects.

Design consequence:
- continual-learning pressure in the benchmark is real enough to study mechanistically.

---

## E-V1-003 — Private recurrent updates can cause forgetting
**Status:** SUPPORTED

Freezing private recurrent weights reduced old-task damage on sampled destructive transitions.

Design consequence:
- destructive interference is partly parametric, not merely routing/context noise.

---

## E-V1-004 — Usage is not maturity
**Status:** REJECTED SIMPLE RULE

Protecting high-usage cells did not reliably outperform matched random cells.

Rejected rule:
`high use -> important -> mature -> protect`

---

## E-V1-005 — Execution importance is not update danger
**Status:** REJECTED SIMPLE RULE

Cells that were most important for executing old skills did not reliably identify the updates responsible for later forgetting.

Rejected rule:
`important for old execution -> dangerous to modify`

Design consequence:
- execution causality and learning-update causality are different questions.

---

## E-V1-006 — Destructive updates are localized post hoc
**Status:** SUPPORTED / REPLICATED

Fresh-seed replication:

**fixed16**
- top-4 destructive updates beat matched random in **10/11** destructive transitions;
- top-4 captured about **95.4%** of positive destructive-attribution mass.

**sparse64**
- top-4 beat matched random in **8/12**;
- top-4 captured about **96.9%**.

Strongest supported statement:

> A relatively small subset of private-cell parameter updates disproportionately causes forgetting in the current benchmark.

Limitation:
- this is a post-hoc reversion/autopsy result, not an online learning rule.

---

## E-V1-007 — Simple prospective per-cell predictors are weak
**Status:** REJECTED SIMPLE RULE / MIXED

Tested predictors:
- incoming gradient magnitude;
- usage × incoming gradient;
- output-sensitivity × incoming gradient;
- old-loss sensitivity × incoming gradient;
- old/new gradient conflict.

Fresh-seed result:
- mean Spearman rank correlation with true destructive-update scores was near zero;
- fixed16 predictors were roughly +0.02 to +0.11;
- sparse64 predictors were roughly -0.06 to -0.03.

Some selected top-4 sets protected old performance more often than random, but the ranking signal was weak and overlap with true destructive cells modest.

Design consequence:
- do not keep rescuing the hypothesis with increasingly clever one-shot scalar "importance" scores;
- next tests should distinguish trajectory/history, interactions, and spare-capacity routing explanations.

---

## E-ARCH-001 — One substrate is not required
**Status:** ARCHITECTURAL SYNTHESIS, NOT YET PERFORMANCE PROOF

The project now treats `Capability` as the common public abstraction. A capability may be implemented by:
- Transformer/attention;
- SSM/recurrent machinery;
- learned memory;
- code;
- tools;
- learned specialists;
- compiled compositions.

This is a design direction supported by prior internal failures of monolithic assumptions, not yet an end-to-end benchmark win.

---

## E-ARCH-002 — Whole-system utility dominates local elegance
**Status:** SUPPORTED DESIGN RULE

Several experiments showed that:
- locally useful/compressive structure can still hurt search;
- individually weak candidates can be jointly useful;
- locally faster motifs may not repay recognition/dispatch overhead.

Design consequence:
> Structural changes must pay rent at the whole-system level.