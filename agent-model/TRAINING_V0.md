# Agent Language V0 Training

This is the first serious from-scratch language-learning run for the homegrown agent.

## Frozen comparison
- Candidate: BytePatchHybridV0 (local 4-byte patches + recurrent global state + bounded patch-memory attention).
- Control: causal byte Transformer, parameter matched within 2%.
- Both see the same source streams, curriculum, batch size, sequence length, optimizer, step count, and held-out evaluation suite.

## V0 curriculum
The 4,096-step run keeps the original 32 MiB sampled-byte budget but stages it deliberately.

### Phase 1 — language foundation (steps 1–2048) — COMPLETE
- 75% WikiText raw prose
- 25% held-in English OpenAssistant dialogue
- 0% explicit reasoning
- 0% semantic-plan examples
- Batch 64 means exactly 48 prose sequences + 16 dialogue sequences per step.
- Total sampled bytes: 16,777,216.
- Frozen release/tag: `v0-phase1-2048`.
- Frozen source commit: `716366777c5c6552bdff03c32aef117261324b53`.
- Frozen checkpoint SHA256: `820ef9c11ab1322748b9f5032691a0d6c0eac0afc10df00dbc2c77b454eaa131`.
- Final phase-valid BPB: 4.8939156542; best observed region was ~4.884–4.885 before the boundary.
- Original phone run demonstrated correctness but exposed thermal/scheduler limits; later phases move to a benchmark-gated Kaggle GPU fork.

### Phase 2 — conversation bridge (steps 2049–3072)
- 45% prose
- 40% dialogue
- 10% reasoning
- 5% planner → response

### Phase 3 — cognitive integration (steps 3073–4096)
- 30% prose
- 30% dialogue
- 20% reasoning
- 20% planner → response

## Data
From `agent-model/`:

```bash
python3 -m agent_language.fetch_v0_sources
python3 -m agent_language.build_v0_corpus --train-mb 16 --valid-mb 2
```

Downloaded corpora and generated binary streams stay local and are gitignored.
Expected hashes are frozen in `configs/corpus_v0_manifest.json`.

## Telemetry
At each evaluation checkpoint the trainer records:
- training bytes/sec;
- approximate conventional-token equivalent/sec (bytes/sec ÷ 4);
- cached generation bytes/sec;
- cached generation conventional-token equivalent/sec;
- current phase and exact per-source batch counts;
- train loss; fixed global validation loss; phase-matched validation loss; and both validation bits/byte measurements.

The token-equivalent rate is only a readability conversion. The model itself remains byte-native.

## Preflight
```bash
python3 -m pytest -q
python3 -m agent_language.preflight_v0
```

The deterministic interruption rehearsal uses `configs/v0_rehearsal.json`.
The serious run uses `configs/v0_first_run.json` and refuses to start from a dirty Git tree.

## First run
```bash
python3 -m agent_language.train_v0 \
  --config configs/v0_first_run.json \
  --model hybrid \
  --run-dir runs/v0-first-hybrid
```

Phase 1 was completed on the phone and frozen at step 2048. Do not mutate that checkpoint or source tag.

## Cloud continuation

Cloud continuation lives on `experiment/v0-kaggle-t4`. The trainer now supports CUDA, FP16 autocast, fused AdamW, synchronized GPU timing, strict runtime provenance, and a vectorized hybrid forward.

Crossing the frozen Phase-1 boundary is an intentional fork, not an exact resume:

```bash
python3 -m agent_language.train_v0 \
  --config configs/v0_first_run.json \
  --model hybrid \
  --run-dir runs/v0-kaggle-phase2 \
  --fork-from /path/to/v0-phase1-2048-hybrid.pt \
  --max-step 3072 \
  --device cuda:0 \
  --execution vectorized \
  --precision fp32
```

This is the minimum cloud profile currently worth carrying forward: CUDA plus the vectorized execution path, while keeping the model architecture and deployment path unchanged. FP16 and fused AdamW remain optional experiments and must earn their complexity through stable benchmarks. See `KAGGLE_V0.md` and `LOCAL_DEPLOYMENT_GATE.md`.

Then train the parameter-matched control with the identical curriculum and budget.

Do not change the corpus, curriculum, evaluation suite, or frozen Phase-1 artifacts after inspecting results. Any changed experiment gets a new version.
