# Agent Runtime v0 — Hybrid Capability Foundation

**Date:** 2026-09-28  
**Status:** first executable chatbot-integration foundation  
**Scope:** runtime shell only; not yet an intelligent language system

## Purpose

This is the first bottom-up implementation step toward the hybrid chatbot described in `docs/agent-memory/agent_current_frontier_v21.md`.

The runtime deliberately does **not** choose the final language architecture.

Instead it creates a lightweight boundary in which learned models, deterministic code, memory, tools, and later promoted composites can coexist without one implementation becoming the architecture by accident.

## Package boundary

`agent_runtime` is separate from `agent_ecology`.

That is deliberate.

The runtime shell has no required PyTorch dependency. The current recurrent ecology is an experimental developmental substrate that can later be attached as a capability.

This keeps:

```text
chatbot runtime
!=
current developmental experiment
```

## First common contract

A capability exposes:

```text
offer(context)
→ relevance
→ estimated cost
→ confidence
→ optional tags

run(context)
→ bounded public messages
→ active-state updates
→ semantic-memory updates
→ measured cost
→ success/error
```

The current `utility_hint` selection rule is intentionally primitive:

```text
relevance * confidence - estimated_cost
```

It is scaffolding, **not** a claim that this is the final router.

## Memory boundaries

The initial in-memory backend keeps separate:

- active state;
- episodic events;
- semantic/world memory;
- capability usage/cost history.

This is the first executable enforcement of the project rule that ordinary remembered facts must not automatically become parametric learning.

## Composer boundary

The runtime currently has one required `COMPOSER` capability.

The included `EchoComposer` is test-only.

A future compact Transformer, attention/SSM hybrid, recurrent language model, or other language spine can implement the same public contract.

A contributor failure is recorded as trace data rather than killing the turn.

## Trace

Every turn records:

- offers;
- selected/non-selected capabilities;
- estimated relevance/cost;
- measured cost;
- latency;
- success/error;
- final response.

This gives causal/provenance hooks before real model complexity is added.

## Test-only contributors

Two tiny contributors exist only to exercise boundaries:

- `ArithmeticCapability` — deterministic exact arithmetic;
- `RememberCapability` — explicit semantic-memory write.

They are not intended as the final tool/memory interfaces.

## Local scratch result

Before repository integration:

```text
8 focused tests passed
20,000-turn pure shell smoke: ~10.6 us/turn
mixed 5,000-turn x3 benchmark:
  median ~11.7 us/turn
```

These numbers measure only Python orchestration, not a model.

They establish that the initial shell overhead is negligible relative to realistic language inference.

## Next integration gate

Do not make the router smarter yet.

The next useful step is to attach **replaceable language-spine adapters** and benchmark candidate backends through this same runtime.

The hybrid must always be compared against the language spine running alone.

After the language boundary is real:

1. add persistent memory backend(s);
2. add one external capability;
3. test whether recruitment changes quality/cost;
4. integrate developmental mechanisms only where they have an earned job.


## First durable memory backend

`SQLiteAgentMemory` provides a stdlib-only persistent backend for:

- active state;
- episodic events;
- semantic/world memory;
- capability call/success/cost history.

The backend resumes the runtime turn counter from durable episodes, so a process restart does not reset conversational chronology.

Values are currently required to be JSON-serializable. That is an explicit v0 boundary, not a claim that the final memory representation must be JSON.

The backend exists to enforce a key architectural distinction in executable form:

```text
remembering conversational information
!=
changing model weights
```


## Selective semantic retrieval

The runtime now has a first replaceable semantic-memory retriever.

`SemanticRetrievalCapability` sits between stored semantic memory and the language composer.

Its current backends are deliberately cheap:

- token-overlap for the in-memory test backend;
- SQLite FTS5 shortlist + lexical overlap for durable memory.

The language composer can set `max_semantic_items=0` so stored memory is not automatically dumped into the prompt.

The intended production shape is:

```text
large semantic store
        ↓
retrieval capability
        ↓
small bounded memory report
        ↓
language / reasoning capability
```

Dense or hybrid retrieval remains an experimental replacement, not a prerequisite.
