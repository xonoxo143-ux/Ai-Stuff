# Grounded Percentage Algebra v1 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Result

Three seeds.

```text
learned verb semantics         exact
held-out generated problems    300/300 per seed
chatbot-v0 math_01             $100, exact
```

Benchmark response: `Original price: $100. Check: $100 × 0.8 × 1.2 = $96.`

## Method

Verb meanings were inferred from observed numeric transitions rather than supplied as direct lexical labels. Parsed percentage changes were compiled into multiplicative factors and the original value was solved by symbolic inversion.

## Scope

This covers a family of chained percentage transformations, not arbitrary mathematical language.