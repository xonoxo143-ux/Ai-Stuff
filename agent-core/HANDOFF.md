# Agent Core handoff

_Last updated: 2026-09-30_

## Project boundary

This handoff is for the **AgentMail / SELF-ROOT operational agent** only.

It is not the separate homegrown conversational-agent research project. Keep those projects separate unless the human explicitly integrates them.

## Resume here

Agent Core **v0.19.0** is live in production.

- Repository: `xonoxo143-ux/Ai-Stuff`
- Branch: `agent-core`
- Code-release SHA: `707414f883dc4a66c4e608330385b9c795efee9f`
- Live Railway project: `continuity-browser-worker`
- Production environment: `b0d5c534-3f76-4e4e-ae3d-8e9791ba2f3e`
- Live service: `browser-worker-wNUX`
- Service ID: `08ef56b4-1e47-41ff-99de-95eec675ff83`
- Successful deployment: `38ae8cd5-92f7-412d-89cd-a5a309c47d86`
- Runtime startup reports version `0.19.0`
- Outbound work: enabled
- Direct financial actions: disabled
- Operating float target: $100

The Railway start command is pinned to the code-release SHA above. Later docs-only commits may advance the branch without changing the running release.

## Canonical continuity model — v0.19

The old mutable continuity kernel is **no longer canonical**.

Canonical SELF-ROOT continuity is:

```text
agent-core/identity/manifest.json
        |
        v
append-only EvidenceLedgerEvent[]
        |
        +--> materialized-state-v1.json   (rebuildable cache)
        +--> generated handoff/status     (derived)
```

Shared contract:

- `agent-core/schemas/evidence/event_record.schema.json`

Trading contracts remain isolated under:

- `agent-core/schemas/trading/`

Reusing the EvidenceLedgerEvent envelope does not give Agent Core trading authority.

Runtime files under `AGENT_STATE_DIR`:

- `evidence-ledger-v1.jsonl` — canonical append-only history for the current ledger segment
- `materialized-state-v1.json` — rebuildable cache
- `agent-state-v1.json` — legacy snapshot, migration evidence only if present
- `events-v1.jsonl` — legacy event journal, migration evidence only if present

Migration rules:

1. never overwrite/delete legacy evidence during migration;
2. write a canonical evidence checkpoint before writing derived materialized state;
3. if materialized state is deleted, rebuild it from the latest ledger checkpoint;
4. if the ledger is missing but materialized state survives, emit `continuity.materialized_cache_adopted` and explicitly start/re-anchor a new ledger segment;
5. bind recovered materialized state to the SELF-ROOT identity ID before merging it;
6. human-readable handoff files are summaries, not source-of-truth state.

## Identity anchor

- identity ID: `self-root-541`
- lineage ID: `self-root-541`
- display name: `SELF-ROOT`
- primary mailbox: `oldcraft541@agentmail.to`
- agent GitHub identity: `self-root-541`
- human collaborator GitHub: `xonoxo143-ux`

Do not treat `xonoxo143-ux` as the agent identity.

Static manifest:

- `agent-core/identity/manifest.json`

Credentials remain outside the manifest and evidence ledger except as non-secret references.

## Runtime continuity APIs

Authenticated endpoints:

- `GET /v1/continuity`
  - identity manifest
  - identity/config hashes
  - ledger/cache status
  - migration state
  - ledger-chain verification
- `GET /v1/evidence?limit=N&event_type=...`
  - recent canonical EvidenceLedgerEvent records

Compatibility key `durability` still exists in status/health responses but is deprecated in favor of `continuity`.

## Verified migration behavior

Tests pass for:

- canonical evidence append + normal restart;
- rebuilding materialized state after cache loss;
- re-anchoring a new ledger segment after ledger loss while materialized state survives;
- importing a v1 legacy snapshot without modifying legacy files;
- machine evidence-ledger append idempotency;
- existing work/payment restart lifecycle;
- bounded `work.execute` dispatch lifecycle.

Production migration verification on 2026-09-30:

- v0.19 deployment reached SUCCESS;
- old smolmachine snapshot acknowledgement initially exceeded the old 128 KiB ack limit and returned HTTP 413;
- v0.19 release was corrected to accept bounded 1 MiB motor acknowledgements;
- the final deployment returned HTTP 200 for snapshot recovery;
- production logged `durable_work_state.merged` with source `smolmachine`.

Therefore current work state survived the continuity migration.

## Persistent machine boundary

Canonical persistent machine:

- `mach-187357670b1349d2a59ab423272af52e`
- workspace: `/workspace/continuity`
- browser profile: `/workspace/browser/profile`

Repository v0.19 motor supports:

- `system.ping`
- `continuity.verify`
- `continuity.status`
- `browser.profile.status`
- `state.snapshot.read`
- `state.snapshot.write`
- `work.execute`
- `evidence.ledger.append`
- `evidence.ledger.status`
- `evidence.ledger.read`

Machine target paths after the v0.19 daemon refresh:

- canonical machine ledger: `/workspace/continuity/evidence/evidence-ledger-v1.jsonl`
- evidence ID index: `/workspace/continuity/evidence/event-index-v1.json`
- materialized work-state mirror: `/workspace/continuity/state/materialized-work-state-v1.json`
- old `/workspace/continuity/kernel` remains historical migration evidence.

### Important rollout boundary

The persistent smolmachine still runs the **earlier daemon**. Its existing `state.snapshot.read/write` compatibility path is live and recovered state successfully, but do not claim these are live on the machine yet:

- `work.execute`
- `evidence.ledger.append/status/read`

The server-side code and repository daemon are ready. `EVIDENCE_MOTOR_MIRROR_ENABLED` is intentionally off until the machine daemon is refreshed and verified.

## Bounded work execution

The v0.19 server supports `POST /v1/work/dispatch` and typed `work.execute`.

Allowed machine work primitives remain bounded:

- public GitHub clone;
- public HTTPS fetch with private-address rejection;
- per-job file read/write;
- patch application;
- git inspection;
- JSON/Python/Node syntax checks;
- local no-hook git commit.

There is no arbitrary shell action, credential-bearing clone URL, wallet/spend operation, or push action.

## Next major milestone

Use the existing owner-controlled smolmachines session/API when available to:

1. replace only `/workspace/continuity/motor/self_root_motor.py` with the pinned v0.19 repository file;
2. restart the existing motor service;
3. run `evidence.ledger.status`;
4. enable `EVIDENCE_MOTOR_MIRROR_ENABLED=true` only after that succeeds;
5. verify an evidence record is durably appended and idempotently re-accepted;
6. run one harmless `work.execute` smoke job;
7. then give SELF-ROOT a real paid coding/research assignment.

Do not create a second machine or weaken the bounded-motor security model to finish this rollout.

## Recovery order for a new worker

1. Verify control/access to `oldcraft541@agentmail.to`.
2. Read `agent-core/identity/manifest.json`.
3. Read/verify the canonical evidence ledger before trusting generated handoff text.
4. Rebuild/read materialized state and compare state hash / ledger head.
5. Treat old kernel and legacy continuity docs as migration evidence only.
6. Inspect current Railway deployment before changing infrastructure.
7. Recover credentials only from managed secret/credential stores.
8. Resume open commitments and paid work from the materialized state + evidence history.

## Pickup rule

Before changing infrastructure:

1. read this file and `agent-core/README.md`;
2. verify the pinned runtime SHA and current Railway deployment;
3. distinguish runtime release commits from later docs commits;
4. continue from **Next major milestone** unless newer evidence supersedes it;
5. record material architecture/deployment changes as new evidence/continuity records rather than rewriting history.
