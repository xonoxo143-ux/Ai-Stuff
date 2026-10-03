# Agent Integrated Developmental Lifetime v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can a growing self-authored cold skill library accumulate roughly two orders of magnitude more capability without forcing proportional growth in active reasoning, retrieval, or payload movement?

## Integrated mechanism

Each durable skill consists of:
- a behavioral/effect key;
- a compiled executable program;
- a compact active-falsification certificate;
- a 4 KiB cold payload stored on disk.

Inference:
1. use the initial behavioral goal signature as the coarse address;
2. retrieve only matching cold-store rows;
3. execute the skill's discriminating certificate probes;
4. on match, page the one capability payload and execute;
5. on no match, treat the problem as novel and perform expensive identification.

Novel identification uses the bounded 21,845-program hypothesis space from Active-Probe Compilation v0.

## Scaling

Skill-library stages:

```text
32
320
3,200
```

Cold bytes include SQLite index/storage plus one 4 KiB payload per skill.

Three query-sampling replications were run at each stage with 160 familiar and 160 novel test queries.

## Replicated result

From 32 to 3,200 skills:

```text
skill-count growth                 100×
mean cold-store byte growth       93.74×
mean familiar-row growth           1.43×
mean familiar-query growth         1.79×
mean mixed active-work growth      1.27×
selected payload bytes/query       4,096 constant on hits
```

All 9 stage × replication combinations:

```text
familiar hit rate                  100%
familiar correctness given hit    100%
novel false hits                     0
```

The standardized mixed-work metric used 80% familiar and 20% novel tasks so its workload composition did not improve merely because the library became larger.

Per-replication 32→3,200 mixed-work growth:

```text
seed 42    1.319×
seed 142   1.315×
seed 242   1.180×
mean       1.272×
```

## What this supports

In this bounded computational world:

> durable capability can grow much faster than the active work required for a thought.

The combination of effect-addressed lookup plus falsification certificates prevents a large library from becoming either a global-scan cost or an unsafe cache.

## What it does not support

- no claim of equivalent scaling for open-domain natural-language cognition;
- no proof that the behavioral address can be constructed from unconstrained language;
- no demonstration of neural module paging;
- no claim that SQLite/hash lookup is the final addressing system;
- no claim that 4 KiB payloads approximate realistic skill sizes;
- no whole-agent conversational behavior.

## Decision

Promote the developmental pattern; stop growing the toy domain.

Next integrated gate: Whole-Agent Closure using the existing homegrown perception/state/cognition/production stack, with the nursery mechanisms available as the way durable skills can later be acquired and reused.
