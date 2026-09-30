# Shared machine contracts

The continuity substrate is the generic **EvidenceLedgerEvent** contract in `evidence/event_record.schema.json`.

Trading contracts remain namespaced under `trading/`. Reusing the evidence ledger does **not** grant Agent Core or SELF-ROOT any trading authority.

Continuity rules:

1. Append-only evidence is canonical history.
2. Materialized state is a rebuildable cache.
3. Identity is a small immutable anchor plus versioned account/capability references; secrets never belong in the manifest or ledger.
4. Human-readable handoffs are generated summaries, not the source of truth.
5. Legacy continuity files are migration evidence and are never silently overwritten or deleted.
