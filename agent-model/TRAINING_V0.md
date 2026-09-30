# Agent Language V0 Training

This is the first serious from-scratch language-learning run for the homegrown agent.

## Frozen comparison
- Candidate: BytePatchHybridV0 (local 4-byte patches + recurrent global state + bounded patch-memory attention).
- Control: causal byte Transformer, parameter matched within 2%.
- Both see the same bytes, batch size, sequence length, optimizer, step count, and held-out evaluation suite.

## Data
From `agent-model/`:

```bash
python3 -m agent_language.fetch_v0_sources
python3 -m agent_language.build_v0_corpus --train-mb 16 --valid-mb 2
```

The expected corpus hashes are recorded in `configs/corpus_v0_manifest.json`.
Downloaded data and binary mixtures stay local and are gitignored.

## Preflight
```bash
python3 -m pytest -q
```

The deterministic interruption rehearsal uses `configs/v0_rehearsal.json`.
The serious run uses `configs/v0_first_run.json` and refuses to start from a dirty Git working tree.

## First run
```bash
python3 -m agent_language.train_v0 \
  --config configs/v0_first_run.json \
  --model hybrid \
  --run-dir runs/v0-first-hybrid
```

Then train the matched control with the same config:

```bash
python3 -m agent_language.train_v0 \
  --config configs/v0_first_run.json \
  --model transformer \
  --run-dir runs/v0-first-transformer
```

## Frozen behavioral evaluation
```bash
python3 -m agent_language.eval_v0 \
  --checkpoint runs/v0-first-hybrid/hybrid.pt \
  --model hybrid \
  --out runs/v0-first-hybrid/eval.json
```

Do not change the corpus, evaluation suite, or config after looking at first-run results. Any changed experiment gets a new config/version.
