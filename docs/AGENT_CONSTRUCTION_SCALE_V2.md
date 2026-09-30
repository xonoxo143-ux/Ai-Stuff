# Construction Store Scaling v2 — Result

**Date:** 2026-09-29  
**Status:** immutable experiment record

## Corrected result

Three seeds, 500 queries per stage.

```text
store size: 10 → 1,000 → 10,000 → 100,000 constructions
accuracy:   100% at every stage and seed
mean candidates loaded: ~1.4 throughout
p95 candidates loaded: 2 throughout
mean pattern bytes loaded: ~70–75 B throughout
median lookup: ~0.05 ms → ~0.08 ms
mean postings returned: ~4.7 → ~11.4
100k cold store: ~48.7 MB
```

The discrimination index is disk-backed SQLite. Query signatures are derived only from the current utterance; candidate construction payloads are fetched only after signature retrieval.

A naive global matcher would examine every stored construction, growing 10,000× over the same range.

## Interpretation

In the controlled construction regime, dormant language capacity can grow by four orders of magnitude while active candidate payload remains nearly constant.

## Limitations

This does not test broad natural-language ambiguity, semantic/pragmatic context, multilingual morphology, noisy input, or open-domain grammar induction.

## Next step

Integrate the surviving perception mechanism with memory/cognition and the pointer/copy producer in Whole-Agent Closure v0.