# FluidLM

FluidLM is a small research prototype for testing one question:

> Can next-character language generation be driven by explicit fluid-like state dynamics rather than attention?

This is intentionally tiny and CPU-first. It is not intended to compete with modern language models yet. The first goal is to make the mechanism measurable and falsifiable.

## Core idea

Each character perturbs a 2D periodic semantic-fluid grid.

The state contains:

- **density**: where semantic activation is concentrated,
- **velocity X/Y**: how that activation is moving,
- **pressure response**: density gradients push on the velocity field,
- **diffusion**: smooths density,
- **viscosity**: smooths velocity,
- **advection**: the flow carries itself,
- **token forcing**: each observed character injects a learned redistribution/force pattern.

The updated fluid state is decoded into a probability distribution for the next character.

The grid is a torus (wraparound edges), so there are no artificial walls. This also gives us real 2D flow quantities such as vorticity.

## What counts as success

The first prototype is useful if it can demonstrate all of these:

1. Training loss falls substantially below an untrained/uniform baseline.
2. Generated text develops recognizable local language structure.
3. The hidden state remains numerically stable.
4. Fluid controls such as viscosity and diffusion produce measurable changes in the state dynamics.
5. Vortices, attractor-like regions, or other flow structures can be inspected rather than merely inferred from prose.
6. Fixed data + model configuration + random seed produces reproducible experiments.

A pretty sample is not enough. The experiment should tell us whether the fluid dynamics are actually doing useful computational work.

## Layout

```
text/fluidlm/
├── fluidlm/
│   ├── __init__.py
│   ├── corpus.py
│   └── model.py
├── tests/
│   └── test_fluidlm.py
├── train.py
├── visualize.py
├── requirements.txt
└── EXPERIMENT.md
```

## Quick local run

From `text/fluidlm`:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python train.py --corpus synthetic --steps 200 --out-dir outputs/quick
python visualize.py outputs/quick/trace.npz --out outputs/quick/flow.png
```

For a public-domain literary corpus:

```bash
python train.py --corpus tiny-shakespeare --steps 1000 --out-dir outputs/shakespeare
```

Other supported corpora:

- `synthetic` — deterministic built-in toy language, no network required.
- `tiny-shakespeare` — public-domain Shakespeare text.
- `alice` — Project Gutenberg's *Alice's Adventures in Wonderland*.

Downloaded corpora are cached under `data/cache/`.

## GitHub Actions

The repository workflow `fluidlm-train.yml`:

1. installs the CPU dependencies,
2. runs the unit tests,
3. trains a small FluidLM,
4. renders a diagnostic flow image,
5. uploads the checkpoint, generated sample, metrics, and fluid trace as an artifact.

Pushes to the `fluidlm-experiment` branch run a short synthetic smoke test. The workflow also supports manual corpus/parameter selection once it is available from the repository's Actions UI.

## Important limitation

This is a **fluid-inspired recurrent model**, not a claim that transformers or brains literally implement Navier-Stokes equations. The point of the prototype is to make that question experimentally accessible.
