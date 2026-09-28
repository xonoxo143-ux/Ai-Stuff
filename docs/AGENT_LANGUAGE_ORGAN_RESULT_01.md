# Agent language organ result 01 — replicated synthetic gate

**Date:** 2026-09-28  
**Workflow run:** `36394549359`  
**Status:** RESULT

## Surface byte modeling

Five seeds, 160 updates, ~parameter-matched models:

```text
                 mean bits/byte   wins   mean train time
GRU                 2.002         5/5        12.85 s
Transformer         2.606         0/5         5.08 s
Patch RNN           3.381         0/5        14.78 s
```

Interpretation:

- the GRU learned the synthetic held-out byte distribution better at the fixed update budget on every seed;
- the Transformer trained about 2.5× faster;
- the first fixed-patch multiscale formulation was substantially worse in both quality and speed.

Decision:

> Drop the current fixed-patch RNN from the main path. Preserve multiscale language as an open family, but do not tune this formulation merely to rescue it.

GRU and Transformer both survive into later tests.

## Non-language state → English

Three seeds, 300 updates.

Both surviving architectures achieved:

```text
64 / 64 held-out semantic combinations exact
slot accuracy: 100%
```

on every seed.

This establishes, inside the controlled synthetic task:

> A small language organ can express novel combinations of bounded non-language state without receiving that state as prompt text.

This does not establish open-domain language ability or a final internal representation.

## Architectural consequence

Do not require the same model family to implement both language perception and language production.

Production now has two surviving candidates with a real tradeoff:

- GRU: better synthetic data efficiency at fixed updates;
- Transformer: substantially faster training.

The perception side is tested separately.
