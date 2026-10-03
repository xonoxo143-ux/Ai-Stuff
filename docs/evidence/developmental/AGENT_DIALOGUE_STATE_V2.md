# Dialogue State v2 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Result

Three seeds.

```text
synthetic thread recovery      100% over 2,000 sequences/seed
Mara enter                     pass
role exit                      pass
intervening philosophy mode    analytic
Mara resume                    pass
brass-box recovery             pass
analytic leakage               none
```

## Developmental lineage

v0 unigram cue induction failed.
v1 learned multiword constructions and recovered threads but allowed an accidental one-token control cue to change mode.
v2 requires mode-changing operations to be supported by multiword constructions, eliminating that failure.

## Scope

This establishes dialogue-mode and thread-state control, not open-ended roleplay or analytical content generation.