# Agent v1-A1 destructive-update reversion result

**Date:** 2026-09-27  
**Commit tested:** `9f22573d48c7fec654288f8c098766aafba18a09`  
**Workflow run:** `36362910401`  
**Status:** promising mechanistic signal; fresh-seed replication required

## Question

After a new-family block damages old skills, can we identify the private-cell **updates** responsible for that damage by reverting them one cell at a time?

This differs from previous diagnostics:

- routing usage asked which cells were used;
- execution lesions asked which cells were important for performing old skills;
- update reversion asks which parameter changes actually caused the forgetting.

## Triggered events

```text
fixed16:  6 / 12 checkpoints
sparse64: 6 / 12 checkpoints
```

Mean baseline old-family damage on those triggered events:

```text
fixed16:  +0.008365
sparse64: +0.004332
```

## Independent-stream top-k result

Scores were ranked on held-out stream 2 and protection was measured on independent stream 1.

### Fixed-16

```text
k    top protection   random protection   top>random   positive-score mass   learning cost
1    +0.001485        +0.000895           4/6          65.7%                 +0.003609
2    +0.001707        +0.000244           5/6          89.0%                 +0.003658
4    +0.001790        +0.000780           5/6          99.3%                 +0.004150
8    +0.002379        +0.001467           5/6         100.0%                 +0.005334
```

### Sparse-64

```text
k    top protection   random protection   top>random   positive-score mass   learning cost
1    +0.000576        +0.000001           4/6          57.7%                 +0.000743
2    +0.000687        ~0                  4/6          73.9%                 +0.000847
4    +0.000904        -0.000002           4/6          89.8%                 +0.001086
8    +0.000912        +0.000355           3/6          98.4%                 +0.001278
```

## Interpretation

This is the first cell-selection diagnostic in v1 where the selected set consistently beats a matched random set on an **independent evaluation stream**.

The strongest preliminary statement is:

> Destructive private-cell updates appear to be sparse enough to identify post hoc.

That does **not** yet imply an online agent can predict those updates before observing their later damage.

It also does not yet establish that sparse64 has a better stability/plasticity frontier. Sparse64 shows lower absolute damage and substantially lower learning cost for top-k reversion, but the event mix differs and some sparse64 events have very small or unstable reversion effects.

## Reporting correction

The original summary requested widths:

```text
1,2,4,8,16,32
```

For fixed16, width 32 clips to all 16 cells. The original summary therefore duplicated the effective width-16 condition and reported 12 observations there.

Raw measurements at widths 1,2,4,8 are unaffected.

The implementation is corrected to deduplicate effective widths before evaluation.

## Gate

Do not turn post-hoc reversion into a developmental mechanism yet.

Next:

1. fresh world/model seeds;
2. same family count, checkpoints, training schedule;
3. widths 1,2,4,8 only;
4. verify top destructive-update sets beat random sets;
5. compare protection/new-learning tradeoff between fixed16 and sparse64.

If this fails on fresh seeds, the mechanism signal was trajectory-specific.

If it replicates, the next problem becomes **online prediction/gating of destructive updates**.
