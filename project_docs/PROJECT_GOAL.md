# Coding AI Lab Project Goal

## Purpose

This branch turns the upstream SmolLM-style repository into a beginner-readable coding-AI lab.

The first goal is not to train a new model. The first goal is to create a fast browser test surface where we can run small coding prompts, save outputs, and build a baseline before fine-tuning.

## Current target

Use GitHub Pages to host a static browser app that can:

- check browser support for WebGPU and WASM
- load a small Hugging Face model in the browser
- run simple coding prompts
- copy or export outputs
- save a local session log for comparison

## Non-goals for the first version

- no from-scratch pretraining
- no server backend
- no user accounts
- no repo editing agent
- no fine-tuning UI
- no automatic grading

## Practical success condition

The first successful test is:

1. open the GitHub Pages site
2. load the 135M model
3. run a simple coding prompt
4. copy or export the result

Quality can be weak at first. Weak answers still matter because they define the baseline we need to improve.
