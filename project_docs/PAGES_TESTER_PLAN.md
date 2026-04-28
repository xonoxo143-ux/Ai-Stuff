# Pages Tester Plan

## Purpose

The Pages tester is the first runnable surface for this project.

It should answer one question quickly:

> Can a small coding model run in the browser and produce testable coding answers?

## First user flow

1. Open the Pages site.
2. Browser support is checked automatically.
3. Select the default 135M model.
4. Tap `Load Model`.
5. Select a built-in coding prompt.
6. Tap `Run Prompt`.
7. Read the output.
8. Rate the answer.
9. Save the result to the page log.
10. Export JSON or Markdown.

## Included panels

- header with global status
- browser runtime support
- model setup
- prompt editor
- output viewer
- session results log
- beginner help section

## Included controls

- Check Browser Support
- Load Model
- Unload Model
- Reset Page
- Run Prompt
- Stop Generation
- Clear Prompt
- Copy Prompt
- Copy Output
- Save Result to Page Log
- Export Results JSON
- Export Results Markdown
- Copy All Results
- Clear Session Log

## First model choices

- `HuggingFaceTB/SmolLM2-135M-Instruct`
- `HuggingFaceTB/SmolLM2-360M-Instruct`
- custom model ID for advanced testing

## First prompt categories

- write a function
- explain code
- fix a bug
- write tests
- explain a coding concept
- custom prompt

## What this page does not do yet

- does not fine-tune
- does not grade automatically
- does not edit repositories
- does not save results permanently
- does not require a server

## Next improvements after first test

- add side-by-side model comparison
- add automatic syntax/test checks for simple Python snippets
- add more prompt packs
- add baseline result files to the repo
- add a Python fine-tuning lane after the browser baseline is understood
