[Reading 54 lines from start (total: 54 lines, 0 remaining)]

# AI Workbench / Agent Research

This repository is the working laboratory for the homegrown Agent project.

## Goal

Build a generally capable worker agent from our own learned machinery.

The target system should understand instructions, communicate clearly, plan,
use tools, preserve relevant state, recover from failures, and complete real
work. Conversation is an interface, not the product boundary.

A pretrained LLM may be used during development as a teacher, critic,
scientist, or control. It must not silently become the deployed agent's
cognitive core.

## Current research direction

The current language baseline is a small causal byte Transformer. It is a
control, not an architectural commitment.

The previous GRU/patch hybrid is retired as a mainline training candidate.
The next challenger is DeltaHybrid V1: state-heavy Gated-Delta-style sequence
processing with occasional exact-attention blocks.
## Compute architecture

The project uses a simple separation of roles:

- Optiplex server — durable storage, credentials, repositories, scheduling,
  experiment submission, result collection, dashboards, and control-plane work.
- Kaggle CPU — substantive CPU experiments, correctness tests, reference
  implementations, multi-seed probes, data/evaluation jobs.
- Kaggle 2×T4 — GPU training, architecture races, throughput tests, and
  promoted long runs.
- Phone — optional user interface / emergency access; not an infrastructure
  dependency and not an AI-compute tier.

The Optiplex currently has a 2 TB main Linux drive, a 500 GB Toshiba USB
external drive for bulk/archive use, and a 32 GB USB device reserved for a
future deliberate role.

See docs/AGENT_CURRENT.md for the authoritative project state and
agent-model/DELTA_HYBRID_V1.md for the next architecture build.
## Repository role

Git stores source, configs, evaluation definitions, architecture notes, small
results, and reproducible experiment manifests.

Large datasets, caches, and most checkpoints belong on controlled storage or in
ephemeral Kaggle runs rather than in Git.

Historical Android/workbench and earlier chatbot experiments remain in the
repository as evidence. They are not the current project objective unless
docs/AGENT_CURRENT.md explicitly re-promotes them.
