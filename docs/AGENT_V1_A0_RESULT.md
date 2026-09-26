# Agent v1-A0 result

**Date:** 2026-09-26  
**Commit tested:** `0b447044eb6446e9d8f0a71d4fb7cc0415c2b394`  
**Workflow run:** `36258058747`  
**Result:** PASS

## What A0 established

The first v1 implementation gate is now executable.

The branch contains:

- deterministic nonstationary lifetime generation;
- evaluator-only hidden regime metadata;
- per-experience deterministic random access;
- exact world configuration fingerprints;
- checkpoint serialization/validation;
- deterministic JSONL evaluator traces;
- tests for schedule order, replay, seed sensitivity, event-schema isolation, decoy dynamics, and checkpoint identity.

CI completed successfully.

The same seeded lifetime trace was generated twice and compared byte-for-byte with `cmp`.

## What this does not establish

A0 does not yet show that:

- v0 adapts well to the lifetime world;
- the world creates useful developmental pressure;
- 64 cells outperform 16;
- sparse 64 beats dense 64;
- reserve recruitment is useful;
- any structural development should be promoted.

Those are A1+ questions.

## Next gate

V1-A1 introduces fixed controls on the same deterministic world:

1. fixed 16-cell sparse ecology;
2. fixed 64-cell sparse ecology;
3. dense 64-cell ecology.

Reserve recruitment remains disabled.
