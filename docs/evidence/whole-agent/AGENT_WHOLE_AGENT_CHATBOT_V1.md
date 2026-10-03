# Whole-Agent Chatbot v1 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Benchmark

`workspace/benchmarks/chatbot-v0.json`

## Result

Three seeds, identical result each seed:

```text
perception success   3/13
automatic passes    3/5
```

Passing turns: `compression_01`, `compression_02`, `compression_03`.

Responses:

```text
280
616
-8
```

The agent learned phrase→operation mappings from execution outcomes during development, compiled the first prompt into `DOUBLE → ADD3 → SQUARE → SUB9`, stored that procedure, and reused it on later turns.

## Comparison

Whole-Agent Chatbot v0: 0/13 perception, 0/5 automatic.
Whole-Agent Chatbot v1: 3/13 perception, 3/5 automatic.

## Remaining verified first failures

`math_01` and `logic_01` still fail before a relevant capability executes.
All manual/open-ended benchmark items still fail at perception.