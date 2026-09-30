# AGENT_CURRENT

Updated: 2026-09-29

## Canonical persistence
This file and its paired research files are durably stored in GitHub repository `xonoxo143-ux/Ai-Stuff`, branch `agent-core`, at the repository root.

Paired canonical files:
- `AGENT_CURRENT.md`
- `AGENT_RESEARCH_FINDINGS.md`
- `AGENT_RESEARCH_SYNTHESIS.md`

Future research cycles must read these files from this branch first and write updates back to the same branch.

## Primary objective
Build a self-contained, from-scratch conversational agent that can move across topics, remember, reason, retrieve knowledge, and generate each response from its own learned machinery, without a pretrained LLM as hidden intelligence or response engine.

## Current whole-agent frontier
The chatbot integration track outranks isolated developmental/cognition benchmarks. The most important missing capability is now a broad productive language/semantic interface that can use external evidence, preserve conversational state, and generate coherent responses from homegrown learned machinery.

## Provisionally settled
1. **External retrievable knowledge can carry much of the factual burden.** The core need not memorize an encyclopedia parametrically. Retrieval remains part of the agent only if our own machinery selects, interprets, rejects, and uses retrieved evidence.
2. **Fixed subword tokenization is not fundamental.** Byte/character interfaces are viable, but naive byte-at-a-time global processing is inefficient; local composition/patching is better supported.
3. **Pure recurrence/SSM should not be the default first conversational spine.** Evidence from Griffin/Hawk, associative-recall studies, Taipan, and larger hybrid systems supports bounded recurrent/SSM state plus a limited precise-access mechanism for evidence-grounded conversation. Exact tiny-scale architecture details remain open.

## Current engineering prior
The best-supported first serious language-spine family is:
> **byte/character boundary + local/learned patching + mostly recurrent/SSM persistent state + limited local/sparse/selective attention + external semantic/world memory.**

This is a provisional engineering prior, not a final architecture. It should be overturned by matched tiny-model evidence if pure recurrence or a compact Transformer wins the combined whole-agent gate.

## Current highest-value open question
> For a small, from-scratch hybrid conversational spine, which training objective and curriculum most efficiently produces a broad productive semantic interface rather than merely low next-step prediction loss?

Research should compare independent paths such as:
- plain causal language modeling;
- dialogue-conditioned causal training;
- denoising or bidirectional auxiliary objectives;
- retrieval-conditioned generation;
- staged curricula that progressively add dialogue, retrieval, memory-conditioned generation, and topic switching.

## What is no longer the main research target
- repeated pure-Mamba-vs-Transformer literature comparison;
- isolated compositional OOD optimization unless whole-agent failures point back to it;
- developmental plasticity refinements without evidence that they unblock the conversational loop.

## Next research target
Determine which training objective/curriculum yields the largest whole-agent gain on:
- free-form conversation;
- topic switching;
- semantic/paraphrase transfer;
- retrieval-grounded answering with distractors;
- multi-turn reference/thread retention;
- compute and convergence efficiency.

## Cheapest later experiment
Fix one tiny hybrid spine and train matched variants under the strongest two or three curricula identified by research. Compare whole-agent behavior and training economics without changing the architecture between runs.
