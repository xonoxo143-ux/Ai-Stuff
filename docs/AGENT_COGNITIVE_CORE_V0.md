# Agent Cognitive Core v0

Date: 2026-09-28
Status: ACTIVE EXPERIMENT

Goal: test whether one learned non-language processor can perform multiple kinds of cognition and generalize beyond the sizes and combinations seen during training.

## Task anchor

This project is still building the intelligent conversational agent itself from scratch.

Language perception and production are interfaces around the missing middle:

language perception
  -> non-language state
  -> COGNITIVE CORE
  -> new non-language state
  -> language production

No pretrained LLM is used by this cognitive-core experiment.

## Shared benchmark representation

Every family uses the same slot schema:

(kind, symbol_a, symbol_b, symbol_c, operator, position)

The same bounded symbol vocabulary is also the answer vocabulary. TRUE and FALSE are ordinary special symbols. There is no task-specific neural head.

The five families are:

1. transitive directed relations;
2. ordered state updates using SET, +1 and -1;
3. graph reachability;
4. modular rule induction from examples;
5. associative key/value memory.

OOD evaluation increases chain length, event length, graph size/path length, example combinations, or memory load.

Every family has an exact oracle solver. CI checks hundreds of IID and OOD generated examples against those oracles.

## Why the core became a factor graph

Several cheaper formulations failed locally before v0 was frozen.

A dense all-pairs slot MLP was too slow for its size.

A recurrent all-slot attention processor was much faster, but a transitive-relation specialist stayed at chance.

Explicitly linking slots that mention the same symbol also stayed at chance.

The successful change was to give shared symbols their own persistent recurrent states instead of treating identity only as a property of fact slots.

## Current processor

v0 is a recurrent factor graph:

fact / event / query slots
  <-> role-typed messages
persistent symbol nodes

Each thought step:

1. slots send role-specific messages to symbols in argument positions A, B and C;
2. symbol nodes recurrently update;
3. symbol states send role-specific messages back to slots;
4. slots receive a global context summary;
5. slots recurrently update;
6. original slot and symbol inputs may be re-injected.

The same weights are reused across thought steps and across every task family.

The answer head is pointer-like: the query state scores the same persistent symbol states used during cognition.

## Local discriminating results

These are single-seed local results and are not yet durable evidence.

Transitive specialist after 200 updates:

6 thought steps: 100% IID, 97.5% OOD.
1 thought step: 100% IID, 91.5% OOD.

Other specialist sanity checks:

relation: 100% IID, 97.5% OOD.
rule: 97% IID, 99% OOD.
memory: 100% IID, 100% OOD.
state: 46% IID, 27.5% OOD.
graph: 100% IID, 46% OOD.

State is learnable but hard. Graph reachability currently fits IID and fails to extrapolate, making it a useful falsification family.

Matched 250-update shared five-family run:

one-pass factor: 73.5% IID mean, 54.2% OOD mean, 4.6 s.
6-step recurrent factor: 76.2% IID mean, 66.2% OOD mean, 15.4 s.

OOD breakdown, one-pass -> recurrent:

relation 86% -> 94%.
state 19% -> 26%.
graph 42% -> 50%.
rule 55% -> 62%.
memory 69% -> 99%.

Input reinjection ablation:

with reinjection: 66.2% OOD mean.
without reinjection: 62.5% OOD mean.

Thought-depth ablation on the same trained model:

1 step: 38.0% OOD mean.
2 steps: 48.6%.
4 steps: 63.4%.
6 steps: 63.4%.
8 steps: 63.4%.

Memory specifically went from 10% at one step to 34% at two steps to 100% at four steps.

This is the first local sign that repeated processing is carrying useful computation rather than merely adding parameters.

## Rigorous CI gate

The workflow runs:

1. shared-core comparison across three seeds:
   flat MLP, one-pass factor, recurrent factor, recurrent factor without input reinjection;

2. specialist ceilings:
   the same recurrent processor trained separately on each family;

3. thought-depth probe:
   one trained shared core evaluated at 1, 2, 4, 6 and 8 recurrent steps.

Primary metrics are IID accuracy, OOD accuracy, specialist/shared gap, recurrence gain, reinjection gain, thought-depth curve, and wall-clock cost.

## Kill and redesign conditions

Do not keep the factor graph because it is elegant.

Redesign if replicated tests show:

- recurrence does not improve OOD performance enough to justify cost;
- shared training stays far below specialists with no transfer benefit;
- graph/state failures are fixed only by brute-force scale;
- performance depends on human structure the language-perception layer cannot plausibly supply;
- later transfer tests show no reusable computational knowledge.

## Next gate if v0 survives

Train on four families and measure adaptation speed on the fifth against a fresh core and a specialist.

Then connect controlled language-perception states to the core and require one system to switch cognitive task families turn-to-turn.
