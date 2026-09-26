# Agent v1-A1 fixed-control smoke

**Date:** 2026-09-26  
**Commit tested:** `159d05af1d6de2babff8b836420303f096562f82`  
**Workflow run:** `36258204830`  
**Result:** mechanics PASS; scientific interpretation intentionally deferred

The A1 control runner successfully executed:

- fixed 16 cells / top-4 active;
- fixed 64 cells / top-4 active;
- dense 64 cells / all active.

All three used the same deterministic world seed and model seed.

The first smoke used only 24 experiences in a 256-experience world, so every sample remained inside the initial `base` regime. The measured losses therefore **must not** be interpreted as evidence for or against any architecture.

Observed smoke means:

- fixed16 task loss: ~0.947
- sparse64 task loss: ~0.943
- dense64 task loss: ~0.919

Those values only show that the runner produces finite, separable outputs.

The next run expands the paired pilot to the full lifetime schedule so every hidden regime is crossed. Reserve recruitment remains disabled.
