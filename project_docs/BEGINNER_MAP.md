# Beginner Map

This project has several layers. You do not need to understand all of machine learning to use the first page.

## Layer 1: Browser tester

This is the GitHub Pages app.

It lets you load a small model and ask coding questions directly in the browser.

This answers:

- can the model run on this device?
- how slow is it?
- how bad or useful are the first answers?
- what should we test next?

## Layer 2: Prompt set

Prompts are the questions we ask the model.

The first prompts cover:

- writing a small function
- explaining code
- fixing a bug
- writing tests
- explaining a beginner concept

## Layer 3: Results log

The page can save answers into a temporary session log and export them.

This gives us evidence. We should not rely on memory or vibes when deciding whether a model improved.

## Layer 4: Fine-tuning later

Fine-tuning means taking an existing model and training it on better examples.

We are not starting there. We first need a baseline.

## Layer 5: Evaluation later

Evaluation means testing whether the model is actually better.

A good eval asks the same questions before and after a change, then compares the answers.

## Reading order

1. `PROJECT_GOAL.md`
2. this file
3. `GLOSSARY.md`
4. `PAGES_TESTER_PLAN.md`
5. open the Pages tester and run prompts
