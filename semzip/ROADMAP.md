# SemZip VM Roadmap — Discovering an Algebra of Meaning

## North-star question

> **What algebraic laws does ordinary meaning obey, and how small can the resulting
> semantic instruction set become without losing the ability to reason, predict,
> remember, and reconstruct important meaning?**

The `semzip` branch preserves the earlier v0.3 semantic-graph/codec line. This roadmap
is for `semzip-vm`.

The project does **not** assume that language words, graph predicates, or today's K0–K3
kernel are the final semantic primitives.

---

## Working model

A grounded assertion can often be viewed as a partial transformation on world state:

```text
M : S -> S'
```

The current atomic state-effect hypotheses are:

```text
Set(entity, dimension, value)
Shift(entity, dimension, before, after)
Clear(entity, dimension)
```

with separate domain constraints when a required fact is not itself the source of a
`Shift`.

Higher meaning is composed rather than encoded as an ever-growing verb dictionary:

```text
atomic effects
    ↓
parallel transforms / ordered sequences / guards / projections
    ↓
reusable learned subexpressions
    ↓
semantic library
    ↓
K0–K3 execution
```

Language is one compiler boundary into this algebra, not the ontology itself.

---

# What is already established

## A. Ledger-first state

Durable truth is an append-only event ledger. Current state is a projection/cache.
Branches, history, provenance, uncertain observations, and separate minds use the same
basic machinery.

## B. Ownership is not possession

Temporary possession no longer implies ownership transfer. This remains a permanent
regression test because it exposed the danger of deriving ontology from words alone.

## C. Tiny executable kernel

The experimental kernel is:

```text
K0 SET
K1 SHIFT
K2 REQUIRE
K3 CLEAR
```

A shift already checks its source value. K2 is therefore reserved for extra guards,
not duplicated before every K1.

## D. Atomic semantic effect algebra

Canonical patches store one atomic effect per state cell. Grouped structures such as
`RelationDelta(owner+possessor)` are compatibility/compression views, not semantic
truth.

The current law tests establish:

- explicit identity / no-change
- associative, commutative, idempotent parallel composition when compatible
- explicit failure for conflicting simultaneous writes
- associative, generally non-commutative sequence
- local inverses for `Shift`
- non-invertibility of `Set/Clear` without prior state
- equivalence under selected projections

These are empirical design commitments and may be revised if broader semantic tests
break them.

## E. Neural perception should stay narrow

Controlled experiments strongly favor small purpose-fit semantic perception plus exact
runtime composition over asking a larger decoder to regenerate low-level bytecode.

Current best lessons:

- architecture changes beat a 135M -> 360M parameter increase on the toy compiler task
- a roughly 4.4M bidirectional encoder is already useful as a semantic perception unit
- relation-conditioned probing improves disentanglement
- deterministic composition of independently understood atomic clauses solved the clean
  unseen-composition gate exactly

These results are benchmark evidence, not claims of general language capability.

---

# Phase 1 — Consolidate the algebraic core

**Status: active / mostly complete.**

Goals:

- one canonical state-effect algebra
- explicit identities
- guards/domain conditions
- parallel versus ordered composition
- layered/projection equivalence
- compatibility adapters around older representations
- a single public `semzip.vm` facade

Remaining high-value work:

- demote domain-specific compatibility effects such as return obligations into generic
  semantic-library structures when a clean representation is available
- decide whether a general expression AST is needed beyond patch + sequence; do not add
  speculative operators just for completeness

Gate:

> Changing display grouping or bytecode layout must not change semantic identity.

---

# Phase 2 — Generic cognition over the algebra

**Status: active.**

Planning and simulation should consume semantic transformations rather than lexical
actions.

Architecture:

```text
ActionSchema
    ↓ instantiate
SemanticTransform(guards, effects)
    ↓ pure apply
StateSnapshot
```

The event ledger is durable memory, not an inner-loop scratch simulator.

