# FluidLM-0 experiment plan

## Hypothesis

A trainable, explicitly fluid-like dynamical state can carry enough sequential information to perform non-trivial next-character prediction.

## Null result

The idea should be considered unsuccessful in its current form if training repeatedly produces one or more of the following:

- loss stays near the uniform-character baseline,
- the model only memorizes local character frequencies,
- changing fluid parameters has no meaningful effect on learned behavior,
- the flow variables collapse to a static encoding and the PDE terms become irrelevant,
- numerical stability requires making the dynamics so weak that the model behaves like an ordinary shallow recurrent network.

A negative result is useful; it tells us which part of the analogy does not survive implementation.

## Initial measurements

For every run, save:

- training and validation loss,
- seed and all model parameters,
- generated text sample,
- final checkpoint,
- density trace,
- vorticity trace,
- kinetic-energy trace.

## First ablations after the smoke test

Run matched-seed experiments with:

1. advection disabled,
2. diffusion disabled,
3. viscosity near zero,
4. pressure response disabled,
5. token forcing retained but fluid evolution nearly frozen.

If performance is unchanged, the fluid dynamics are decorative rather than computational.

## Later comparison

The first meaningful baseline should be a similarly sized character-level GRU or simple recurrent network trained on the exact same corpus and number of optimization steps.

The interesting question is not only perplexity. We also care about whether FluidLM exposes interpretable dynamical structures such as vortices, stable channels, separatrices, and history-dependent loops.
