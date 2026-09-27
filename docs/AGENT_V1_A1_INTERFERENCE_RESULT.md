# Agent v1-A1 direct interference result

**Date:** 2026-09-27  
**Commit tested:** `297c654ecd09361f028fe20b287d9da466080871`  
**Workflow run:** `36344687464`  
**Pairs:** 3 per family count  
**Status:** forgetting is real; larger sparse storage reduces it in some regimes, but with a learning-speed tradeoff

## Primary result

Mean average forgetting:

```text
families    fixed16     sparse64     64 - 16      64 wins
16          0.06232     0.02664      -0.03568     3/3
32          0.03908     0.03688      -0.00220     2/3
64          0.07345     0.04705      -0.02640     3/3
```

Lower is better.

The 16- and 64-family settings therefore show reproducible lower forgetting with a 64-cell sparse bank while keeping top-4 active compute.

## Post-learning retention change

Mean:

```text
families    fixed16      sparse64
16          +0.03307     +0.00702
32          -0.00331     +0.00328
64          +0.02455     +0.00871
```

Positive means an old family is worse at the end than immediately after its own training block.

The 32-family regime does not show a clean retention advantage; the best-after-learning forgetting score there is largely fluctuation around later improvements/regressions.

## New-family learning tradeoff

Mean one-block learning gain:

```text
families    fixed16      sparse64      64 - 16
16          0.03692      0.02096       -0.01596
32          0.02535      0.01670       -0.00865
64          0.03472      0.02208       -0.01263
```

Higher is better.

So the 64-cell ecology is not simply "better at retention." It also adapts less per new family in this one-pass lifetime.

This creates a real stability/plasticity ambiguity:

```text
more stored cells
→ less backward damage in some regimes
but
→ less immediate learning gain
```

## Final held-out loss

```text
families    sparse64 - fixed16    64 wins
16          -0.01825              2/3
32          -0.04927              2/3
64          -0.01575              3/3
```

Despite the lower learning gain, sparse64 ends with lower mean held-out loss on average at all three family counts and wins all 3 pairs at 64 families.

That is useful, but it does not identify *why*.

## Structural correlations

The preregistered simple mechanism did **not** survive cleanly.

Within-run Pearson correlations between old-family forgetting and:

- future routing-mass overlap;
- future private-cell update exposure;

were mostly negative or inconsistent.

Examples at 64 families:

```text
fixed16 collision correlation:
-0.102, -0.123, -0.125

sparse64 collision correlation:
-0.163, -0.121, -0.423

fixed16 private-update exposure correlation:
-0.111, -0.106, -0.171

sparse64 private-update exposure correlation:
-0.208, -0.161, -0.329
```

Therefore the naive claim

```text
more cell reuse / more update exposure
→ more forgetting
```

is not supported by this diagnostic.

These correlations are not causal and are confounded by family difficulty and usage, but they are enough to stop treating simple cell collision as the explanation.

## Decision

Do **not** promote reserve recruitment or adaptive plasticity yet.

The next gate is causal localization of the stability/plasticity tradeoff.

At selected lifetime checkpoints, clone the exact model + optimizer state and train one additional family under one-step interventions:

```text
all trainable
freeze private recurrent cell computation
freeze router/signatures
freeze workspace/communication
freeze shared input/output machinery
```

For each intervention measure:

```text
old-family damage prevented
vs
new-family learning sacrificed
```

This preserves the Agent v1 trunk while identifying which subsystem actually carries destructive or stabilizing updates.
