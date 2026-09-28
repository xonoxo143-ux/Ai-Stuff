# Agent v1 integration anchor — chatbot first

**Date:** 2026-09-28  
**Status:** CURRENT integration priority  
**Current architecture:** see `AGENT_CURRENT.md`

## Primary first embodiment

Agent v1's first integrated product target is a **chatbot**.

Conversation is the first environment:

```text
user message
    ↓
language / representation machinery
    ↓
bounded active state + capability ecology
    ↓
selective composition of useful capabilities
    ↓
response and/or tool action
    ↓
next conversational consequence
    ↓
fast memory/relevance updates
    +
slower capability development when justified
```

The first real integrated milestone is not locomotion or a sensorimotor benchmark.

It is a multi-turn conversational system where:

1. the capability ecology materially changes what computation is used;
2. state persists across turns;
3. episodic/semantic memory changes later conversation without requiring every fact to become a weight update;
4. genuine capability learning can continue over a lifetime;
5. structural organization matters causally to quality and/or cost.

## Substrate neutrality

Do **not** assume:

- Transformer required;
- Transformer forbidden;
- tokens required;
- tokens forbidden;
- SSM/recurrent core required;
- a single representation must serve every capability.

The target is the best conceptual and engineering hybrid.

A Transformer or attention/SSM hybrid may be the strongest language spine.

Recurrent/SSM components may be strongest for persistent compact state.

Sparse learned memory may be strongest for large stored knowledge.

Code/tools may be strongest for exact capabilities.

The capability graph is allowed to contain all of them.

## Do not cheat the integration

A strong language model is allowed and may be central to language quality.

The failure mode is different:

> The ecology must not become decorative.

The integrated experiment should expose whether capability recruitment, memory boundaries, composition, developmental control, or promoted structure produces measurable quality/cost/continual-learning value beyond simply running the language model alone.

Always compare against the underlying language-system baseline.

## Developmental role

Agent v1's recurrent-cell experiments are not assumed to be the final language architecture.

They are testing developmental machinery:

- specialization;
- causal accountability;
- interference/forgetting;
- plasticity allocation;
- reserve capacity;
- reusable interaction motifs;
- promotion/pruning.

The successful mechanisms may later govern heterogeneous capabilities whose internal implementations differ radically from the experimental recurrent cells.

## Memory boundary

Keep separate:

```text
active state
episodic experience
semantic/world knowledge
capability/skill
```

Conversation should normally update episodic/semantic memory first.

Parametric or structural learning is for durable capability changes that earn their developmental cost.

## Future interfaces remain valid

Sensors, actuators, game control, robotics, and other environments are **not removed**.

They are modular future interfaces:

```text
chat first
    ↓
tools / external actions
    ↓
optional game / sensor / actuator adapters
```

A game may later supply grounded development, but is not a prerequisite for the first real chatbot.

## Parallel sequence

```text
TRACK A — DEVELOPMENT
destructive-update prediction
→ prospective plasticity control
→ reserve / motif development

TRACK B — CHATBOT
language-spine benchmark
→ capability contract + memory boundary
→ minimal multi-turn hybrid chatbot

A + B
→ lifelong hybrid chatbot
```
