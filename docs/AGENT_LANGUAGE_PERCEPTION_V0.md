# Agent language perception v0

**Date:** 2026-09-28  
**Status:** ACTIVE EXPERIMENT  
**Goal:** learn a bounded non-language state from raw English bytes.

## Why this experiment exists

The language-production probe established:

```text
bounded non-language state
→ language organ
→ English
```

The mirror boundary is:

```text
English
→ language perception organ
→ bounded non-language state
```

If both directions work, language can function as an input/output organ around cognition instead of being the only place cognition exists.

## Semantic target

The first probe uses an explicitly structured 16-logit state:

```text
person: 4-way
color:  4-way
animal: 4-way
place:  4-way
```

This representation is intentionally human-defined for the interface test.

It is **not** the proposed final Agent ontology.

The point is to test whether a small raw-byte encoder can recover compositional meaning under controlled distribution shift.

## Generalization split

Training and validation differ in two ways at once:

1. validation uses **held-out semantic combinations**;
2. validation uses **sentence templates never seen during training**.

This guards against passing by memorizing complete sentence strings or a single word order.

## First candidates

Roughly parameter-matched:

- unidirectional byte GRU;
- bidirectional byte GRU;
- byte Transformer encoder with a learned summary token.

Perception is not required to share the production architecture.

Unlike autoregressive production, perception can inspect the entire utterance.

## Fast local screen

At ~110k parameters and 200 updates, one seed:

```text
GRU encoder          ~30% exact states
Transformer encoder  ~63% exact states
```

At 100 updates, the fair bidirectional recurrent comparison gave:

```text
BiGRU                ~38% exact states
Transformer          ~57% exact states
```

The Transformer was also materially faster to train.

These are scratch results only.

## Rigorous gate

The GitHub workflow runs:

```text
3 architectures
× 3 seeds
× 200 updates
```

Primary metrics:

- exact latent-state recovery;
- per-slot accuracy;
- held-out-template breakdown;
- wall-clock training speed.

## Research interpretation

Semantic-parsing work has repeatedly shown that good surface behavior can conceal weak compositional meaning representations.

That is why this first perception test scores the recovered non-language state directly rather than judging a generated paraphrase.

## Next step

If the perception boundary survives replication:

1. connect perception and production around the same state;
2. test round-trip paraphrases;
3. replace some human-defined slots with learned continuous state;
4. test whether memory/capabilities can consume that state without translating it back to English first.
