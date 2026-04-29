# Notebooks

This folder is for Colab/Kaggle notebooks used by the Android coding assistant workflow.

## Current proof

The first Colab proof confirmed:

- hosted T4 runtime connects
- CUDA is available
- PyTorch sees the Tesla T4
- Hugging Face packages install
- SmolLM2 models load and generate

The initial notebook may currently exist at the repository root as `Welcome_To_Colab.ipynb`. That is acceptable for now. It can be moved here later.

## Expected notebook flow

A training/eval notebook should run in this order:

1. Check GPU.
2. Install dependencies.
3. Load model and tokenizer.
4. Load eval prompts from `evals/android_coding_eval_v1.json`.
5. Run baseline outputs.
6. Save outputs to a file.
7. Fine-tune only after baseline review.
8. Re-run the same eval after fine-tuning.

## Runtime notes

Known browser runtime rules are documented at:

- `docs/runtime-notes.html`

Current project rule:

- 135M: WebGPU/q4 works in browser.
- 360M: WASM/q8 works in browser.
- 360M WebGPU q4/q4f16 produced corrupt output on the tested phone.

## Storage rule

Do not trust Colab runtime storage as permanent. Save useful outputs to GitHub, Google Drive, or downloadable files.
