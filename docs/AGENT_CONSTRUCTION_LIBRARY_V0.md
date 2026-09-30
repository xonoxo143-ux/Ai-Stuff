# Learned Construction Library v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can explicit reusable constructions systematically recombine already-grounded language structures better than the current sequential byte encoder?

## Deconfounded benchmark

All function words in the structural-OOD test occur during training.
Only particular construction × semantic-attribute combinations are held out.
Argument strings are tested both from the training lexical pool and from a completely disjoint OOV pool.

## Neural baseline

77,274-parameter byte BiGRU + joint bounded span decoder, 1,200 updates:

```text
seed 0 structural exact       34.94%
seed 1                        31.61%
seed 2                        28.50%

with OOV arguments:
seed 0                        35.22%
seed 1                        28.28%
seed 2                        28.00%
```

## Construction learner

From grounded examples it masks argument spans, deduplicates grounded surface structures, anti-unifies structures with the same shape but different semantic attributes, infers lexical attribute mappings from systematic semantic differences, and compiles a construction only after support from at least two semantic attributes.

The corrected implementation induced 8 generalized constructions.
Fit time was approximately 0.04 seconds/seed.

## Result

```text
                         seed0   seed1   seed2
structural OOD           100%    100%    100%
structural + OOV args    100%    100%    100%
unparsed                    0       0       0
```

In every seed the learner inferred:

```text
color → color
pet   → pet
place → place
```

## Interpretation

This is a large representation result in the controlled regime.
The sequential encoder can learn all observed templates but does not reliably factor them into reusable structural operations. Explicit construction induction does.

The result does not establish broad natural-language coverage, synonym semantics without grounding, recursive construction composition, ambiguity resolution, discourse pragmatics, or unsupervised language acquisition.

## Next gate

Developmental Construction Grammar v1:
- recursive composition;
- one/few-shot new-construction grounding;
- no regression on old language;
- sparse lookup as the construction store grows.