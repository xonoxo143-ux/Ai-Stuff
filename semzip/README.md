# SemZip

SemZip is an experimental semantic codec and semantic substrate: convert surface
language into canonical inspectable meaning, reuse shared semantic structure, reason
over world state, and keep language itself at the edge rather than treating wording
as the internal representation.

The project is deliberately dependency-light while the representation is being
discovered. Unsupported meaning is preserved as ambiguity where possible or rejected
rather than silently guessed.

## Current v0.3 checkpoint

SemZip now includes:

- canonical recursive `Meaning` expressions with stable semantic hashes
- nested propositions for belief, negation, modality, conditionals, and causation
- deterministic world state with history and arbitrary past-state queries
- explicit belief/knowledge state that does not overwrite reality
- transitive concept ontology
- semantic molecules for shared operations such as `CHANGE`, transfer, exchange,
  and loan/return obligation
- atomic compound execution so half an exchange cannot corrupt world state
- instance identity separate from lexical concept identity (`key`, `key#2`, ...)
- first-class ambiguity that preserves candidate meanings without mutating reality
- canonical unordered ambiguity, bundles, and sets
- quantified sets (`ALL`, `SOME`, `NONE`, `MOST`, `EXACT(n)`)
- semantic queries independent of the original wording
- compression metrics for exact deduplication and deeper structural reuse
- automatic repeated-substructure discovery for candidate semantic molecules
- JSON serialization/deserialization and recursive schema validation
- a trust bridge for accepting proposed meanings from future external/learned parsers
- a tiny English/Spanish transfer adapter proving separate languages can converge on
  the same language-neutral semantic object

## Demonstrated world-model gate

The v0.2/v0.3 mini-world consumes:

```text
John owned a red key.
John gave the key to Mary.
Mary put it in the kitchen.
Bob believes the key is still with John.
Later, Mary moved the key to the garage.
John does not know where the key is.
```

The semantic world can then answer, without rereading those strings:

```text
owner              -> Mary
current location   -> garage
previous location  -> kitchen
Bob believes owner -> John
Bob is correct      -> false
John knows location -> false
```

Run the integrated checkpoint with:

```bash
cd semzip
PYTHONPATH=src python benchmarks/progress_gate.py
```

## Compression experiment

Different lexical viewpoints can compile to the same meaning:

```text
give / receive   -> possession CHANGE
buy / sell       -> EXCHANGE of two possession CHANGEs
borrow / lend    -> temporary transfer + return OBLIGATION
```

`benchmarks/progress_gate.py` measures exact semantic deduplication separately from
structural reuse. `metrics.repeated_structures()` recursively searches a corpus for
recurring semantic subtrees instead of requiring candidate primitives to be named in
advance.

## Multilingual probe

The current bilingual adapter is intentionally tiny, but these independently parsed
forms converge to the same semantic hash:

```text
John gave Mary the book.
Mary received the book from John.
John le dio el libro a Mary.
Mary recibió el libro de John.
```

The result is not a claim of broad multilingual parsing. It demonstrates that the
semantic IR does not have to encode English word order.

## Current blocker: general surface parsing

The semantic representation is now substantially more capable than the hand-written
surface grammars. For example, the IR can validate representations for possibility,
nested belief+possibility, and conditionals, while the current regex parser cannot
recover those meanings from unrestricted prose.

Run:

```bash
PYTHONPATH=src python benchmarks/parser_boundary.py
```

The next major step is therefore not more regex rules. It is a general semantic
front-end (learned parser, external semantic parser, or another model) that proposes
SemZip structures through the validated JSON trust bridge. The substrate should remain
the authority: parser output is a proposal until it passes SemZip schema validation.

## Quick tests

```bash
cd semzip
python -m unittest discover -s tests -v
```

The original v0.1 `SemZipCodec` and CLI remain available for the small TRANSFER
round-trip experiments.

## Architecture

```text
surface language / images / sensors
              |
              v
       parser / adapter
              |
              v
      validated SemZip IR
          /    |     \
         /     |      \
        v      v       v
   world     memory   semantic hash
   model              / deduplication
      |
      v
 reasoning / planning / downstream modules
```

## Design rule

A false canonicalization is worse than an explicit unknown. SemZip should preserve
ambiguity, provenance, and uncertainty rather than manufacture convenient certainty.
