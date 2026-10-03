# Agent Effect Address + Reachability v0 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Question

Can a developing agent retrieve useful executable computation from current state + desired outcome without receiving module identity, and can immediate causal testing choose among retrieved candidates?

## Setup

- 12,800 executable unary modules.
- Module addresses were seven-dimensional behavioral signatures from probe executions.
- Four recurrently useful operations were hidden among thousands of distractors.
- A small MLP was trained from developmental traces only.
- Input: current behavioral signature + target signature + their difference.
- Output: predicted behavioral address for the next operation.

No pretrained model was used.

## Addressing result

Held-out in-distribution developmental traces:

```text
top-1 next-operation recall   99.6%
top-8 recall                 100.0%
```

Deeper unseen composition traces:

```text
top-1   68.5%
top-8   88.5%
```

Interpretation: learned effect-based addressing is viable in the toy domain, but depth shift degrades the address.

## Closed-loop failure

For each state, the agent retrieved eight candidates, executed them, and selected the one with the best immediate reduction in target error.

Deep composition performance was poor.

Inspection showed the failure mode:

> a candidate can create strong immediate progress while moving to a state from which the goal is not reachable.

## Oracle future-reachability diagnostic

A bounded reachability oracle was inserted only for candidate selection; addressing was unchanged.

Diagnostic sample:

```text
myopic causal selector        6.25%
future-reachability oracle   30.00%
```

On teacher-solvable tasks:

```text
5.6% → 66.7%
```

The oracle sometimes used nominal distractor modules to create valid alternate paths, so its gain was not merely restoring the original hidden sequence.

This localizes a major failure to downstream consequence evaluation.

## Learned value replacement

A small goal-conditioned value network was trained on 1,304 candidate-consequence examples generated during development.

Labels represented bounded future reachability.

Fresh deep-task sample:

```text
teacher ceiling            25%
myopic selector            29%
learned-value selector     19%
```

On the teacher-solvable subset:

```text
myopic   32%
learned  36%
```

The learned value branch is rejected.

## Surviving conclusions

1. Behavioral/effect signatures can serve as learned computational addresses.
2. Address quality itself degrades under deeper composition and needs future work.
3. Immediate causal improvement is not a sufficient definition of 'matters.'
4. Downstream reachability is a high-leverage variable.
5. A generic shallow goal-conditioned value MLP is not enough.

## Next question

What representation lets a module carry a compact model of:

```text
what future states/capabilities it tends to make reachable
```

so that a new goal can cheaply evaluate reusable modules without exhaustive rollout?

Research successor features, reusable option models, compact planning abstractions, and uncertainty-aware search before the next build.
