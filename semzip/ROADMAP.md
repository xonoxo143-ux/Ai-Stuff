# SemZip Roadmap: From Toy Codec to Semantic Substrate

## Goal

SemZip is an experiment in semantic compression.

Instead of treating different strings as fundamentally different objects, SemZip tries to convert language into a canonical, inspectable meaning representation that can be reused by memory, reasoning, simulation, translation, and eventually a broader Cognitive Engine.

The working hypothesis is:

> A large portion of everyday language can be represented as compositions of a much smaller number of reusable semantic structures.

We do **not** assume the final number of primitives in advance. The project should discover the useful level of decomposition empirically.

---

## Mental model

Think of ordinary text as a rendered file format.

```text
English sentence ─┐
Spanish sentence ─┤
Image observation ┼─> canonical meaning graph ─> reasoning / memory / planning
Sensor event ─────┤
Database record ──┘
```

Language is an encoder/decoder around the canonical meaning, not necessarily the canonical meaning itself.

This is closer to an intermediate representation (IR) in a compiler than a dictionary.

A compiler may turn many source-level spellings into the same low-level operation. SemZip should attempt the same thing for meaning.

---

# Design principles

## 1. Meaning first, wording second

Paraphrases should converge when they carry the same relevant meaning.

```text
John gave Mary the book.
Mary received the book from John.
The book was given to Mary by John.
```

should converge toward one semantic object.

## 2. Preserve meaningful differences

Compression must not erase distinctions such as:

- John killed Bill.
- John almost killed Bill.
- John did not kill Bill.
- John believes he killed Bill.
- John might kill Bill.

A shorter graph that merges these is a failed codec.

## 3. Unknown is better than invented

If SemZip cannot represent or parse something faithfully, it should say so or retain an unresolved structure. It must not silently manufacture a convenient interpretation.

## 4. Ambiguity is data

"I saw the man with the telescope" can have more than one valid analysis. The representation should be able to keep competing interpretations until context resolves them.

## 5. Inference is not assertion

If the input says:

```text
A robin is a bird.
```

and the ontology knows birds are animals, SemZip may infer that the robin is an animal, but it should distinguish the inferred fact from the explicitly supplied fact.

## 6. Language independence is a target

English grammar should not become the ontology by accident. Equivalent meanings in different languages should have a path toward the same canonical structure.

## 7. Inspectability before cleverness

Early versions should favor explicit Python structures and deterministic transformations. Learned parsers can assist at the edges later, but the semantic substrate should remain visible and testable.

---

# Architecture target

```text
                 SEMZIP

Input text
   |
   v
Surface parser
   |
   v
Candidate meaning graph
   |
   +--> ambiguity / uncertainty
   |
   v
Canonicalizer
   |
   v
Semantic IR
   |\
   | +--> ontology
   | +--> inference engine
   | +--> memory
   | +--> semantic hash / deduplication
   |
   v
Generator / downstream consumer
```

The existing v0.1 prototype already demonstrates a tiny version of the parser -> canonical graph -> hash -> generator loop for TRANSFER events.

---

# Phase 1 — Build the universal graph grammar

Before defining thousands of concepts, define the kinds of things the graph itself can express.

## Core node kinds

Start with a deliberately small structural vocabulary:

- ENTITY — a thing or identifiable participant
- EVENT — something that happens
- STATE — a condition that holds
- PROPERTY — a quality or measurement
- RELATION — a connection between things
- PROPOSITION — a claim that can itself be believed, negated, questioned, etc.

These are graph machinery, not necessarily ultimate metaphysical categories.

## Core edge / role families

Examples:

- actor / agent
- patient / affected
- theme / object
- source
- destination / goal
- instrument
- owner
- location
- time
- cause
- purpose
- manner

The exact names are less important than canonical consistency.

## Why this comes first

If the graph cannot represent nested propositions, uncertainty, time, or causation cleanly, adding 50,000 vocabulary concepts will only create a larger broken system.

## Deliverable

`model.py` evolves from the current simple event structure into a typed graph with stable canonical serialization.

## Gate tests

The graph must distinguish at minimum:

```text
Alice opened the door.
Bob opened the door.
Alice closed the door.
Alice did not open the door.
Alice might open the door.
Alice believes Bob opened the door.
Alice believes Bob did not open the door.
```

---

# Phase 2 — State, change, and event decomposition

This is the first real test of the "small semantic alphabet" idea.

Instead of immediately treating OPEN, CLOSE, GIVE, TAKE, BUY, SELL, ENTER, LEAVE, etc. as unrelated atoms, define reusable change structures.

Example:

```text
MOVE(x, source, destination)
```

