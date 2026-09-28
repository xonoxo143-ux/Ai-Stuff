# Agent language perception result 02 — slot-query refinement

**Date:** 2026-09-28  
**Workflow run:** `36436906318`  
**Status:** NEGATIVE REFINEMENT RESULT

## Three-seed means

```text
model             exact state   slot accuracy
plain BiGRU          72.0%          91.6%
attentive BiGRU      64.6%          89.9%
Transformer          36.5%          77.9%
GRU                  36.3%          75.9%
```

The attentive BiGRU added four learned semantic-slot queries over the recurrent sequence.

It did not beat the simpler final-state BiGRU on any aggregate quality metric.

## Decision

Drop the slot-query refinement.

Do not add readout complexity merely because a single scratch seed looked better.

Plain BiGRU remains the perception quality baseline for the next integration gate.