Gates:

- planner can solve tasks using anonymous/generic transform schemas
- no planner dependency on `give`, `move`, `sell`, etc.
- candidate simulation does not rebuild event history
- selected plans can still compile to K0–K3 and commit transactionally

Future question:

> Can useful action schemas themselves be discovered or compressed from repeated
> experienced transformations rather than hand-authored?

---

# Phase 3 — Real description-length learning

The current effect-level learner already discovers reusable anonymous world-change
patterns and can factor a reciprocal exchange into two smaller transfer-shaped patterns.

The next objective is stricter:

```text
TOTAL DESCRIPTION COST =
    encoded experience
  + semantic library definitions
  + macro calls
  + required atom/dimension tables
  + optional execution penalty
  + reconstruction/prediction loss
```

Near-term work:

1. Make all abstraction discovery operate on canonical atomic semantic effects.
2. Charge **actual encoded bytes** where possible instead of fixed hand-selected record
   costs.
3. Encode a corpus with promoted macros and prove exact reconstruction.
4. Reject macros that save representation but harm prediction/reasoning behavior.
5. Recursively factor learned macro definitions.

A macro remains an optimization. It must never become true merely because it compresses.

Gate:

> Promotion must reduce the real objective after paying for the library definition.

---

# Phase 4 — Expand algebraic operators only when earned

Do **not** create a checklist of linguistic operators and add them mechanically.

Candidate mathematical domains to investigate include:

- negation / complement
- implication / conditional transformations
- alternatives / branching
- probability and confidence
- sets and quantities
- continuous dimensions and geometry
- scoped belief/knowledge states
- goals / desired-state constraints
- discourse acts such as ASSERT / QUERY / REQUEST

For every candidate, ask:

1. Is this an algebraic operator, a data type, a scoped world, or merely a semantic
   library macro?
2. What laws should it obey?
3. What counterexamples break those laws?
4. Can it be reduced to existing operations without unacceptable cost or loss?
5. Does adding it improve compression, reasoning, or prediction on held-out tasks?

Examples:

- probability may belong primarily on evidence/branches rather than as a kernel opcode
- belief may be a scoped projection/ledger rather than a `BELIEVE` instruction
- quantity may be a value/data algebra rather than a verb-like semantic operator
- `ASSERT`, `QUERY`, and `REQUEST` may belong to a discourse/executive layer rather
  than world-state transformation itself

Gate:

> No new primitive is accepted because its English name feels fundamental.

---

# Phase 5 — Layered equivalence

SemZip should support several explicit equivalence relations instead of one universal
semantic hash:

```text
surface
pragmatic/discourse
propositional
full world transition
projection-specific transition
kernel behavior
```

Experiments should include sentences that deliberately diverge at one layer and
converge at another.

Example:

```text
John gave Mary the book.
Mary received the book from John.
```

Expected:

- surface: different
- perspective/pragmatic focus: potentially different
- relevant ownership/possession transition: potentially equal

Gate:

> Every canonicalization claim names the equivalence layer it is canonicalizing.

---

# Phase 6 — Tiny raw-language perception

The neural front end should predict bounded semantic evidence, not arbitrary JSON or
bytecode.

Preferred decomposition:

```text
raw text
  ↓
mention evidence
  ↓
identity resolution
  ↓
relation/dimension-conditioned semantic probes
  ↓
confidence-preserving atomic effects
  ↓
exact parser/algebraic composition
```

Important rules:

- entity spelling/identity is not generated by the neural model when a pointer can be
  used
- compiler outputs are bound to a signed/versioned semantic-dimension registry
- near-ties and low confidence remain ambiguous evidence
- exact union/sequence is runtime work, not neural memorization

Next gates:

1. raw mention detection on unseen names and multiword entities
2. raw-text -> atomic-effect accuracy with gold mentions
3. raw-text -> effects with predicted mentions
4. adversarial paraphrases outside the synthetic training dialect
5. shared-backbone versus separate tiny encoders
6. calibration, not only top-1 accuracy

