# SemVM Experiment Ledger

This file records **which experiments currently inform the architecture**. Historical
modules/workflows are intentionally preserved for reproducibility; their existence does
not mean they remain canonical.

## Canonical runtime line

New runtime work should target these concepts, preferably through `semzip.vm`:

| Layer | Canonical implementation |
|---|---|
| atomic effects | `vm_effects.py` — `SetEffect`, `ShiftEffect`, `ClearEffect` |
| simultaneous meaning | `vm_patch.py` — `SemanticPatch` |
| guarded partial transform | `vm_transform.py` — `SemanticTransform` |
| algebra operations | `vm_algebra.py` — parallel, sequential, inverse, projection |
| ordered meaning | `vm_sequence.py` |
| tiny kernel | `vm_kernel.py` — K0..K3 |
| durable history | `vm_ledger.py` |
| disposable reasoning state | `vm_state.py` — `StateSnapshot` |
| parameterized actions | `vm_actions.py` — `ActionSchema` |
| planning | `vm_plan.py` — generic schema search over snapshots |
| dimension vocabulary | `vm_relations.py` (preferred terminology: dimension registry) |
| public API | `semzip.vm` |

`RelationDelta` is a compatibility/compact grouping view. It is **not** the canonical
semantic atom.

## Compatibility boundaries still in use

- `vm_delta.py`: early grounded delta frame and `RelationDelta` compatibility API
- `vm_compile.py`: named toy-world compiler helpers used by old benchmarks
- `vm_delta_bridge.py`: old primary/secondary delta compiler contract
- `vm_patch_bridge.py`: factorized relation-cell compiler experiments
- `vm_effect_bridge.py`: generalized bounded compiler proposal bridge
- `vm_equivalence.py`: earlier surface/proposition/program equivalence experiment

These may be retired later, but deleting them now would destroy useful regression and
comparison baselines for little architectural gain.

## Preferred language-learning result

The current direction is **small bidirectional semantic perception + deterministic
composition**.

Most informative results so far:

1. Pooled ~135M decoder, grounded delta output: about 45.8% exact.
2. Same task with ~360M backbone: about 46.9%; parameter scale was not the main lever.
3. Pointer/full-context interfaces materially improved the 135M line.
4. Purpose-fit ~4.4M bidirectional encoder was competitive with or better than much
   larger pooled decoder baselines.
5. Relation-conditioned ~4.4M semantic probes reached about 77.1% exact on the richer
   held-out synthetic-language benchmark.
6. Atomic compiler + deterministic patch composition reached 96/96 on the clean unseen
   semantic-composition gate.

Interpretation:

> Neural models should identify uncertain atomic semantic evidence. Algebraic union,
> ordering, validation, memory, and execution should be explicit runtime work when
> possible.

## Important negative results

### Bigger decoder alone

135M -> 360M barely changed total exact grounded compilation. Do not scale the language
front end merely because a semantic template is difficult.

### Relation-subset classifier

The ~4.4M model obtained a strong standard score by choosing among predeclared relation
bundles, then scored 0/96 when an owner+possessor combination was held out from training.
This representation is convenient but not compositionally trustworthy.

### Independent sparse grid without sufficient conditioning

Factorizing output cells alone did not cause unseen conjunctions to compose reliably.
Representation factorization is not the same as learned compositional behavior.

### Masking absent secondary-transfer fields

Conditional decoding reduced total accuracy. Do not assume removing every `NONE` target
helps training.

### Whole-sentence entity marker states in a causal decoder

Early pointer heads were context-limited because an entity marker could not attend to
future words. Full-sentence role queries or bidirectional encoders are preferred.

## Abstraction-learning line

### Retained as historical controls

- `vm_mdl.py`
- `vm_macros.py`

These discover/rewrite **K-instruction sequences**. They prove program-level compression
but can accidentally reward bytecode layout choices.

### Preferred

- `vm_patch_mdl.py`
- `vm_patch_codec.py`

These operate on semantic world effects after erasing entity names and patch order.
The current toy gate finds a reusable transfer-shaped pattern; a reciprocal exchange
can factor exactly into two instances of it.

Next improvement: replace fixed semantic record weights with a corpus/library objective
based on real compact encoded bytes where possible.

## World-delta discovery

`vm_deltas.py` remains valuable as a separate experiment because it mines before/after
world changes with action labels hidden. It should be interpreted as **evidence about
possible abstractions**, not as the canonical runtime representation.

## Research workflows

The repository currently contains many one-off `semzip-vm-*.yml` workflows. They are an
experiment archive, not an intended permanent CI architecture.

Keep:

- `semzip-vm-core.yml` as the required runtime/regression gate.

Future research should preferentially migrate toward one parameterized research
workflow and one deployment/phone-proxy workflow. Do not delete old workflows until
important metrics/artifacts have durable snapshots.

## Decision rule

When comparing two approaches, prefer the one that improves held-out reasoning,
composition, calibration, storage, or compute **without moving deterministic work back
into neural weights**.

A higher toy score is not sufficient if it is achieved by baking combinations or
ontology classes into the model's output vocabulary.
