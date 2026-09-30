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
The chatbot integration track now outranks the isolated developmental-interference track for research priority. Existing project evidence still supports heterogeneous capability machinery and multi-timescale development, but the qualitatively missing capability is a broad productive language/semantic interface.

## Provisionally settled
1. **External retrievable knowledge can carry much of the factual burden.** The core need not memorize an encyclopedia parametrically. Retrieval remains part of the agent only if our own machinery selects, interprets, rejects, and uses retrieved evidence.
2. **Fixed subword tokenization is not fundamental.** Byte/character models can be competitive, but naive byte/character processing pays a substantial sequence-length cost. Learned or structured compression/patching is the stronger family.

## Current highest-value open question
> For a small, from-scratch conversational agent, which language spine gives the best whole-agent tradeoff between productive generation, sample efficiency, exact retrieval/copying, persistent state, and local inference cost?

Current candidates:
- compact causal Transformer baseline;
- selective SSM/recurrent spine (Mamba/RWKV family);
- hybrid recurrent/SSM + sparse/local attention;
- byte/character interface with learned multiscale patches rather than naive one-byte-one-step processing.

## Current research inference
Evidence does **not** justify replacing attention entirely. Pure SSMs are competitive at language modeling and efficient recurrent inference, but controlled comparisons report weaknesses on copying, in-context learning, and some long-context reasoning. Hybrid SSM+attention systems recover or exceed Transformer quality in those regimes while retaining much of the recurrent efficiency.

For this project, exact access to retrieved evidence and conversational history is unusually important. Therefore the leading engineering hypothesis is:
> **compact persistent recurrent/SSM state for cheap continuity + a small precise attention path for retrieved/current evidence + a byte/patch language interface.**

This is a hypothesis to test, not an architecture commitment.

## Next research question
Can a small hybrid language spine trained from scratch beat both a compact Transformer and a pure recurrent/SSM model on the *combined* gate of language quality, evidence copying/use, multi-turn continuity, and local inference economics?

## Research-cycle note — 2026-09-29
Small-scale evidence now supports treating the hybrid recurrent plus limited precise-access family as provisionally preferred over pure recurrence for the first whole-agent comparison. The next research bottleneck is the training objective and curriculum for broad productive conversation; exact tiny-scale architecture remains an experimental question.
