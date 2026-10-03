# Agent Developmental Nursery v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can a very small local system author reusable executable computation from experience, preserve alternative developmental paths, and use the resulting primitives to solve novel compositions that are unavailable under the same active program-depth constraint?

## Environment

The experiment ran entirely in the ChatGPT local container using Python 3.13 standard library only.

Observed container budget during the run:
- 5 CPU cores;
- about 5.8 GiB RAM;
- no external model runtime used;
- no pretrained model used by the nursery.

## Generation-0 substrate

The initial computational language contained nine stack-machine instructions:

`DUP ADD MUL PUSH1 PUSH2 NEG ABS SUB SWAP`

The nursery could:
1. synthesize short programs from input/output behavior;
2. retain solved traces;
3. mine candidate instruction sequences;
4. promote a sequence into a one-token macro primitive;
5. branch genomes into an archive;
6. evaluate descendants on separate composition tasks;
7. hold out a final task set not used for promotion.

## First curriculum

Three hidden reusable operations occurred across developmental tasks.

The system was not given their names or boundaries.

After three developmental generations it promoted:

```text
M1 = DUP MUL PUSH1 ADD
M2 = DUP ADD PUSH1 ADD
M3 = PUSH2 SUB ABS
```

Final untouched compositions:

```text
fixed primitive library   0 / 5
evolved genome            5 / 5
```

The evolved programs used 4–5 active macro-level tokens for target computations whose generating base programs were approximately 15–19 primitive instructions long.

Important: in v0 the macros are interpreted composites, so this primarily reduces search/program-description depth and active dispatch structure; it does not yet establish proportional primitive-FLOP reduction.

## Stress variation

Three different motif sets were tried.

Initial developmental law:

```text
set 0   5 / 5
set 1   5 / 5
set 2   1 / 5
```

The failed set was retained as evidence rather than tuned away.

## Failure analysis

The initial learner proposed new primitives mainly by retrospective compression/frequency.

A useful operation in set 2 occurred in several behaviorally related forms, while shorter/frequent fragments dominated the candidate queue. The complete operation therefore did not receive a prospective validation trial.

This failure is consistent with two external research warnings:
- syntactic library learning can miss abstractions hidden by equivalent program variation;
- retrospective compression need not select the abstraction with greatest future usefulness.

## Research-backed revision

v0.3 changed the developmental law:

1. frequent/compressible subprograms remain candidates;
2. each compact whole solved procedure can also become a candidate even if it occurred once;
3. promotion is decided by separate prospective validation;
4. parent selection preserves structurally different archive branches instead of only current top score.

No missing target operation was manually inserted.

Previously failing set:

```text
before revision   1 / 5
after revision    5 / 5
```

Promoted procedures:

```text
DUP ADD PUSH1 SUB ABS
DUP MUL NEG
PUSH1 SUB ABS
```

## What survived

- executable self-authored computational genome;
- archive/open-ended stepping stones rather than latest-only hill climbing;
- empirical promotion;
- prospective whole-skill proposals plus retrospective compression;
- local/container execution as a viable development environment.

## What remains unproven

- open-domain cognition;
- language integration;
- large-scale continual learning;
- neural/latent module invention;
- high reasoning quality per FLOP;
- sparse addressing when the cold store becomes large;
- representation-language invention.

## Next discriminating gate

Scale dormant stored capabilities by 10× and 100×.

Measure:
- held-out capability;
- number of stored modules;
- number of modules inspected per thought;
- active program/module count;
- bytes moved;
- wall-clock;
- synthesis/search expansions;
- causal ablation effect.

The critical question is whether capability can grow substantially faster than active computation.

If global search cost grows with total storage, the next research/build target becomes learned or hierarchical addressing rather than more library growth.
