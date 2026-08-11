# SemZip VM Branch

This branch (`semzip-vm`) forks from the preserved `semzip` v0.3 checkpoint.

## Branch roles

- `semzip`: preserve and later continue the semantic-graph / semantic-codec prototype.
- `semzip-vm`: pursue the Semantic Virtual Machine direction without requiring backward compatibility with every v0.3 design choice.

## Semantic VM research goal

Build a compact executable semantic substrate where:

- surface language compiles into richer semantic representations;
- rich representations compile into a tiny stable VM kernel;
- world state is projected from an event/observation ledger;
- higher-level semantic operations are learned/discovered macros rather than automatically privileged primitives;
- compression / description cost helps decide whether a macro deserves to exist;
- a small recursive neural controller may eventually propose VM operations while the VM validates, executes, remembers, and verifies them.

## Immediate direction

1. Separate ownership from possession/custody/control.
2. Add levels of semantic equivalence rather than one all-or-nothing meaning hash.
3. Move the world model toward an event-ledger-first architecture.
4. Define the smallest viable executable kernel.
5. Compile existing high-level molecules such as EXCHANGE and LOAN into kernel programs.
6. Replace simple structural-frequency metrics with a description-cost objective.
7. Let repeated experience propose/promote reusable semantic macros.
8. Preserve reconstruction, prediction, and reasoning fidelity as compression increases.

The old branch remains available specifically so useful semantic-parser, ontology, and codec work can continue independently later.
