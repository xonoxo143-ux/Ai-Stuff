# Agent Reasoning Amortization v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can an expensive successful reasoning episode be compiled into durable reusable computation so later encounters preserve capability while using materially less active computation?

## Setup

Deep functional problem classes were generated as compositions of the existing executable unary operation set.

First encounter:
1. breadth-first program search against a seven-probe behavioral specification;
2. candidate procedure validation on wider held-out inputs;
3. surviving candidate stored in a SQLite cold skill database.

Second encounter:
- exact behavioral skill lookup;
- direct execution on hit;
- synthesis fallback on miss.

No pretrained model or external compute service was used.

## Corrected three-seed replication

The first draft of this gate contained an accounting bug that reported zero repeat search even for skills rejected by validation. The metrics below are from the corrected implementation: rejected skills correctly fall back to search.

### Seed 0

```text
accepted skills                    38 / 40
cache hit rate                     95.0%
correct given cache hit           100%
first mean search expansions      392.825
repeat mean expansions              7.200
expansion reduction               54.56×
median planning → repeat latency  241.97× reduction
```

### Seed 100

```text
accepted skills                    37 / 40
cache hit rate                     92.5%
correct given cache hit           100%
first mean search expansions      328.475
repeat mean expansions             26.550
expansion reduction               12.37×
median latency reduction          240.46×
```

### Seed 200

```text
accepted skills                    38 / 40
cache hit rate                     95.0%
correct given cache hit           100%
first mean search expansions      322.275
repeat mean expansions             22.250
expansion reduction               14.48×
median latency reduction          166.66×
```

Novel classes had zero false cache hits.

## Failure

The seven input/output probes were not always sufficient to identify the intended function.

For rejected classes, search could produce a short program that matched every supplied example but differed on wider inputs.

This means the remaining error was not fixed by making compilation more permissive. The evidence itself was insufficient.

## Decision

Promote reasoning amortization as a developmental principle.

Do not promote fixed-probe validation as the durable verification rule.

The failure motivates Active-Probe Compilation v0.
