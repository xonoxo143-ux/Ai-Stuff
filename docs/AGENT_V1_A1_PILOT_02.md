# Agent v1-A1 pilot 02 — multi-family correction

**Date:** 2026-09-26  
**Commit tested:** `ca4095375ac6fda4461d5f5b93a2b2a3d1caa250`  
**Workflow run:** `36258614443`  
**Experiences:** 500 paired experiences across seven multi-family regimes  
**Status:** suggestive capacity signal; replication required

## Overall result

| Control | Mean task loss |
|---|---:|
| fixed 16 / top-4 | 0.68952 |
| **fixed 64 / top-4** | **0.67917** |
| dense 64 | 0.70050 |

Sparse-64 improved on fixed-16 by about 0.01035 absolute loss (~1.5% relative to fixed-16).

Dense-64 was worse than both sparse systems.

## Where sparse-64 helped

Largest favorable sparse64 - fixed16 deltas occurred in:

- `mixed_return`: about **-0.05135**
- `family_expansion_b`: about **-0.03281**
- `foundation`: about **-0.02915**
- `return_with_decoy`: about **-0.01826**

Sparse-64 was worse in some earlier phases, especially `family_expansion_a`.

## Interpretation

This is the first sign that larger stored capacity with narrow activation may help in the revised lifetime world, particularly when later families appear and old structure is recombined.

It is not enough to advance to reserve recruitment.

One model/world seed can be noise or initialization luck. The next gate is paired multi-seed replication of fixed16, sparse64 and dense64 using the same world schedules within each pair.

A2 remains blocked until that replication establishes a reproducible developmental-pressure signal.