can be understood as a change in location.

```text
TRANSFER_POSSESSION(x, A, B)
```

can be understood as a change in possession.

A useful generic schema may look like:

```text
CHANGE
  subject: X
  dimension: LOCATION
  before: A
  after: B
```

or:

```text
CHANGE
  subject: BOOK
  dimension: OWNER
  before: JOHN
  after: MARY
```

## Why this matters

If many verbs reduce to variations of CHANGE + a semantic dimension + constraints, that is real semantic compression rather than a renamed dictionary.

## Gate tests

SemZip should express and compare:

- enter / leave
- give / receive
- buy / sell
- borrow / lend
- appear / disappear
- heat / cool
- grow / shrink

while preserving perspective and special constraints.

---

# Phase 3 — Identity, ontology, and inheritance

Introduce concept identity independent of spelling.

Example hierarchy:

```text
physical_entity
  -> living_entity
     -> animal
        -> mammal
           -> dog
```

WordNet-like resources are donors here, but SemZip should not copy the assumption that every useful concept is merely a word sense.

## Key distinctions

- TYPE: dog
- INSTANCE: Fido
- PROPERTY: brown
- RELATION: owns

## Inference

If:

```text
Fido instance_of DOG
DOG is_a MAMMAL
MAMMAL is_a ANIMAL
```

then SemZip can derive:

```text
Fido instance_of ANIMAL
```

and mark that result as inferred.

## Gate tests

- inheritance works transitively
- exceptions can override defaults
- identity is not confused with labels
- aliases and synonyms can point to the same concept
- polysemous words can point to different concepts

Example: `bank` must not force riverbank and financial institution into one node.

---

# Phase 4 — Time and aspect

Time is not just a word such as "yesterday".

Represent:

- before / after / simultaneous
- points and intervals
- duration
- event ordering
- started / ongoing / completed
- habitual / repeated

Examples that must remain distinct:

```text
Alice eats.
Alice ate.
Alice is eating.
Alice had eaten.
Alice used to eat there.
Alice will have eaten before Bob arrives.
```

We do not need to reproduce every English tense label internally. We need to preserve the underlying temporal relationships.

---

# Phase 5 — Negation, modality, and possible worlds

This prevents a major category of semantic corruption.

Represent at least:

- NOT
- POSSIBLE
- PROBABLE
- NECESSARY
- INTENDED
- ATTEMPTED
- COUNTERFACTUAL
- CONDITIONAL

Examples:

```text
John opened the door.
John did not open the door.
John tried to open the door.
John almost opened the door.
John may open the door.
John must open the door.
If John opens the door, Mary will leave.
```

A proposition may therefore be embedded inside operators rather than flattened into the main world state.

---

# Phase 6 — Minds: belief, knowledge, desire, speech

The graph needs to represent different agents having different models of reality.

Example:

```text
REALITY:
  box contains KEY

ALICE believes:
  box contains COIN

BOB knows:
  box contains KEY
```

This is essential for conversation, planning, deception, fiction, social reasoning, and a future agent architecture.

## Required operations

- believe(P)
- know(P)
- want(P)
- expect(P)
- intend(P)
- say(P)
- ask(P)
- command(P)

The embedded proposition P is its own semantic object.

---

# Phase 7 — Causation and counterfactual simulation

Add explicit distinctions among:

- cause
- enable
- prevent
- correlate
- precede

The system should not infer causation merely because one event occurs before another.

Examples:

```text
The collision broke the glass.
The open window allowed the smoke to escape.
The lock prevented the door from opening.
```

Later, this becomes the bridge from SemZip into a world simulator: a semantic cause can point to executable domain models rather than remaining only a language relation.

---

# Phase 8 — Quantity, sets, and reference

Represent:

- one / many
- exact quantities
- ranges
- all / some / none
- groups and members
- definite vs indefinite reference when it changes meaning
- same entity vs another entity

Examples:

```text
A dog barked.
The dog barked again.
Every dog barked.
Some dogs barked.
No dogs barked.
Exactly three dogs barked.
Most dogs barked.
```

This phase is important because many superficially similar sentences have very different truth conditions.

---

# Phase 9 — Semantic molecules and lexical mapping

Only after the graph substrate is capable enough do we aggressively map ordinary vocabulary into reusable structures.

Donor resources can propose candidate frames/concepts. SemZip then asks whether they can be decomposed.

Example family:

```text
TRANSFER
  give
  receive
  donate
  award
  lend
  borrow
  steal

EXCHANGE
  buy
  sell
  trade
```

Each lexical concept can be modeled as:

```text
base structure
+ constraints
+ perspective
+ conventional implications
```

