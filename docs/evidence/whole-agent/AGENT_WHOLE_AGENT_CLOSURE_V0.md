# Whole-Agent Closure v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Gate

Three-seed end-to-end homegrown conversational loop with persistent restart.

## Result

```text
seed 0     7/7 exact
seed 1     7/7 exact
seed 2     7/7 exact
all seeds  PASS
```

Producer size: 47,396 parameters.
Producer training: 500 updates, approximately 3.6–3.7 seconds per seed on GitHub CPU.

Every response-state scaffold was generated exactly by the learned autoregressive pointer/copy GRU.

The runtime and SQLite memory object were recreated after turn 4; only the durable database file remained. Later retrievals and overwrite state were correct.

## Architecture

```text
raw bytes
→ developmental construction grammar
→ typed state
→ AgentRuntime + SQLite memory
→ response state
→ homegrown pointer/copy GRU
→ raw bytes
```

No pretrained/external LLM is present in the inference path.

## Scope

This proves self-contained conversational plumbing in a narrow controlled language regime.
It does not prove broad language understanding, open-domain knowledge, flexible reasoning, roleplay, coding ability, or broad response generation.

## Next gate

Unmodified `chatbot-v0` mixed-domain benchmark with layer-level failure tracing.