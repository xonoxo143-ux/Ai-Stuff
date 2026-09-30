# Evidence Content Planner v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Scaling

Three seeds, 100 → 1,000 → 10,000 → 100,000 cold evidence facts.

```text
retrieved rows / complete query     4 throughout
active payload                       ~55–56 bytes
complete realization                 100%
100k SQLite store                    ~20.8 MB
median-scale lookup                  sub-millisecond
hot producer                         56,118 parameters
```

## Causal deletion

One required fact was deleted after a correct response while model parameters were held fixed.

```text
rows after deletion                  3
missing-evidence response exact      100%
deleted factual value leaked         0 cases
```

## Interpretation

The tested factual values genuinely lived in cold evidence rather than the hot recurrent realizer. Stored factual capacity grew three orders of magnitude while active evidence stayed fixed.

## Scope

This establishes sparse evidence-grounded content planning, not open-domain knowledge acquisition or relational/interpretive synthesis.