Example idea:

```text
SELL =
  exchange(goods, seller -> buyer)
  exchange(payment, buyer -> seller)
  agreement(participants)
```

The exact decomposition must be tested, not assumed.

---

# Phase 10 — Primitive discovery experiment

Do not hand-author a sacred list of primitives.

Instead:

1. Import a large sample of common concepts/events.
2. Decompose each into reusable structures.
3. Count repeated structures.
4. Merge structures that behave equivalently.
5. Try recursively decomposing those structures.
6. Measure whether compression increases without harming fidelity.

Track a curve:

```text
number of primitive concepts
        vs
semantic fidelity / representation cost
```

The likely useful answer may be a hierarchy, not one tiny irreducible vocabulary.

For example:

```text
surface concepts
    ↓
frames
    ↓
semantic molecules
    ↓
core operations
    ↓
small structural primitives
```

---

# Phase 11 — Ambiguity and uncertainty

A candidate graph can carry confidence and alternatives.

Example:

```text
"I saw the man with the telescope."

candidate A: telescope is instrument of SEE
candidate B: man possesses telescope
```

Context may later collapse the alternatives.

Important rule: semantic hash equality should normally require resolved canonical meaning, not merely the same ambiguous surface sentence.

---

# Phase 12 — Cross-lingual convergence

Add a second language only after English-side semantics are stable enough to test something meaningful.

The test is not translation quality by itself.

The key experiment is:

```text
English sentence -> SemZip graph A
Spanish sentence -> SemZip graph B

A == B ?
```

Equivalent meanings should increasingly converge.

If they systematically fail because the graph encodes English-specific syntax, redesign the graph rather than patching each language.

---

# Phase 13 — Connect SemZip to the Cognitive Engine

Once SemZip can reliably represent events, states, time, causation, beliefs, goals, and identity, it can become the shared substrate between modules.

```text
language parser ----┐
vision system ------┤
memory -------------┼-> SemZip/world model
simulator -----------┤
planner -------------┘
```

At this point SemZip stops being merely a language experiment and becomes a candidate internal communication format for a modular AI system.

---

# Benchmark strategy

Every feature must arrive with adversarial examples.

## A. Paraphrase convergence

Same meaning, different wording -> same or equivalent graph.

## B. Minimal-pair discrimination

One small semantic difference -> different graph.

Example:

```text
John gave Mary a book.
Mary gave John a book.
```

## C. Round-trip preservation

```text
text -> graph -> generated text
```

Generated wording may change; important meaning must survive.

## D. Inference preservation

Graph should support valid derived facts without mixing them with asserted facts.

## E. Novel composition

The system should represent meaningful but bizarre combinations rather than failing because the exact phrase was absent from a dictionary.

## F. Contradiction tests

The system should notice incompatibilities such as:

```text
The door is fully open.
The same door is fully closed at the same time.
```

when the ontology says those states are mutually exclusive.

## G. Compression measurements

Measure at several levels:

1. serialized bytes
2. unique concept count
3. unique relation count
4. deduplication across paraphrases
5. shared structure across a corpus

Raw bytes are not the only useful measure. A verbose debug JSON representation may be physically larger than English while still exposing major structural deduplication potential.

---

# Development order

Recommended immediate sequence:

1. typed semantic graph
2. propositions as first-class nodes
3. negation and modality
4. state/change representation
5. ontology + identity
6. time
7. belief/knowledge/desire
8. causation
9. quantity/reference
10. frame/lexical expansion
11. ambiguity
12. cross-lingual tests
13. primitive-discovery tooling
14. Cognitive Engine integration

This ordering deliberately builds representational safety before vocabulary breadth.

---

# v0.2 concrete target

The next code milestone should handle a compact but difficult mini-world involving people, objects, rooms, possession, movement, beliefs, and time.

Example story:

```text
John owned a red key.
John gave the key to Mary.
Mary put it in the kitchen.
Bob believes the key is still with John.
Later, Mary moved the key to the garage.
John does not know where the key is.
```

SemZip v0.2 should be able to answer from its graph:

- Who owns the key now?
- Where is it now?
- Where was it before?
- What does Bob believe?
- Is Bob's belief true?
- Does John know its location?

without solving those questions from the original English strings.

That is the first milestone where SemZip starts behaving like a tiny structured world model rather than a paraphrase demo.

---

# Non-goals for now

Do not yet:

- train a giant neural model
- chase every English word
- optimize byte-level compression
- build a polished UI
- move the core to Rust
- assume an LLM's generated graph is ground truth
- declare a final primitive inventory

First prove the representation deserves to exist.
