# V0 Training Data Sources

## WikiText-2 raw
- Purpose: broad natural prose / language-modeling substrate.
- Source mirror: https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip
- Upstream dataset: Salesforce WikiText.
- License: CC BY-SA / GFDL as documented by the upstream dataset.
- Raw zip SHA-256: ef7edb566e3e2b2d31b29c1fdb0c89a4cc683597484c3dc2517919c615435a11

## OpenAssistant OASST1
- Purpose: real multi-turn conversational language.
- Source: https://huggingface.co/datasets/OpenAssistant/oasst1/resolve/main/2023-04-12_oasst_ready.messages.jsonl.gz
- License: Apache-2.0.
- Ready-messages SHA-256: 286a6e9a5a413b3272ae9c0b5a20d327983dea1c24342ae28cb244a6da65185c

## Project-generated streams
Reasoning and semantic-plan realization records are generated deterministically by
`agent_language/build_v0_corpus.py`. Validation uses separate seeds and exact
train/validation duplicate hashes are rejected.

## Frozen V0 mixture
- 50% WikiText prose
- 25% OASST1 dialogue
- 12.5% project-generated reasoning
- 12.5% semantic-plan -> response realization

The downloaded corpora and generated binary mixtures are intentionally not committed.
Their hashes are recorded in `configs/corpus_v0_manifest.json`.
