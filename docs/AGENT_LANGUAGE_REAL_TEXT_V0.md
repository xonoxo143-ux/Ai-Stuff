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


## First completed run

Workflow `36436244279`, seed 101:

```text
GRU
  parameters: 800,640
  validation: 1.659 bits/byte
  train time: 133.1 s

Transformer
  parameters: 927,872
  validation: 2.610 bits/byte
  train time: 82.8 s
```

Greedy GRU sample after only 800 updates:

```text
Once upon a time there was a little girl named Lily.
She was so happy and said the bird was so happy.
The bird was so happy and said the...
```

The sample is repetitive and shallow but already recognizably grammatical English.

The Transformer sample remained mostly malformed at this update budget.

Interpretation:

- the synthetic GRU quality advantage survived the first real-text screen;
- the Transformer retained a substantial training-throughput advantage;
- one seed is not enough to treat the gap as settled.

The workflow now repeats the exact screen on seeds 101, 202, and 303 before either model is scaled further.
