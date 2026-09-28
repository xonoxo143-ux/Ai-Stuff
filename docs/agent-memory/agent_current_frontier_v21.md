# Agent Current Frontier

**Version:** 2.1  
**Date:** 2026-09-28  
**Role:** shortest current-state file. Update this after every meaningful experiment cycle.

## Current state

The project has two active tracks.

### Track A — developmental mechanism

Established:
- destructive forgetting exists;
- destructive private-cell updates can be localized post hoc;
- localization replicated on fresh seeds;
- simple one-shot prospective per-cell predictors are weak.

Current uncertainty:

> Is destructive interference predictable from **update trajectory/history or interactions**, or is the better solution to route new learning into spare capacity rather than predict danger precisely?

Next high-information experiment should distinguish at least these explanations:

1. **trajectory/history hypothesis**  
   Danger accumulates across a sequence of updates and cannot be inferred from one gradient snapshot.

2. **interaction hypothesis**  
   Destructive effects depend on combinations of cell updates, so per-cell pre-update scores are structurally insufficient.

3. **spare-capacity hypothesis**  
   Avoiding overlap may matter more than predicting exactly which old parameters are vulnerable.

Do not add a complex online plasticity controller before one of these earns support.

### Track B — chatbot integration

Goal:
Build the first hybrid chatbot bottom-up without waiting for every developmental mechanism to be finished.

Next steps:
1. choose/benchmark compact language-spine candidates;
2. define the capability contract;
3. define active/episodic/semantic/capability memory boundaries;
4. build a minimal multi-turn shell;
5. add one non-language capability;
6. compare against the language-only baseline;
7. then integrate developmental machinery where it has a clear job.

## Development loop

```text
READ CURRENT DOCS
→ identify weakest assumption
→ RESEARCH prior solutions/failures
→ define smallest discriminating experiment
→ IMPLEMENT
→ run fast tests / ablations / combinations
→ FALSIFY / COMPARE
→ integrate only what survives
→ UPDATE docs + evidence + frontier
→ periodic end-to-end prototype
→ repeat
```

## Immediate documentation rule

After each cycle:
- update this file first;
- update Evidence Ledger only for durable results;
- update Decision Ledger only if architecture changed;
- save exact experiment/result separately;
- never append another competing "current" section to the archive.