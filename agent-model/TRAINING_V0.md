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
- Post-freeze audit: 0/6 on `v0-frozen-2026-09-30`; greedy generation collapsed to spaces, and stochastic decoding produced letter/space fragments rather than coherent language.
- A train-derived held-out unigram baseline scores ~4.6384 BPB on the same 75/25 prose-dialogue mixture, so Phase 1 did not yet establish useful contextual language modeling despite improving from initialization.
- Scientific status at freeze: training run complete, but language capability was not established.
- 2026-10-02 postmortem: batch training and streaming inference used different causal alignment. The immediately previous byte had zero effect on the frozen model's final next-byte prediction. See `CAUSAL_ALIGNMENT_V0.md`.
- Preserve the frozen checkpoint as a failed-formulation artifact, but do not resume it or use it as a parent checkpoint.
- Phase 2 remains blocked. The corrected lineage restarts Phase 1 from fresh initialization.
- Original phone run demonstrated execution stability and exposed thermal/scheduler limits, but the later causal-alignment postmortem invalidated it as a correctness proof. Corrected experiments move to benchmark-gated GPU execution.

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

Cloud execution still uses the CUDA/vectorized trainer, but the frozen Phase-1 checkpoint predates the causal-alignment correction and is not a valid parent for future language training.

Start corrected Phase 1 from fresh initialization:

    python3 -m agent_language.train_v0 \
      --config configs/v0_first_run.json \
      --model hybrid \
      --run-dir runs/v0-kaggle-causal-v1 \
      --max-step 2048 \
      --device cuda:0 \
      --execution vectorized \
      --precision fp32

CUDA plus vectorized FP32 is the conservative first cloud profile. FP16 and fused AdamW remain experiment arms and must earn promotion through stable learning and throughput evidence. See CAUSAL_ALIGNMENT_V0.md, KAGGLE_V0.md, and LOCAL_DEPLOYMENT_GATE.md.

Train the parameter-matched control with the identical corrected curriculum and budget.

Do not change the corpus, curriculum, evaluation suite, or frozen historical artifacts after inspecting results. Any changed experiment gets a new version.
