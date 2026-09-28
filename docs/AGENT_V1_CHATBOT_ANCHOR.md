# Agent v1 integration anchor — chatbot first

**Date:** 2026-09-28  
**Status:** standing integration priority

## Primary first embodiment

Agent v1's first integrated product target is a **chatbot**.

Conversation is the first environment:

```text
user input
    ↓
input representation
    ↓
sparse recurrent ecology
    ↓
internal computation
    ↓
response and/or tool action
    ↓
next conversational consequence
    ↓
continued lifetime learning
```

The first real integrated milestone is not locomotion or a sensorimotor benchmark.

It is a multi-turn conversational system where:

1. the ecology materially participates in choosing/computing the response;
2. state persists across turns;
3. experience changes later behavior;
4. lifetime learning does not require resetting/retraining from scratch;
5. the architecture's own organization matters causally to quality or cost.

## Do not cheat the integration

Do not attach a conventional language model that performs essentially all language reasoning while the ecology becomes decorative routing or memory.

Temporary adapters are allowed for bootstrapping and measurement, but the experiment must expose whether useful computation genuinely resides in the Agent v1 substrate.

## Language path

Before choosing a language representation/generation scheme, research existing non-Transformer and non-token-first approaches.

Do not assume conventional subword tokens are the permanent interface.

A deliberately constrained first conversational domain is acceptable if it gives the ecology real responsibility and measurable multi-turn learning.

## Future interfaces remain valid

Sensors, actuators, game control, robotics, or other environments are **not removed** from the architecture.

They are modular future interfaces:

```text
chat first
    ↓
tools / external actions
    ↓
optional game or sensorimotor adapters
```

A game may later be useful as a grounded developmental environment, but it is not a prerequisite for the first real Agent v1 chatbot.

## Current sequence

```text
replicate lifelong-learning mechanism
→ derive an online developmental rule
→ language representation/generation research
→ minimal conversational integration
→ multi-turn lifetime-learning test
```
