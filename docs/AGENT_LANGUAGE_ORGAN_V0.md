# Agent language organ v0

**Date:** 2026-09-28  
**Status:** ACTIVE EXPERIMENT  
**Goal:** build language machinery from scratch so language becomes an organ of Agent cognition rather than an imported pretrained brain.

## Architectural decision

Existing pretrained LLMs remain useful **controls and reference systems**.

They are no longer the presumed main construction path.

The main path now asks:

> What is the smallest trainable language subsystem that can perceive and produce useful English while allowing cognition, memory, tools, and development to live outside it?

## Why raw bytes first

The first experiment uses UTF-8 bytes directly.

This does **not** mean bytes have been chosen permanently.

Reasons to start here:

- no external tokenizer or fixed vocabulary is required;
- the representation boundary is simple and exact;
- token-free language modeling is already known to be viable;
- later learned chunking/patching can be tested against a byte baseline.

Relevant precedent includes TinyStories, MEGABYTE, MambaByte, Charformer, and BLT.

## External cognition seam

Every v0 model accepts:

```text
tokens
+
optional condition vector
→ byte logits
```

The 16-dimensional condition vector is deliberately small.

It is treated as a **persistent conditioning channel** available throughout language production, not merely as a one-time initial-state hint. A zero condition is defined to be neutral.

It exists to reserve a **non-language interface** through which the future Agent workspace/capability ecology can influence language production.

This is important:

```text
Agent state
→ latent condition
→ language organ
→ text
```

should be possible without serializing every internal thought into an English prompt.

## First three candidates

All are intentionally tiny and roughly parameter matched (~130k-150k).

### A — byte GRU

Two-layer recurrent baseline.

Purpose:
- test whether compact persistent recurrence is unusually effective at this scale;
- provide a fixed-state decoding baseline.

### B — byte Transformer

Two-layer causal Transformer.

Purpose:
- establish the training-parallel attention baseline;
- measure whether its faster training repays its weaker/stronger validation behavior.

### C — fixed-patch multiscale RNN

```text
bytes inside patch
→ local GRU
→ patch summary
→ slower global GRU
→ next patch local decoder
```

Purpose:
- test a crude fast/slow language hierarchy inspired by multiscale byte models.

This implementation is intentionally simple. A loss here rejects **this fixed-patch formulation**, not multiscale language in general.

## Fast local result

Container, one seed, synthetic held-out micro-English corpus, 160 updates:

```text
model          parameters   validation bits/byte   train time
GRU            ~148k        ~1.67                  ~11.1 s
Transformer    ~134k        ~2.62                  ~4.4 s
Patch RNN      ~152k        ~3.31                  ~12.8 s
```

Interpretation:

- the Transformer trained substantially faster;
- the GRU achieved much lower held-out byte loss at the fixed update budget;
- the first fixed-patch model was clearly poor;
- one seed on synthetic language is insufficient for promotion.

## Rigorous gate

GitHub workflow:

```text
.github/workflows/agent-language-organ-v0.yml
```

runs the same ~parameter-matched comparison over five model/training seeds.

Primary metrics:

- validation bits/byte;
- validation wins by seed;
- wall-clock training time;
- steps/second;
- parameter count.

The same workflow also runs a three-seed compositional conditioning probe.

In that probe, an evaluator supplies a 16-dimensional structured latent state describing a novel combination of name/color/animal/place. The language organ must generate the corresponding English sentence.

The local fair-interface check reached:

```text
GRU          64 / 64 held-out combinations exact
Transformer  64 / 64 held-out combinations exact
```

after 300 tiny updates.

This establishes that both candidate families can, in principle, act as a language **output organ** driven by non-language state.

No architecture is promoted until the replicated surface and conditioning tests complete.

## After the synthetic gate

The surviving model(s) move to a small real-language curriculum.

TinyStories is attractive for the first real-language stage because published results show coherent English emerging in models far below normal LLM scale.

The purpose is **not** to reproduce TinyStories rankings.

The purpose is to learn:

- how much language capacity our own organ needs;
- whether recurrence/attention/multiscale structure pays rent;
- how well external Agent conditioning can control production;
- when language knowledge begins to absorb cognition we would rather keep elsewhere.

## Kill / redesign rules

- If a simple recurrent model dominates, keep it until another mechanism earns complexity.
- If attention wins strongly once real data is used, use attention.
- If fixed patching remains poor, remove it rather than tuning indefinitely.
- If raw bytes become the bottleneck, test learned chunking before assuming BPE.
- If the language organ starts becoming the entire intelligence, strengthen the cognition/language interface instead of hiding the problem with scale.
