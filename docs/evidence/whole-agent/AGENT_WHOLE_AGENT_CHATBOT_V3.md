# Whole-Agent Chatbot v3 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Result

Three seeds:

```text
perception success   5/13
automatic score      5/5
```

Passing turns: `math_01`, `logic_01`, `compression_01`, `compression_02`, `compression_03`.

## Components

- execution-grounded phrase→procedure learning;
- persistent compiled procedures;
- grounded percentage semantics + symbolic algebra;
- explicit logic-world enumeration + information-gain action selection;
- learned recurrent pointer/copy response realization.

## Production correction

The first v3 integration hit 5/5 but the long logic explanation exceeded a 256-step realization ceiling. The generation bound was increased and the entire benchmark rerun. The final response reached its intended EOS and remained 5/5 on all seeds.

## Scope

This closes only the objective automatically scored subset. Eight open-ended/manual turns remain unsolved and mostly do not yet reach a relevant capability.