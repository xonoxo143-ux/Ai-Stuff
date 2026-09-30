# Kaggle GPU Training — Agent Language V0

## Verified environment

Observed on 2026-09-30 for Kaggle account `selfroot`:

- GPU runtime: 2 × NVIDIA Tesla T4
- VRAM reported per visible device: ~15.6 GB
- PyTorch: 2.10.0+cu128
- CUDA visible: yes, 2 devices
- GPU quota: 108,000 seconds = 30 hours/week
- GPU used at verification: 14.731 seconds
- TPU quota: 72,000 seconds = 20 hours/week
- Quota refresh reported by Kaggle: 2026-10-03T00:00:00Z

Treat quota values as observed state, not a permanent contract. Query Kaggle before planning a large sweep.

## Frozen scientific boundary

Phase 1 is immutable:

- tag/release: `v0-phase1-2048`
- source commit: `716366777c5c6552bdff03c32aef117261324b53`
- checkpoint SHA256: `820ef9c11ab1322748b9f5032691a0d6c0eac0afc10df00dbc2c77b454eaa131`
- step: 2048
- sampled bytes: 16,777,216
Cloud work continues on `experiment/v0-kaggle-t4`.

Do not overwrite or reinterpret the Phase-1 checkpoint as an exact resume under new code. Use `--fork-from` when crossing from the frozen CPU implementation into the cloud implementation. Normal `--resume` remains strict and requires matching Git/config/runtime provenance.

## Compute strategy

The default unit is **one model per T4**, not one model across two T4s.

The V0 hybrid has only ~1.06M parameters. Data-parallel synchronization is likely to cost more than it saves. Use the two GPUs as two independent experiment lanes unless a benchmark proves otherwise:

- GPU 0: experiment A
- GPU 1: experiment B

This converts one Kaggle T4×2 session into two simultaneous architecture/training experiments.

## Cloud execution changes

The cloud branch adds:

- explicit CPU/CUDA device selection;
- GPU-safe evaluation and generation;
- synchronized CUDA timing so throughput is real rather than asynchronous launch time;
- optional FP16 autocast + GradScaler for T4 Tensor Cores;
- optional fused AdamW;
- CUDA RNG state in checkpoints;
- strict runtime provenance for future resumes;
- `--fork-from` for intentional transitions from the frozen Phase-1 checkpoint;
- vectorized batch extraction with unchanged RNG positions and byte contents;
- optional vectorized hybrid forward.
### Vectorized hybrid forward

The reference implementation launches the local GRU and patch encoder once per 4-byte patch. At sequence length 128 that means 32 tiny patch-level calls.

The vectorized path precomputes all patch summaries/local inputs in batches and runs the local GRU over all patch lanes together. The recurrent global-state sequence is still preserved.

On CPU tests, reference and vectorized paths produce bit-identical forward logits from the same weights and inputs. Gradient reduction order differs, so the optimization intentionally begins only after the frozen Phase-1 boundary.

## Benchmark gate

Before Phase 2, run:

```bash
python3 -m agent_language.benchmark_v0_cloud \
  --checkpoint /path/to/v0-phase1-2048-hybrid.pt \
  --device cuda:0 \
  --steps 32 \
  --warmup 4
```

The benchmark compares:

1. reference FP32;
2. reference FP16 + fused AdamW;
3. vectorized FP32;
4. vectorized FP16 + fused AdamW.

Select the fastest profile that remains numerically stable. Prefer the smallest sufficient optimization stack: CUDA + vectorized FP32 is the default candidate; FP16 and fused AdamW must each show a stable measurable gain before becoming defaults.

Cloud acceleration must not become an inference requirement. Every architecture survivor is checked against `LOCAL_DEPLOYMENT_GATE.md` on the phone or another ordinary CPU target.
## Phase-2 fork example

After the benchmark selects a runtime profile:

```bash
python3 -m agent_language.train_v0 \
  --config configs/v0_first_run.json \
  --model hybrid \
  --run-dir runs/v0-kaggle-phase2-a \
  --fork-from /path/to/v0-phase1-2048-hybrid.pt \
  --max-step 3072 \
  --device cuda:0 \
  --execution vectorized \
  --precision fp16 \
  --fused-adamw
```

Use those acceleration flags only if the benchmark supports them.

For two independent experiments in one T4×2 session, run separate processes pinned to different visible GPUs or use `--device cuda:0` and `--device cuda:1` with separate run directories.

## Quota discipline

- Prepare/download/build corpora before enabling a GPU when possible.
- Do not leave an accelerator notebook idle.
- Prefer parallel A/B experiments over DDP for this model size.
- Checkpoint at phase/evaluation boundaries.
- Preserve failed variants and their reason for rejection.
- Judge experiments by task/validation gain per GPU-minute, not by raw throughput alone.

The goal of the free compute is not simply to finish the current curriculum faster. It is to make high-value architecture comparisons cheap enough that weak directions can be killed quickly.
