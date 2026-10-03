# Agent language perception result 01

**Date:** 2026-09-28  
**Workflow run:** `36435692995`  
**Status:** RESULT

## Protocol

Raw UTF-8 bytes were mapped into four explicit semantic slots:

- person;
- color;
- animal;
- place.

Validation simultaneously held out:

- semantic combinations;
- sentence templates.

Three architectures were tested across seeds 11, 22, 33 for 200 updates.

## Result

```text
model        exact state   slot accuracy   train steps/s
BiGRU           72.0%          91.6%           14.8
GRU             36.3%          75.9%           21.8
Transformer     36.3%          77.9%           46.5
```

BiGRU exact-state rates by seed:

```text
seed 11   76.0%
seed 22   65.1%
seed 33   75.0%
```

## Interpretation

The perception task currently rewards access to both left and right context strongly enough that the bidirectional recurrent encoder beats both the one-way GRU and the small Transformer on compositional generalization.

The Transformer remains much cheaper to train.

This result also corrects the earlier one-seed scratch impression that the Transformer was clearly better.

## Next test

The largest failure remaining is not tokenization or lack of capacity; it is loss of slot-specific information across paraphrases.

Candidate D keeps the BiGRU but adds separate learned readout queries for each semantic slot.

This tests whether **disentangled readout** improves the perception boundary without replacing the recurrent substrate.
