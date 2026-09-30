# Continuity migration — Evidence Ledger v1

Date: 2026-09-30 UTC

## Decision

SELF-ROOT / Agent Core continuity has been migrated from the bespoke mutable continuity-kernel model to an event-sourced model derived from the uploaded autonomous-trading handoff bundle's shared EvidenceLedgerEvent contract.

The trading project's role boundaries remain separate. Only the generic evidence-ledger infrastructure was promoted into SELF-ROOT continuity.

## Canonical model

- Identity anchor: `agent-core/identity/manifest.json`
- Canonical runtime history: `evidence-ledger-v1.jsonl`
- Derived/rebuildable cache: `materialized-state-v1.json`
- Human-readable handoffs: derived summaries, not source-of-truth state
- Legacy kernel/snapshot/journal: migration evidence only; preserve read-only

Canonical schema:

- `agent-core/schemas/evidence/event_record.schema.json`

Trading-only schemas remain isolated under:

- `agent-core/schemas/trading/`

## Runtime release

- Agent Core: v0.19.0
- Code-release SHA: `707414f883dc4a66c4e608330385b9c795efee9f`
- Railway production deployment: `38ae8cd5-92f7-412d-89cd-a5a309c47d86`
- Live service: `browser-worker-wNUX`
- financialActionsEnabled: false
- outboundWorkEnabled: true

## Evidence semantics

Each canonical record follows EvidenceLedgerEvent v1 and includes:

- event ID
- correlation ID
- optional parent event ID
- event type
- occurred/recorded timestamps
- source
- payload
- software/config provenance

Agent Core additionally records ledger sequence, previous-event hash, and event hash inside provenance.

State writes follow:

1. append `continuity.state_checkpoint` to the evidence ledger;
2. atomically write the materialized cache pointing at that source event/head.

Recovery follows:

- cache missing -> rebuild from latest evidence checkpoint;
- ledger missing but cache survives -> emit `continuity.materialized_cache_adopted` and explicitly re-anchor a new segment;
- legacy v1 snapshot present -> emit `continuity.legacy_snapshot_imported`; preserve legacy files unchanged;
- recovered state carrying another identity ID -> reject merge.

## Verification

Passing tests:

- normal evidence-ledger persistence/restart
- cache rebuild from ledger
- ledger re-anchor from surviving cache
- legacy snapshot migration without overwrite
- bounded motor state snapshot
- bounded work executor and path-traversal rejection
- machine evidence append/read/status idempotency
- restart/payment-proof lifecycle
- work dispatch -> motor -> acknowledgement lifecycle

Latest suite: 9 passed, 0 failed.

## Production migration result

The first v0.19 deployment exposed an old motor-ack body ceiling: the persisted smolmachine snapshot exceeded 128 KiB and the acknowledgement returned HTTP 413.

The release was corrected to accept bounded 1 MiB motor acknowledgements. Final production deployment then returned HTTP 200 for the recovery acknowledgement and logged:

`durable_work_state.merged source=smolmachine`

Therefore the pre-migration materialized work state survived and was merged into v0.19.

## Persistent-machine rollout boundary

Repository v0.19 motor now implements:

- `evidence.ledger.append`
- `evidence.ledger.status`
- `evidence.ledger.read`
- `work.execute`

The existing smolmachine is still running its earlier daemon. The backwards-compatible state snapshot path is working, but full evidence mirroring is intentionally disabled until the machine daemon is refreshed and verified.

After refresh:

1. verify `evidence.ledger.status`;
2. enable `EVIDENCE_MOTOR_MIRROR_ENABLED=true`;
3. verify an event append twice (second must be idempotent duplicate);
4. verify ledger head/count;
5. then run a harmless `work.execute` smoke job.

Do not create a second machine or add arbitrary shell access to complete this rollout.

## Source-design invariant retained

Append-only raw evidence outranks derived state. Derived state may be regenerated. Historical failure/migration evidence is preserved rather than rewritten.
