# Agent Ecology Model v0

This directory contains the first learned model intended to inhabit the Agent v0 runtime.

It is **not** a language model and it is **not** a prompt-orchestrated set of personas. It is a learned sparse recurrent computational ecology designed to test the architecture before language becomes a confound.

## Current model

The model contains:

- persistent private recurrent state for each capability cell;
- learned cell signatures;
- a cheap learned need/signature router;
- top-k cell recruitment at runtime;
- a small bounded shared workspace;
- bounded learned public messages;
- recurrent internal thought steps;
- full routing traces for later causal analysis.

Training is intentionally allowed to spend more compute than deployment. The current training path evaluates all candidate cells, but only selected top-k cells commit private-state updates and expose messages. Evaluation/export uses the sparse path.

The model therefore follows the project rule:

> Use expensive learning to teach cheap thinking.

## First curriculum

The first controlled curriculum is a stateful register-machine world with:

`SET, ADD, SUB, MUL, NEG, ABS, HALF, SQUARE`.

This is not meant to approximate conversation. It tests:

- persistent internal state;
- order-sensitive composition;
- selective recruitment;
- recurrent computation;
- novel recombination.

Several operation pairs are withheld during training and forced during recombination evaluation.

## First phone candidate

The initial hardware candidate uses:

- 16 learned capability cells;
- 4 active cells per thought step;
- 96-dimensional private cell state;
- 4 workspace slots;
- 32-dimensional routing signatures;
- 32-dimensional public messages;
- 3 recurrent thought steps per external event.

The first completed training run produced 1,403,810 parameters and used all 16 cells. Its evaluation MAE was approximately 0.229 on seen-composition programs and 0.252 on programs forced to contain held-out operation pairs.

These figures are a checkpoint, not evidence that the architecture is superior. The immediate purpose is to get the learned ecology onto the physical phone and measure its real execution behavior.

## Android export

`export_onnx.py` exports exactly **one thought step** rather than baking the whole recurrent loop into the model file.

That is deliberate. The Android Agent runtime owns recurrence, state lifetime, instrumentation, and eventual interaction with the wider capability/motif ecology.

The export package contains:

- `agent-ecology-thought-step.onnx`
- `agent-ecology-thought-step.json` manifest with model config, initial learned workspace, SHA-256, and interface metadata.

## Current limits

The following are not yet implemented and must not be implied by the v0 model:

- trained adaptive halting;
- learned/persisted interaction motifs;
- slow structural promotion/pruning;
- language;
- semantic or episodic long-term memory;
- proof that sparse runtime wins on phone hardware;
- proof that capability cells become clean human-interpretable specialists;
- proof that this architecture beats a conventional recurrent/dense baseline.

Those are subsequent experiments.

See `docs/AGENT_V0_SPEC.md` for the architecture contract.
