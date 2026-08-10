# SemZip

SemZip is an experimental semantic codec: convert surface language into a compact,
canonical meaning graph, reason over that representation, and generate language back
from it.

This branch starts deliberately small. v0.1 is dependency-light and inspectable so
semantic loss is easy to find before adding neural parsers or large ontologies.

## Goals

- Canonicalize paraphrases into the same semantic representation.
- Preserve distinctions such as role changes and negation.
- Give every canonical meaning a stable semantic hash.
- Keep language generation separate from the semantic representation.
- Build benchmarks before scaling the ontology or parser.

## Current v0.1 scope

The seed parser handles a tiny TRANSFER domain and several English paraphrase forms,
including active, receive, and passive constructions. It is intentionally narrow:
unsupported text raises a clear error rather than pretending it understood.

## Quick start

```bash
cd semzip
python -m pip install -e .
python -m unittest discover -s tests -v

semzip encode "John gave Mary the book."
semzip compare "John gave Mary the book." "Mary received the book from John."
semzip roundtrip "The book was given to Mary by John."
```

## Architecture

```text
surface language
      |
      v
  parser/adapter
      |
      v
canonical semantic graph
      |
  +---+------------------+
  |                      |
  v                      v
reasoning / memory   semantic hash
  |
  v
language generator
```

Later versions can add AMR/FrameNet/WordNet/UCCA adapters, learned parsers, ambiguity
sets, richer temporal/modality representations, multilingual input, and a compiled
binary encoding. Those are intentionally not dependencies of this seed.

## Design rule

SemZip should fail loudly on unsupported meaning. A false canonicalization is worse
than no canonicalization.
