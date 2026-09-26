# Agent v1-A1 capacity-pressure audit

**Date:** 2026-09-26  
**Status:** running

The first two lifetime curricula did not establish reproducible marginal value for more than 16 stored cells.

The next test therefore stops guessing one "hard enough" world and measures the capacity boundary directly.

## Controlled family dynamics

Each family exposes a fixed-width 8-dimensional continuous context code.

Behind that public code is a deterministic family-specific recurrent target system:

```text
z_(t+1) = tanh(A_f z_t + B_f u_t + b_f)
y_t     = 4 tanh(w_f · z_t)
```

where the family-specific matrices are generated independently from the public code.

This gives each family genuinely different temporal dynamics while keeping:

- the public event interface width fixed;
- the active cell budget fixed at top-4 for sparse systems;
- the per-family exposure budget controlled.

## Sweep

Test:

```text
family count: 8, 16, 32, 64
controls: fixed16, sparse64, dense64
paired seeds: 3
```

The lifetime phases are:

1. foundation — first quarter of families;
2. expansion — first half available;
3. novel-only — second half dominates;
4. mixed-return — all families return.

The primary diagnostic is not whether 64 wins at one arbitrary setting.

It is whether a reproducible crossover appears as stored environmental diversity grows:

```text
small family count:
    fixed16 ≈ sparse64

larger family count:
    sparse64 < fixed16 loss
```

while sparse top-4 remains preferable to simply activating all 64.

If no crossover appears, the current recurrent cell substrate has not demonstrated a reason to recruit reserve capacity and A2 remains blocked.
