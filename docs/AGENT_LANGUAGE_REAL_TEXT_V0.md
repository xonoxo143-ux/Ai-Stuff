# Agent language real-text v0

**Date:** 2026-09-28  
**Status:** ACTIVE EXPERIMENT  
**Goal:** move surviving from-scratch language-production candidates from synthetic micro-English to a bounded real-language curriculum.

## What is and is not imported

Imported:

- training text from the TinyStories dataset.

Not imported:

- pretrained weights;
- tokenizer;
- model architecture;
- hidden states;
- teacher logits;
- another language model at inference time.

Both models start from random initialization.

## Models

First scale-up:

```text
GRU production organ          ~0.8M parameters
Transformer production organ  ~0.93M parameters
```

Both continue to use raw UTF-8 bytes and preserve the 16-dimensional external Agent-state conditioning channel.

## Corpus

The workflow streams only a bounded subset:

```text
train:      first 4,000 TinyStories examples
validation: first   400 TinyStories examples
```

The trainer then caps raw bytes again before training.

This is deliberately a small first screen, not an attempt to reproduce TinyStories training.

## Training gate

One seed, same byte corpus:

```text
800 updates
batch 8
sequence length 256 bytes
AdamW
CPU GitHub runner
```

Measurements:

- validation bits/byte;
- wall-clock training throughput;
- short greedy sample from "Once upon a time";
- checkpoint size/provenance.

## Why TinyStories

TinyStories was designed around a restricted vocabulary and simple short stories specifically to test how much coherent English small models can learn.

That makes it useful as a curriculum stage before broader web/book/code language.

## Decision rule

This screen does **not** select the final architecture.

It asks whether either surviving synthetic candidate still learns usefully when the language distribution becomes real.

If both produce only byte-level mush at this scale/budget, increase training/curriculum before increasing architectural complexity.

If one clearly dominates quality/cost, carry it forward while retaining the other only when it offers a distinct architectural advantage.
