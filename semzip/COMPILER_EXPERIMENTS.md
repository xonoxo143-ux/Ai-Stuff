# SemVM Compiler Experiments

This file records the language-to-SemVM compiler experiments on the `semzip-vm` branch. The goal is not to maximize a toy benchmark by any means necessary; it is to discover the smallest useful neural boundary around a deterministic semantic runtime.

## Evaluation contract

The current grounded benchmark uses held-out names/items and held-out paraphrase forms. The neural compiler ultimately predicts world changes rather than unrestricted text. Current relation dimensions are `owner`, `possessor`, and `location`, with optional reciprocal transition and return-obligation structure.

All percentages below are toy-domain results, not general language-understanding claims.

## Experiment ladder

| Experiment | Backbone | Train | Eval | Exact | Notes |
|---|---:|---:|---:|---:|---|
| Zero-shot full bytecode | SmolLM2 135M | 0 | 5 | 0/5 | JSON shape learned from prompt; semantics poor. Strict bridge caught malformed arity. |
| Generative bytecode LoRA | SmolLM2 135M | 96 | 16 | 2/16 | Model also had to regenerate arbitrary entity strings. |
| Entity-slot generative | SmolLM2 135M | 96 | 16 | 6/16 | Replacing arbitrary identifiers with `E0..E3` tripled exact accuracy. |
| Structured operation + pointers | SmolLM2 135M | 256 | 64 | 24/64 (37.5%) | No JSON generation. Still used four anonymous event-class labels. |
| Grounded world delta baseline | SmolLM2 135M | 512 | 96 | **44/96 (45.83%)** | No GIVE/LEND/SELL output class. Predicts relation deltas + pointers. |
| Conditional-secondary ablation | SmolLM2 135M | 512 | 96 | 33/96 (34.38%) | Negative result: masking absent-secondary pointer loss hurt generalization. |
| Capacity ablation | SmolLM2 360M | 512 | 96 | 45/96 (46.88%) | 2.7x backbone size barely changed total accuracy; learned some sales but lost gifts/loans. |
| Rich-curriculum ablation | SmolLM2 135M | 1024 | 96 | 39/96 (40.63%) | More semantic paraphrases learned some sales but collapsed gifts. More data alone did not solve entanglement. |

## Grounded baseline details

SmolLM2-135M grounded-delta baseline:

- pointer accuracy: 76.74%
- relation/structure-bit accuracy: 86.72%
- exact frame: 44/96
- gift-like transition: 11/24
- loan-like transition: 9/24
- location movement: 24/24
- reciprocal exchange: 0/24

The important qualitative result is the loan score: the model produced exact loan semantics without a `LEND` output class. A loan is represented as a possession transition plus a return obligation while ownership remains unchanged.

## Capacity ablation details

SmolLM2-360M on the identical 512/96 distribution:

- pointer accuracy: 73.96%
- relation/structure-bit accuracy: 91.67%
- exact frame: 45/96
- gift: 6/24
- loan: 7/24
- move: 24/24
- exchange: 8/24

Interpretation: extra capacity improved some structural bits and reciprocal exchange, but total exact accuracy rose by only one example while simpler event families regressed. Scaling the language model is therefore not the preferred next lever.

## Rich-curriculum details

SmolLM2-135M with 1,024 richer training examples and the same 96-example held-out evaluation:

- pointer accuracy: 77.95%
- relation/structure-bit accuracy: 92.45%
- exact frame: 39/96
- gift: 0/24
- loan: 7/24
- move: 24/24
- exchange: 8/24

Interpretation: explicitly teaching more ways to describe reciprocal exchange transferred to the held-out exchange templates, but the pooled representation traded away another distinction. This is evidence against blindly expanding the paraphrase corpus as the primary solution.

## Negative result: conditional secondary loss

The secondary-delta fields are absent in most examples, so an experiment trained secondary pointer heads only on examples where a second transition existed. This sounded attractive because deterministic code can fill `NONE` when no secondary delta exists.

It performed worse:

- exact: 33/96
- gift: 0/24
- loan: 9/24
- move: 24/24
- exchange: 0/24

Do not promote this masking strategy into the preferred architecture without a new controlled result showing a benefit.

## Current architecture hypothesis

The compiler should increasingly behave like semantic perception rather than text generation:

```text
text
  -> deterministic entity slots
  -> tiny neural semantic encoder
  -> bounded entity pointers + grounded relation-change bits
  -> strict DeltaPrediction bridge
  -> SemanticDeltaFrame
  -> deterministic SemVM compilation
  -> K0..K3 execution
```

The model cannot invent opcodes, arbitrary relation names, arbitrary entity strings, or malformed instruction arities at this boundary.

## In progress

1. **Causal entity-marker pointer control** — scores contextual SmolLM2 marker states directly. Known caveat: early marker states in a causal decoder cannot see later text.
2. **Full-context low-rank pointer** — uses the final causal state to produce semantic-role queries which score contextual entity markers in a 32-dimensional pointer space.
3. **Tiny bidirectional encoder** — fully fine-tunes Google's two-layer, hidden-size-128 BERT miniature with the same grounded relation/pointer target. This tests whether a purpose-fit bidirectional encoder can replace a 135M causal language model entirely.

## Research rule reinforced by these runs

Every task that deterministic code can perform reliably should be removed from the neural model unless an experiment shows a clear benefit to learning it. The strongest improvement so far came not from scaling, but from removing arbitrary entity-string generation and replacing it with pointers.
