# Agent v1-A1 pilot 01 — single-family world falsification

**Date:** 2026-09-26  
**Commit tested:** `5acdd29a4d0bb595a521446f9445d8ccd8870e8a`  
**Workflow run:** `36258304871`  
**Experiences:** 500 paired experiences across all seven original regimes  
**Status:** useful negative result; world design revised before A2

## Result

Mean smooth-L1 task loss:

| Control | Mean loss |
|---|---:|
| fixed 16 / top-4 | **0.80033** |
| fixed 64 / top-4 | 0.80426 |
| dense 64 | 0.82184 |

The differences are small, but there is no evidence here that extra stored capacity helps. Fixed-16 was slightly best.

## Interpretation

Do **not** read this as evidence that 16 cells are inherently superior.

The pilot exposed a more basic issue: the A0 world was still one scalar register-machine task family with hidden modifiers. Agent v0's closeout explicitly required a richer multi-family controlled curriculum before v1.

Therefore:

- do not implement reserve recruitment yet;
- treat this pilot as a falsification of the first A0 world as a sufficient developmental-pressure test;
- preserve the deterministic lifetime/replay machinery;
- replace the one-family task stream with visible multi-family contexts plus hidden regime/interactions;
- rerun the same fixed controls before advancing.

This is exactly the kind of gate the v1 plan is intended to enforce.
