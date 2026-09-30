# AGENT_RESEARCH_SYNTHESIS

Updated: 2026-09-29

## Preserved trajectory

### Hypothesis: the developmental cell ecology should become the whole chatbot
**Evidence/test:** Agent v0/v1 established useful causal recurrent mechanisms and localized destructive learning, but did not establish broad language generation.
**Result:** failed as a default architectural assumption.
**Revision:** use developmental machinery where it earns a role; do not require it to be the language substrate.

### Hypothesis: avoid Transformers / attention
**Evidence/test:** literature and project review showed attention remains unusually strong for precise relational access.
**Result:** rejected as an architectural rule.
**Revision:** Transformer/attention is an experimental variable; persistent state and attention may be complementary.

### Hypothesis: broad conversation requires broad factual knowledge in the generator parameters
**Evidence/test:** retrieval-augmented language modeling shows external addressable knowledge can carry substantial factual burden.
**Result:** provisionally settled against the strong form.
**Revision:** separate semantic/world memory from language capability. The generator must learn how to retrieve/use/reject evidence, not memorize all evidence.

### Hypothesis: fixed tokenization is necessary for an efficient language spine
**Evidence/test:** ByT5/CANINE establish token-free feasibility; MEGABYTE and BLT show that multiscale byte processing can recover efficiency and competitive quality.
**Result:** provisionally settled against necessity.
**Revision:** raw bytes/characters are a viable external interface, but naive one-byte-one-global-step processing is a poor default. Learned/local patching is the stronger family.

### Hypothesis: persistent recurrent/SSM state can replace attention wholesale
**Evidence/test:** Mamba and RWKV establish strong recurrent language modeling and attractive inference economics. Controlled Mamba comparisons show weaknesses in copying, in-context learning, and long-context reasoning; Mamba-2 hybrids recover these deficits and can outperform matched Transformers.
**Result:** weakened.
**Revision:** for this project, recurrent compression is best treated as cheap continuity, while a small attention path remains a strong candidate for precise access to current/retrieved evidence.

## Current synthesis
The highest-leverage architecture family is no longer “pick Transformer vs RNN.” The evidence points toward **different mechanisms for different information-access regimes**:

1. **Raw text boundary:** bytes/characters avoid a fossilized tokenizer and preserve exact text.
2. **Local composition / patching:** compress predictable byte spans before expensive global computation.
3. **Persistent recurrent/SSM state:** cheaply carry conversational continuity and slow context.
4. **Precise attention path:** directly access current-turn text, retrieved passages, names, code, and other evidence where lossy state compression is dangerous.
5. **External semantic/world memory:** hold broad factual knowledge outside the trainable generator.
6. **Homegrown generator:** produce every response from the system's own trained machinery; retrieval supplies evidence, not intelligence.

This division aligns with the project's existing hypothesis that attention and persistent state are complementary, but now has stronger external support and a concrete language-interface implication.

## Current question status
The question “must we use tokens?” is **provisionally settled: no**.
The broader question “what minimum from-scratch language machinery should we build?” remains **open**, but the search space is narrower: pure byte Transformer and pure recurrent replacement are weaker default bets than multiscale byte + recurrent/SSM + limited precise attention.

## Single highest-value next research question
> At small model/data budgets, does a hybrid recurrent/SSM + limited-attention language spine preserve the quality and exact evidence-use of a Transformer while materially improving persistent-state inference cost?

This question changes the roadmap more than another isolated cognition/plasticity study because answering it selects the machinery needed to close the first real conversational loop.

## Cheapest discriminating experiment worth running later
Train three genuinely from-scratch models on the same small corpus, same parameter/FLOP budget, same byte or byte-patch front end:
1. compact causal Transformer;
2. pure selective recurrent/SSM model;
3. hybrid with mostly recurrent/SSM blocks plus sparse/local attention.

Evaluate one combined gate:
- held-out next-byte/patch loss;
- short free-form conversational continuation;
- exact copying from an injected passage;
- answer from retrieved evidence including distractors;
- multi-turn entity/thread retention;
- latency, RAM, and bytes/sec on target local hardware.

Do not optimize architecture after the first run. A large hybrid gain on the combined gate earns engineering; a small gain does not.
