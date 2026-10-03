# Agent semantic retrieval v0

**Date:** 2026-09-28  
**Status:** cheap baseline implementation  
**Role:** retrieve a bounded subset of semantic memory instead of dumping the whole store into language context

## Why this exists

The Agent architecture separates:

```text
stored semantic memory
!=
active conversational context
```

A growing semantic store cannot simply be appended to every prompt forever.

The first retrieval implementation is intentionally simple:

- in-memory backend: token-overlap baseline;
- SQLite backend: FTS5 shortlist + normalized lexical-overlap scoring;
- `SemanticRetrievalCapability`: capability-level wrapper that only offers when a memory match clears a threshold.

This is a **baseline**, not the final retriever.

## Local scratch check

Using SQLite FTS5 with roughly 10,000 synthetic memory items plus a few target facts:

```text
favorite fruit lookup:  ~267 us
github branch lookup:    ~45 us
phone model lookup:      ~34 us
broad topic-42 lookup:   ~6.2 ms
index build:             ~23 ms
```

These numbers are from the current container and are only order-of-magnitude guidance.

## Research reason for starting lexical

Recent retrieval work does not support assuming dense embeddings always win.

Useful examples:

- LiveRAG 2025 found hybrid sparse+dense retrieval competitive, while neural reranking improved ranking quality but added very large cost.
- A 2026 text/table RAG benchmark found BM25 could beat dense retrieval on its financial corpus, while two-stage hybrid retrieval + reranking performed best overall at higher cost.
- HORMA (2026) shows another relevant direction: organize memory hierarchically, then retrieve only minimal sufficient context rather than treating similarity search as the entire memory problem.

Therefore the build order is:

```text
cheap lexical baseline
→ measure misses
→ add dense retrieval only where lexical fails
→ test hybrid fusion
→ add reranking only if the quality gain repays latency
```

## Important architecture boundary

The retriever is a capability.

FTS5 is **not** the architecture.

A later dense, graph, temporal, hierarchical, or learned retriever can replace it behind the same public contract.

## Next test

Once the corrected language-spine screen settles the first language backend:

1. disable direct semantic-memory dumping in the composer;
2. attach `SemanticRetrievalCapability`;
3. grow the store with distractor facts;
4. test recall quality, prompt size, latency, and wrong-memory injection;
5. compare lexical vs small dense vs hybrid retrieval.
