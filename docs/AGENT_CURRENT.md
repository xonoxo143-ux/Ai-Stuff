# Agent — Current Architecture and Frontier

**Date:** 2026-09-28  
**Status:** authoritative current orientation for the Agent line  
**Branch:** `experiment/agent-v1-developmental-ecology`

> If another Agent document disagrees with this file about what is currently believed, treat that document as historical unless this file explicitly promotes it.

## 1. Product anchor

Build a high-quality local conversational agent, no larger than roughly 32 GB as a finished runnable system, that can store broad capability while spending only the computation useful for the current moment.

Short form:

```text
STORE BROADLY
ACTIVATE NARROWLY
DEVELOP SELECTIVELY
```

The first integrated embodiment is a **chatbot**.

Game control, sensors, robotics, and other environments remain valid future interfaces, not current prerequisites.

## 2. Current conceptual direction

The target is **not** a pure recurrent agent, pure Transformer, pure state-space model, pure symbolic system, or pure skill graph.

The current direction is a heterogeneous capability ecology:

```text
human language / tools / future sensors
                │
                ▼
      representation + language machinery
                │
        ┌───────┴────────┐
        │                │
 attention/Transformer   recurrent/SSM state
 or hybrids              and continuity
        │                │
        └───────┬────────┘
                │
       bounded shared state
                │
      capability recruitment
                │
 ┌──────────────┼─────────────────┐
 │              │                 │
learned      explicit          sparse / learned
specialist   code/tool         memory capability
 │              │                 │
 └──────── temporary composition ─┘
                │
        response / tool action
                │
              trace
                │
        developmental layer
                │
 causal credit / update risk / promotion
 compilation / pruning / replacement
                │
        persistent capability graph
                ↺
```

No one substrate is required to implement every capability.

A capability may internally be:

- Transformer/attention machinery;
- recurrent or state-space machinery;
- sparse memory;
- deterministic code;
- a tool wrapper;
- a learned specialist;
- an exact or distilled composition;
- another validated implementation.

The common abstraction is the **capability contract**, not the internal substrate.

## 3. Functional division currently worth testing

This is a hypothesis map, not a fixed hierarchy.

### Language / relational processing

Transformer-style attention or an attention/recurrent hybrid is a strong candidate for high-quality language and precise relational manipulation.

There is no anti-Transformer requirement.

### Persistent active continuity

Recurrent or state-space machinery is a strong candidate where fixed-size state, temporal continuity, and cheap repeated updates matter.

### Large stored knowledge

Sparse/addressable memory should be tested separately from active cognition. Most new conversational facts should not automatically become weight updates.

### Exact capabilities

Code and tools should be used where they are more reliable or cheaper than learned approximation.

### Capability-level cognition

The ecology decides which capabilities participate in the current thought/task, how they communicate, and when more computation is worth spending.

Sparse recruitment is primarily a **capability/thought-scale** hypothesis, not a requirement that every low-level language operation be sparse.

### Development

Slow learning changes what the system can do economically in the future:

- specialization;
- routing/relevance;
- new reusable capability;
- interaction motif;
- compilation;
- replacement;
- retirement;
- plasticity allocation.

## 4. Memory is not one thing

Keep these conceptually separate:

```text
ACTIVE STATE
what matters now

EPISODIC MEMORY
what happened

SEMANTIC / WORLD MEMORY
what the system currently treats as true/probable

CAPABILITY MEMORY
what the system has learned how to do
```

A useful development path is often:

```text
"I remember solving this"
        ↓
"I know how to do this"
```

Facts should generally enter episodic/semantic memory first.

Weight or structural changes should be reserved for learning **capability**, representation, routing, or reusable computation when justified.

## 5. Multi-timescale learning

The architecture increasingly points toward learning itself being routed across timescales.

```text
FAST
active/recurrent state
ordinary cognition

MEDIUM
contextual organization
recruitment, gain, temporary coalitions
relevance/reliability updates

SLOW
parametric capability change
structural promotion/pruning
plasticity consolidation
```

The current Agent v1 interference experiments are testing the slow-learning problem in isolation.

## 6. Experimental evidence carried forward

### Agent v0

Supported:

- sparse top-k execution can save real wall-clock work;
- shallow recurrent thought can be useful;
- learned cells can acquire reproducible causal roles;
- useful computation can be relational between cells;
- a causally useful pair motif can be compiled into a smaller/faster reusable unit;
- local speedup alone is insufficient for promotion if whole-agent savings do not pay rent.

### Agent v1-A1

Established so far:

- larger static capacity did not produce a simple robust capacity crossover;
- lifelong sequential training produces measurable interference/forgetting;
- private recurrent updates can causally contribute to destructive forgetting;
- routing frequency does not identify which cells deserve protection;
- old-task execution importance also does not reliably identify destructive updates;
- **post-hoc destructive-update localization replicated on fresh seeds**.

Fresh-seed replication:

```text
fixed16 top-4 destructive updates:
  beat matched random in 10/11 destructive events
  captured ~95.4% of positive destructive-attribution mass

sparse64 top-4:
  beat matched random in 8/12
  captured ~96.9%
```

Strongest current mechanistic statement:

> A relatively small subset of private-cell parameter updates disproportionately causes forgetting in the current benchmark.

This is post-hoc evidence, not yet an online learning rule.

## 7. Current experiment

`AGENT_V1_A1_UPDATE_PREDICTORS.md` tests whether signals available before/during learning can predict the destructive updates later identified by reversion.

Candidate predictor families include:

- new-gradient magnitude;
- old usage × new-gradient magnitude;
- old output sensitivity × new gradient;
- old-loss sensitivity × new gradient;
- old/new gradient conflict.

The result decides whether a prospective plasticity/gating mechanism has earned a test.

## 8. Current integration direction

Do **not** interpret Agent v1's recurrent cells as the final chatbot substrate.

Agent v1 is the experimental developmental tissue.

The integrated chatbot direction is:

```text
strong language machinery
        +
persistent recurrent/SSM continuity where useful
        +
sparse/addressable memory
        +
explicit tools/code
        +
learned specialists
        +
capability-level sparse composition
        +
multi-timescale developmental control
```

Transformers, tokens, SSMs, recurrence, symbolic computation, and learned memory are all implementation variables.

Use whichever mechanism wins at its scale.

## 9. Near-term build sequence

Two tracks may now proceed without contaminating each other.

### Track A — developmental mechanism

```text
destructive-update predictor
→ prospective plasticity/gating test
→ reserve-development pressure
→ motif/promotion lifecycle
```

### Track B — chatbot substrate/interface

```text
benchmark candidate language spines
→ define capability contract / shared-state boundary
→ separate active, episodic, semantic, capability memory
→ minimal multi-turn chatbot
```

Then:

```text
Track A + Track B
        ↓
first hybrid lifelong chatbot
```

## 10. Open decisions

Still experimental:

- exact language spine;
- role and granularity of Transformer attention;
- role and granularity of SSM/recurrent state;
- tokenizer / byte / patch representation;
- memory implementation;
- capability granularity;
- routing mechanism;
- shared-state format/bandwidth;
- online plasticity predictor/gate;
- reserve recruitment;
- physical model placement and cache strategy;
- whether sparse activation wins on actual target hardware.

## 11. Non-negotiable evaluation rule

Architectural elegance does not count.

A mechanism survives only if it improves the whole system after:

- quality;
- wall-clock cost;
- memory movement;
- routing/recognition overhead;
- storage;
- developmental cost;
- maintenance cost

are counted.

> Structural changes must pay rent.
