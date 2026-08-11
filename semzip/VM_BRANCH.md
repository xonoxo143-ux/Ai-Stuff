# SemZip VM Branch

This branch (`semzip-vm`) forks from the preserved `semzip` v0.3 checkpoint.

## Branch roles

- `semzip`: preserve and later continue the semantic-graph / semantic-codec prototype.
- `semzip-vm`: pursue the Semantic Virtual Machine direction without requiring backward compatibility with every v0.3 design choice.

# SemVM v0.4 checkpoint

The v0.4 research prototype now demonstrates:

- ownership and possession as separate world relations;
- an append-only event ledger as durable memory, with current state as a projection;
- historical rewind and counterfactual branches;
- observations carrying confidence/provenance without automatically becoming reality;
- agent-specific belief branches that may become stale or false without corrupting reality;
- a deliberately tiny four-opcode kernel (`K0`..`K3`) for set, transition, require, and clear operations;
- transactional VM execution using a copy-on-write shadow rather than copying event history;
- high-level actions such as GIVE, LEND, SELL, and MOVE compiled into kernel programs rather than privileged VM instructions;
- layered equivalence: surface, pragmatic, proposition, world-transition, and exact-kernel levels;
- a synthetic grounded universe generating exact before/action/after experiences;
- description-length macro scoring based on realized non-overlapping substitution, including definition cost;
- lossless learned program macros that expand back to exact kernel programs;
- semantic abstraction discovery directly from anonymous before/after world deltas with action labels/programs hidden;
- recursive factorization in which a learned four-change exchange pattern can be represented as repeated smaller learned transfer patterns;
- a non-neural symbolic planner used as a correctness baseline and automatic source of controller training data;
- a strict JSON -> VM Program trust boundary that rejects malformed proposals and invented opcodes.

## Measured prototype results

These are engineering/research smoke tests, not claims about general intelligence or phone performance.

- New v0.4 local suite: 31/31 tests passing; consolidated branch gate: 11/11.
- 100,000 event records: about 15.5 MB in the Python prototype after atom interning (down from about 46 MB).
- 100,000 full VM programs: roughly 22,500 programs/sec in the current container after removing whole-ledger transaction copies.
- Balanced 1,000-experience world-delta corpus: base description cost 9,000 units; best discovered four-change pattern saves 2,228 units under the current toy cost model.
- Recursive abstraction: the strongest four-change reciprocal exchange pattern factors exactly into two uses of a smaller two-change transfer pattern.
- Optional Torch benchmark (not a core dependency): an anonymous candidate-operation scorer with 67 trainable parameters solved 300/300 unseen variable-sized toy worlds, including reference plans up to 8 steps. Deterministic graph-distance/search features are supplied by the VM, so this tests operation selection rather than learned graph search.

Run the deterministic gate with:

```bash
cd semzip
PYTHONPATH=src python -m unittest tests/test_vm_v04.py -v
PYTHONPATH=src python benchmarks/vm_progress_gate.py
```

The optional neural benchmark requires PyTorch:

```bash
PYTHONPATH=src python benchmarks/generic_controller.py
```

# Current blocker

The VM substrate can now execute, validate, remember, branch, compress, plan, and accept externally proposed kernel programs. The next major step toward the end goal is a **general learned compiler from unrestricted human language (and later other modalities) into rich SemZip/SemVM representations**.

The current execution environment does not contain a usable pretrained language/semantic parsing model for that experiment: `transformers`/`sentence-transformers`/ONNX/llama.cpp are unavailable, there are no cached Hugging Face models, and spaCy is installed without a language model. Expanding the old hand-written regex grammar would defeat the purpose and is not considered a valid continuation.

So further progress on the language front-end requires at least one external resource choice: bring in a pretrained model/runtime, obtain/train a dedicated text->SemVM compiler, or connect an external model to generate candidate programs through the existing strict validation bridge.

The core runtime remains dependency-light and should stay that way; neural compiler/controller experiments should remain replaceable boundary components.

# Research goal

Build a compact executable semantic substrate where:

- surface language compiles into richer semantic representations;
- rich representations compile into a tiny stable VM kernel;
- world state is projected from an event/observation ledger;
- higher-level semantic operations are learned/discovered macros rather than automatically privileged primitives;
- compression / description cost helps decide whether a macro deserves to exist;
- small recursive neural components can propose VM operations while the VM validates, executes, remembers, and verifies them.

The preserved `semzip` branch remains available so semantic-parser, ontology, and codec work can continue independently later.
