# Glossary

## Model

The model is the AI brain. It has learned patterns from text and code.

## Tokenizer

The tokenizer turns text into smaller chunks the model can read.

## Prompt

The prompt is what you ask the model.

## Inference

Inference means asking a trained model for an answer.

The GitHub Pages tester is an inference tool.

## Training

Training means changing model weights using examples.

## Fine-tuning

Fine-tuning means starting with an existing model and training it more narrowly.

For this project, later fine-tuning would mean teaching a small model to answer coding tasks better.

## LoRA

LoRA is a cheaper way to fine-tune a model by training small adapter weights instead of changing the entire model.

## Dataset

A dataset is a collection of examples.

For a coding assistant, an example may include:

- instruction
- optional input code
- expected output

## Evaluation

Evaluation is testing whether a model actually improved.

A useful eval compares the base model against a changed model using the same prompts.

## WebGPU

WebGPU lets a browser use the device GPU for heavier computation.

If WebGPU is unavailable, the page can try a slower WASM path.

## WASM

WASM means WebAssembly. It lets the browser run fast compiled code.

For model testing, WASM is usually slower than WebGPU but more widely available.

## Baseline

A baseline is the first measured result before improvements.

Bad baseline answers are still useful because they show what needs to improve.
