# Agent language roundtrip v0

**Date:** 2026-09-28  
**Status:** ACTIVE EXPERIMENT  
**Goal:** test the first closed language loop around a bounded non-language state.

## Structure

```text
held-out English paraphrase
        ↓
BiGRU perception organ
        ↓
4 × 4 semantic logits
        ↓
hard or soft 16-d bridge
        ↓
GRU production organ
        ↓
canonical English target
```

The test is synthetic and deliberately interpretable.

It is the first experiment where the language ears and mouth are evaluated as a coupled system.

## Why three bridge conditions

### Oracle state

Ground-truth semantic state is supplied to the producer.

This answers:

> Is the mouth trained well enough for the bridge test to mean anything?

### Hard predicted state

The perception argmax is converted to one-hot state.

This tests a discrete semantic bottleneck.

### Soft predicted state

The four slot probability distributions are concatenated directly.

This tests whether uncertainty-preserving state is easier for the producer to use than hard discretization.

## Metrics

For each bridge:

- exact teacher-forced output sequence;
- byte accuracy.

Also record:

- perception exact-state accuracy;
- training time.

Teacher forcing is intentional in v0.

It isolates the semantic bridge before adding autoregressive exposure errors.

A later gate will generate freely once the bridge itself is reliable.

## Failure interpretation

```text
oracle bad
→ producer is undertrained

oracle good, hard/soft bad
→ perception or bridge is the bottleneck

soft > hard
→ preserving uncertainty helps

hard > soft
→ producer currently expects discrete capability state

hard/soft ≈ perception exact
→ junction adds little extra damage
```

## Current baselines

- perception: plain BiGRU, chosen from the replicated perception gate;
- production: micro GRU, chosen because the semantic-conditioning probe already reached 64/64 held-out combinations across three seeds.

This does not imply those architectures are permanent.
