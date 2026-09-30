# Whole-Agent Chatbot v4 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Result

Three seeds:

```text
meaningful/perceived turns   7/13
automatic checks             5/5
manual surrogate checks      2/2
```

Newly covered manual turns are `ambiguity_01` and `epistemic_01`.

## Architecture delta

The shared uncertainty regulator produces structured clarification/evidence plans. A homegrown recurrent pointer/copy producer realizes six response-plan types: number, math, logic, clarify, epistemic, and fail.

## Scope

Six benchmark turns remain without adequate open-ended content capability. Dialogue thread/mode state is separately passed by Dialogue State v2; the next bottleneck is evidence/knowledge content planning and flexible realization.