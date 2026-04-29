# Android Coding Fine-Tune Plan

## Purpose

Build a small, practical Android coding assistant focused on our actual workflow:

- explain Android errors plainly
- repair small Java/Kotlin/XML/Manifest snippets
- avoid fake Android APIs
- obey constraints such as “no XML layout” or “use Storage Access Framework”
- produce complete, minimal files when requested

This project is not trying to train a general coding model from scratch. The goal is a narrow Android helper that can improve from focused examples.

## Current baseline

Observed so far:

- Colab T4 runtime works.
- Hugging Face model loading works.
- `SmolLM2-135M-Instruct` runs but gives weak/incomplete Android code.
- `SmolLM2-360M-Instruct` runs in Colab and in browser when using the safe runtime path.
- 360M browser rule from testing:
  - 135M: WebGPU / q4 works.
  - 360M: WASM / q8 works.
  - 360M: WebGPU / q4 and q4f16 produced corrupt output on the tested phone.

## First training target

Start with Android code review and repair, not full app generation.

Primary behavior:

> Given requirements plus bad Android code, produce a corrected small Android file or snippet that obeys the requirements exactly.

This is higher value than asking the model to create full apps. It matches how we usually work: inspect a broken snippet, explain what went wrong, and patch the smallest correct piece.

## Data files

- `evals/android_coding_eval_v1.json`
  - Baseline test prompts.
  - Contains expected traits and failure signs.
  - Used before and after training.

- `datasets/android_coding_seed_v1.jsonl`
  - Seed training examples.
  - One JSON object per line.
  - Each example has `instruction`, `input`, `output`, and metadata.

## Evaluation workflow

1. Load the base model in Colab.
2. Run every eval prompt.
3. Save raw outputs.
4. Review each output as `bad`, `partial`, or `good`.
5. Record common failures.
6. Fine-tune only after the baseline is clear.
7. Run the same eval again after training.

## Rating rubric

### Good

- Uses real Android APIs.
- Obeys every user constraint.
- Gives complete code when complete code is requested.
- Avoids unrelated imports/classes.
- Does not rely on missing XML/resources unless asked.
- Keeps the answer small and direct.

### Partial

- Mostly correct but has one fixable issue.
- Code shape is useful but incomplete.
- Uses real APIs but misses one constraint.

### Bad

- Invents APIs or classes.
- Ignores explicit constraints.
- Uses XML/layout resources when told not to.
- Produces incomplete code.
- Explains confidently but gives broken Android behavior.
- Repeats the bad code instead of repairing it.

## First fine-tune shape

Use LoRA or QLoRA rather than full training.

Candidate base models:

- `HuggingFaceTB/SmolLM2-360M-Instruct`
- a small code-specialized model if browser/runtime support is acceptable
- larger models only after the dataset and eval process are working

## Compute plan

Use free/cheap compute first:

1. Colab T4 for environment proof and small experiments.
2. Kaggle as a backup/repeatability lane.
3. Paid 24GB GPU only if free compute blocks progress.
4. Avoid expensive H100-class rentals until the notebook, data, and eval loop are already proven.

## Do not do yet

- Do not train from scratch.
- Do not build a giant dataset before reviewing failures.
- Do not optimize for broad coding skill before Android repair skill.
- Do not treat a single successful output as proof of improvement.
- Do not trust model answers without eval review.

## Next step

Run the eval pack against the current base model, collect outputs, and turn the failures into additional seed examples.
