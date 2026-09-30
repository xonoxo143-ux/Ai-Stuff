# Constraint + Information-Gain Logic v1 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Actual benchmark

After applying the all-labels-wrong constraint, two candidate worlds remain.

```text
action                  worst survivors
APPLES-labeled box      2
ORANGES-labeled box     2
MIXED-labeled box       1
```

The solver therefore chooses the MIXED-labeled box. Either APPLES or ORANGES as the observed fruit uniquely identifies the true assignment.

## Generalization

1,000 randomized variants per seed, three seeds: 100% correct optimal action.

## Method

Finite world enumeration + hard constraints + exact observation filtering + minimax/expected-survivor action selection.

## Scope

This is a reusable small constraint/information-gain solver, not a general natural-language logic engine.