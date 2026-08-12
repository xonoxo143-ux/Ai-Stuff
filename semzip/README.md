# SemZip / Semantic VM

SemZip is an experiment in **semantic compression and executable meaning**.

The original `semzip` branch preserves the v0.3 semantic-graph/codec prototype. This
`semzip-vm` branch asks a different question:

> What algebraic laws does ordinary meaning obey, and how small can an executable
> semantic instruction set become without losing the ability to reason, remember,
> predict, and reconstruct important meaning?

The long-term target is a cognitive substrate that lets very small learned models do
fuzzy perception/language work while deterministic machinery handles state, memory,
composition, planning, validation, and repeated structure. Phone-scale execution is a
design constraint, not a later optimization target.

## Current architecture

```text
raw language / perception
        |
        v
small learned semantic perception
        |
        v
scored atomic evidence
        |
        v
identity + dimension registry
        |
        v
semantic algebra
  Set / Shift / Clear
  guards / projection
  parallel / sequence
        |
        +------> exact composition / planning / simulation
        |
        +------> repeated-effect discovery / learned macros
        |
        v
K0 SET / K1 SHIFT / K2 REQUIRE / K3 CLEAR
        |
        v
append-only event ledger
        |
        +------> projected reality
        +------> minds / stale beliefs
        +------> history / branches / counterfactual state
```

New VM code should prefer the canonical facade:

```python
from semzip.vm import (
    ShiftEffect,
    SemanticPatch,
    SemanticTransform,
    StateConstraint,
    parallel,
    sequential,
    SemanticVM,
)
```

Older `vm_*` modules remain available because many research benchmarks intentionally
preserve earlier experiments.

## The semantic algebra

The current grounded core does **not** treat `GIVE`, `RECEIVE`, `SELL`, `LEND`,
`ENTER`, or `LEAVE` as VM instructions.

The canonical state effects are deliberately smaller:

```text
Set(x, dimension, value)
Shift(x, dimension, before, after)
Clear(x, dimension)
```

For example:

```text
John gave Mary the book.
Mary received the book from John.
```

can share the lower-level effect:

```text
Shift(book, owner, John, Mary)
Shift(book, possessor, John, Mary)
```

while retaining different surface/perspective information above that layer.

`Shift` is a **partial transformation**: it is defined only when the current value is
its stated `before` value. An extra condition that is not itself changed is represented
as a guard:

```text
Constraint(book, owner, John)
Shift(book, possessor, John, Mary)
```

This is enough to distinguish temporary possession from ownership transfer without a
sacred `LOAN` opcode.

### Laws currently made explicit and regression-tested

For compatible simultaneous effects, parallel composition is:

- associative
- commutative
- idempotent
- equipped with an explicit no-change identity
- **partial**: incompatible writes to the same state cell are rejected

Sequential composition is:

- associative
- equipped with an identity
- generally non-commutative

`Shift(a -> b)` has a local inverse `Shift(b -> a)`. `Set` and `Clear` do not have an
intrinsic inverse unless prior state/history is supplied.

Projection is explicit, so two meanings can differ globally while being equivalent
for a selected view. This supports layered equivalence rather than one universal
semantic hash.

## Layered equivalence

SemZip no longer assumes that one sentence should have one all-purpose canonical hash.
Useful layers include:

```text
surface / discourse perspective
        ↓
proposition
        ↓
world-state transformation
        ↓
projection-specific effect
        ↓
kernel execution
```

For example, `give` and `receive` can differ in perspective while sharing a world
transition. Two events may also be equivalent for `possessor` while differing in
`owner`.

## Memory and world state

The durable source of truth is an append-only event ledger. Current state is a
projection/cache, not the permanent representation.

This supports:

- historical queries and replay
- branches / counterfactual state
- confidence and provenance
- observations that do not automatically overwrite reality
- separate agent minds that may be stale or wrong

Planning uses lightweight immutable state snapshots rather than rebuilding event
histories for every candidate. Generic `ActionSchema` objects instantiate semantic
transforms; the planner itself no longer imports lexical actions such as `give` or
`move`.

## Learned abstractions

Repeated semantic effects can be proposed as anonymous macros. A macro is an optional
compression/execution optimization, **not semantic truth** and not a mandatory class
for the language model to predict.

In the current grounded toy corpus, effect-level discovery independently finds a small
transfer-shaped pattern, and a larger reciprocal exchange pattern can be factored into
two uses of that smaller pattern. The discovery operates on world effects rather than
surface action names or K-opcode ordering.

The current MDL score is still a research approximation. A planned refinement is to
charge actual compact encoded bytes for corpus + library + calls so the compression
pressure is tied directly to storage cost rather than hand-selected record weights.

## Tiny learned front-end results

These are controlled toy benchmarks, **not claims of general language understanding**.
They are useful because they compare architectural choices under the same task.

Selected findings:

- increasing a pooled decoder from roughly 135M to 360M parameters barely improved
  exact semantic compilation
- changing to entity/role pointers helped more than increasing model size
- a purpose-fit bidirectional encoder around 4.4M parameters outperformed much larger
  pooled decoder baselines on the grounded task
- relation-conditioned semantic probes reached about 77% exact on the richer held-out
  synthetic-language benchmark
- when already-understood atomic clauses were compiled separately and their patches
  were composed deterministically, the clean unseen-composition gate reached 96/96

The important lesson is architectural:

> Learned models should discover uncertain atomic semantic evidence. Exact algebraic
> composition should not be relearned inside neural weights when the runtime can do it
> perfectly and cheaply.

The remaining language question is therefore narrower: how small can fuzzy perception
remain while reliably extracting atomic semantic evidence from genuinely varied human
language?

## Trust boundary

A learned model is never authority over world state.

Compiler-facing dimension IDs are constrained by a versioned registry. Pointer ranges,
output structure, conflicts, confidence, and registry signatures are validated before
a proposal becomes an executable semantic transformation. Low-confidence or near-tied
predictions can remain evidence instead of being forced into reality.

## Kernel

The current experimental kernel remains only four opcodes:

```text
K0 SET
K1 SHIFT
K2 REQUIRE
K3 CLEAR
```

`GIVE`, `SELL`, `LEND`, etc. are not privileged instructions. K2 is used for genuine
extra guards; K1 already checks its own source state, so redundant `REQUIRE + SHIFT`
pairs are canonicalized away at the semantic layer.

The kernel is provisional. Primitives must earn their status through execution,
generalization, and compression rather than convenience.

## Run the core gate

```bash
cd semzip
python -m unittest discover -s tests -p 'test_vm*.py' -v
python benchmarks/vm_progress_gate.py
python benchmarks/patch_abstraction_gate.py
```

GitHub Actions runs the same core gate on `semzip-vm`. Research-model workflows are
kept separate from the dependency-light runtime.

## Research rules

1. Do not add an opcode because a word is convenient.
2. Preserve uncertainty, provenance, perspective, and identity distinctions.
3. Treat language as one compiler/perception boundary, not the definition of cognition.
4. Prefer exact code for operations that do not require learned fuzziness.
5. Let repeated semantic structure earn macros through measurable savings.
6. Judge equivalence at the layer relevant to the task; avoid one universal hash.
7. Keep durable history separate from disposable reasoning state.
8. Measure capability per parameter, byte, and unit of computation.
9. Do not call a toy benchmark general intelligence.
10. When an abstraction only works because of our encoding choice, reject it.

## Status of the original SemZip work

The original graph/codec line is preserved on branch `semzip` and remains useful as a
language/representation donor. `semzip-vm` is free to diverge from its ontology choices.
Neither branch should be merged into `main` merely to keep branches tidy.
