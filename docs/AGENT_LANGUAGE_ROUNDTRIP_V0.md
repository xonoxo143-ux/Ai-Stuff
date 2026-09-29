# Agent language roundtrip v0

**Date:** 2026-09-29  
**Workflow run:** \`36438063867\`  
**Status:** RESULT  
**Goal:** test the first closed language loop around a bounded non-language state.

## Structure

\`\`\`text
held-out English paraphrase
        ↓
BiGRU perception organ
        ↓
4 × 4 semantic logits
        ↓
hard or soft 16-d bridge
        ↓
GRU production organ
        ↓
canonical English target
\`\`\`

## Bridge controls

### Oracle
Ground-truth state supplied to the producer.

### Hard predicted
Perception argmax converted to one-hot state.

### Soft predicted
Per-slot probability distributions concatenated directly.

Teacher forcing was intentional in this v0 gate to isolate the semantic junction before free-generation exposure errors.

## Three-seed result

\`\`\`text
perception exact state       70.31%
oracle sequence exact       100.00%
oracle byte accuracy        100.00%

hard sequence exact          70.31%
hard byte accuracy           98.65%

soft sequence exact          67.53%
soft byte accuracy           98.70%
\`\`\`

## Interpretation

The hard-state exact output rate equals the perception exact-state rate.

So, in this controlled setting:

> when perception recovers the correct state, the semantic bridge and trained producer add essentially no additional exact-sequence loss.

Soft probabilities did not improve exact sequence recovery.

The primary bottleneck is therefore the perception/state extraction side, not the controlled state→production junction.

## Consequence

This result establishes that language can be split around a bounded non-language representation without automatically destroying the information needed for output.

It does **not** establish open-domain semantics, free-running dialogue, or a final ontology.

Do not keep optimizing this toy bridge. Move effort to higher-leverage cognition/transfer questions and later return with a richer integrated state.