Only after those gates should model size increase materially.

---

# Phase 7 — Identity, reference, and coreference

Surface equality is not entity identity.

The identity store should preserve:

- mention occurrences
- persistent entities
- aliases
- unresolved ambiguity
- explicit evidence linking mentions to entities

A learned resolver may propose links, but persistent IDs and alias history remain
external structured state.

Gate:

> Two identical names may remain distinct; two different names may resolve to one
> entity when evidence supports it.

---

# Phase 8 — Broader grounded universes

The current synthetic world is intentionally tiny. It must not become the ontology by
accident.

Expand controlled environments across qualitatively different domains:

- containment and topology
- resource/quantity changes
- switches/process state
- continuous temperature/position
- simple social obligations/permissions
- uncertainty/noisy observations
- partial visibility and agent belief

Hold entire combinations/domains out during learning.

The important test is not whether the learner compresses one game world. It is whether
reusable algebraic structures survive transfer to new domains.

---

# Phase 9 — Recursive controller

Once the algebra and semantic library are stable enough, train a tiny controller on:

```text
semantic state + goal + available transforms
        ↓
next useful operation / query / simulation step
```

The controller should not memorize factual world knowledge or redo deterministic
search machinery that can be externalized.

Compare:

- explicit search
- tiny recursive controller
- hybrid controller + search
- ordinary small LM baselines

Measure capability per parameter and per unit of compute.

---

# Phase 10 — Reverse compiler / language generation

Only after internal meaning is useful independently of text:

```text
semantic expression
    ↓
optional macro/concept recognition
    ↓
small generator
    ↓
human language
```

Generation should preserve requested perspective and discourse information when that
layer was retained; it should not pretend lower-level transition equivalence means the
original wording was recoverable.

---

# Phase 11 — Phone/native runtime

Python is the research implementation, not the target deployment runtime.

Before a native rewrite, stabilize:

- semantic algebra
- registry format
- binary format
- event-block format
- tiny neural input/output contract

Then evaluate a compact native implementation and phone inference runtime.

Track:

- serialized semantic bytes
- resident RAM
- batch-1 latency
- reasoning steps/second
- model size before/after int8 quantization
- battery/thermal behavior on actual ARM hardware

GitHub x86 runner numbers are proxy measurements only.

---

# Benchmark families

Every major claim needs adversarial tests.

## Algebra laws

Property-style tests for identity, associativity, conditional commutativity,
non-commutative sequence, inverses, conflicts, and projection.

## Paraphrase convergence

Different wording -> same relevant semantic effect when justified.

## Minimal-pair discrimination

Small meaning difference -> different semantic expression.

## Novel composition

Known atomic meanings combined in combinations absent from training.

## Temporal ordering

Parallel versus sequential updates must remain distinct.

## Uncertainty

Low-confidence evidence must not silently become accepted reality.

## Abstraction discovery

Learned macros must be blind to action labels and bytecode serialization.

## Cross-domain transfer

Structures learned in one synthetic domain must remain useful in another.

## Compression

Measure real encoded corpus + library cost, not only unique graph counts.

## Phone efficiency

Measure model/runtime footprint without confusing desktop proxy numbers for device
results.

---

# Stop conditions for architecture work

A restructuring pass is justified when it:

- removes a duplicated semantic authority
- exposes a testable algebraic law
- makes an invalid state unrepresentable or explicitly rejected
- reduces neural responsibility
- removes domain-specific assumptions from the core
- materially improves asymptotic runtime/storage
- makes experiments comparable/reproducible

A restructuring pass is **not** justified merely to:

- rename every historical file
- obtain aesthetically perfect package nesting
- replace stable compatibility adapters
- add speculative operator classes with no benchmark
- move code without changing which layer owns a concept

When only the latter class remains, resume experiments instead of polishing architecture.
