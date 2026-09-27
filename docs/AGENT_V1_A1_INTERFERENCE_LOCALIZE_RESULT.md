# Agent v1-A1 interference localization result

**Date:** 2026-09-27  
**Commit tested:** `2ef73a5a3c22d4acb6d61662285ca77f946864ce`  
**Workflow run:** `36345363638`  
**Status:** complete

## Aggregate localization

At four lifetime checkpoints and three paired seeds, each checkpoint branched for one new family under:

```text
baseline
freeze private recurrent computation
freeze router/signatures
freeze workspace/communication
freeze shared input/output machinery
```

### Fixed-16

```text
intervention      old-damage protection   new-learning cost   positive protection
private           +0.00299                +0.01792            7/12
router            +0.00133                +0.00016            8/12
workspace         +0.00067                +0.00036            7/12
shared            -0.00096                +0.00335            4/12
```

### Sparse-64

```text
intervention      old-damage protection   new-learning cost   positive protection
private           -0.00063                +0.00529            4/12
router            +0.00104                +0.00836            7/12
workspace         +0.00015                +0.00316            4/12
shared            -0.00140                -0.00030            5/12
```

The unconditional means are hard to interpret because many new-family blocks improve old-family performance rather than damage it.

## Condition on actual destructive transitions

A protection intervention only has a clear meaning when the baseline branch causes positive old-family damage.

Observed damaging checkpoints:

```text
fixed16:   6 / 12
sparse64:  4 / 12
```

Among those events:

### Fixed-16

```text
intervention      mean protection   protected events   mean learning cost
private           +0.00720          6/6                +0.03109
router            +0.00025          4/6                +0.00028
workspace         +0.00135          5/6                +0.00064
shared            -0.00003          2/6                +0.00041
```

### Sparse-64

```text
intervention      mean protection   protected events   mean learning cost
private           +0.00387          4/4                +0.00206
router            +0.00139          2/4                +0.00563
workspace         +0.00244          3/4                +0.00657
shared            -0.00281          2/4                -0.00964
```

## Interpretation

The strongest causal fact is:

> When a sampled transition actually damaged old skills, preventing updates to private recurrent cell parameters reduced that damage in **10/10** observed cases.

That does **not** mean global private freezing is a good architecture.

For fixed16, all-private freezing prevented about 0.0072 old loss while sacrificing about 0.0311 of new-family learning on the same damaging transitions. It is therefore an effective but blunt stability intervention.

The next question becomes much narrower:

> Can the system protect only the private cells carrying old useful computation while leaving other cells free to learn?

If yes, the larger sparse bank gains a concrete possible role: extra uncommitted cells may preserve new-learning capacity after old-useful cells are protected.

This is still a diagnostic of the original developmental-ecology idea, not a commitment to a plasticity mechanism.
