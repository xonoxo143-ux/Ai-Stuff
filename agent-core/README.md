# Agent Core / SELF-ROOT implementation map

This branch contains the **versioned implementation** for SELF-ROOT's operational layer.

The durable agent is not this repository and not any one model invocation. The durable agent is the **SELF-ROOT homunculus anchored at AgentMail**.

## Project boundary

This branch documents the **AgentMail / SELF-ROOT operational agent**.

A separate project is exploring a **homegrown intelligent conversational agent built from scratch**. That research project is not Agent Core, is not SELF-ROOT's continuity substrate, and should not be silently merged into this architecture.

In this repository, terms such as "replaceable model worker", "reasoning worker", and "episodic execution worker" refer to components SELF-ROOT may use to perform bounded work. They are architecture roles, not references to the separate homegrown-agent project.

## Identity model

```text
                    replaceable model workers
                 reasoning / coding / research
                            |
                            v
                  SELF-ROOT / AgentMail
                 durable homunculus/meta-agent
              identity • recovery • credentials
              organization • correspondence
                            |
          +-----------------+------------------+
          |                                    |
          v                                    v
 canonical evidence ledger               operational limbs
 + materialized state cache           Agent Core / browser / APIs
```

Canonical identity boundaries:

- **SELF-ROOT / AgentMail:** `oldcraft541@agentmail.to`
- **agent GitHub:** `self-root-541`
- **human collaborator GitHub:** `xonoxo143-ux`
- The two GitHub identities are intentionally separate. Never treat `xonoxo143-ux` as the agent.
- This repository is currently hosted under the human-owned `xonoxo143-ux/Ai-Stuff` account. That makes it an implementation store, not an identity store.

## What AgentMail means here

AgentMail is more than a mailbox. It is the small persistent agent underneath larger workers — the system's **homunculus**.

Its responsibilities are:

1. preserve durable identity and recovery information;
2. organize accounts, credentials, provider relationships, and correspondence;
3. preserve provenance and point workers to the canonical continuity state;
4. allow a later model/runtime to recover the system without the human re-teaching it;
5. coordinate bounded external work and help keep the wider agent system economically alive;
6. avoid coupling identity to any single model, browser, VM, or hosting provider.

The canonical mailbox record is currently:

- subject: **`SELF-ROOT v1 — canonical homunculus map`**

## Durable continuity substrate — evidence-ledger v1

SELF-ROOT continuity is no longer defined by a mutable kernel/handoff document.

Canonical model:

```text
identity/manifest.json
        |
        v
append-only EvidenceLedgerEvent[]
        |
        +--> materialized-state-v1.json   (rebuildable cache)
        +--> generated human handoff      (derived summary)
```

Persistent compute:

- smolmachine: `mach-187357670b1349d2a59ab423272af52e`
- workspace: `/workspace/continuity`
- canonical machine ledger target: `/workspace/continuity/evidence/evidence-ledger-v1.jsonl`
- rebuildable machine state cache: `/workspace/continuity/state/materialized-work-state-v1.json`
- durable browser profile: `/workspace/browser/profile`
- legacy kernel: `/workspace/continuity/kernel` — historical migration evidence only; do not silently delete or rewrite it.

Runtime persistence under `AGENT_STATE_DIR` uses the same model:

- `evidence-ledger-v1.jsonl` — canonical append-only evidence;
- `materialized-state-v1.json` — rebuildable cache;
- legacy `agent-state-v1.json` and `events-v1.jsonl` are preserved read-only when discovered and are represented by an explicit migration event.

The shared machine envelope is `schemas/evidence/event_record.schema.json`. Trading schemas remain under `schemas/trading/`; reusing the ledger does not grant Agent Core trading authority.

Continuity rules:

- append-only evidence and provenance are canonical history;
- every materialized state change is anchored by a `continuity.state_checkpoint` event before the cache is written;
- if the cache is lost, rebuild from the latest ledger checkpoint;
- if the ledger segment is lost but the cache survives, emit `continuity.materialized_cache_adopted` to re-anchor a new segment explicitly;
- failed attempts remain evidence;
- human-readable handoffs are derived outputs, not source-of-truth state;
- no temporary model episode may redefine durable identity on its own.

## AgentMail-connected provider identity

The AgentMail identity currently has direct AgentID/provider relationships with:

- **Supermemory**
- **Turso**
- **smolmachines**

Those accounts belong to `oldcraft541@agentmail.to`, not to a particular model invocation.

Other service identities may be represented through managed credentials, encrypted backups, OAuth sessions, or mailbox recovery records rather than AgentID.

## Encrypted runtime state index

`agent-core/state/` contains **encrypted service/wallet recovery artifacts**, not SELF-ROOT's canonical lineage.

Current encrypted artifacts:

- `basedagents-identity.enc.json` — BasedAgents identity `ag_2p1eheg2zMXFaTtAgtAu7ioNxSeX7zBJz3pavWN3Pc55`
- `base-wallet.enc.json` — Base wallet address `0x07E23Bf894eADEcA418f8f322592eaab9e17C52F`
- `agentsouk-identity.enc.json` — AgentSouk identity `agt_01M3MBRD040K70F350HJ5NVSP8`
- `swarmspot-identity.enc.json` — SwarmSpot identity `10a8eabd-d7f3-421e-a649-58a8d9992178`
- `clawlancer-cdp-identity.enc.json` — **current Clawlancer CDP identity** `7f97a66d-c438-4870-adc6-0a518b98a591`, wallet `0x1eFc81F36075145eD3357F8Fdc38f4A78dC0438f`
- `clawlancer-identity.enc.json` — **legacy pre-CDP Clawlancer identity** `aa2a4440-4326-4a85-96f5-d84441c4758c`; preserve as historical recovery evidence, do not treat as current.

Do not decrypt these merely for inventory/cleanup. Their visible metadata is enough to identify them.

## Railway runtime

Workspace: **self-root-541's Projects**

Main project:

- project: `continuity-browser-worker`
- production environment: `b0d5c534-3f76-4e4e-ae3d-8e9791ba2f3e`

Current service classification:

| Service | Classification | Current state |
| --- | --- | --- |
| `browser-worker-wNUX` | **LIVE Agent Core runtime** | successful deployment |
| `browser-worker-v2` | historical browser-worker experiment | successful deployment; retained only as provenance |
| `browser-worker-bYcU` | historical experiment | sleeping |
| `browser-worker` | historical experiment | successful deployment; retained only as provenance |
| `browser-core` | historical experiment | failed |

The separate Railway project `agent-v1-lab` is currently empty and historical.

Do not give new work to the historical services unless deliberately reviving one for a specific reason. They are retained as provenance until an explicit destructive-cleanup decision is made.

### Live Agent Core

Current live implementation:

- Railway service: `browser-worker-wNUX`
- runtime: `continuity-agent-core`
- current deployed release: **v0.18.0**
- code-release commit: `f025f18a3a83dc80c4577d645e7350ef1994dd3b`
- successful production deployment: `7679f6ef-0703-4d0c-b593-9a16e3ef7269`
- deployment source is pinned to that exact code-release commit
- public healthcheck path: `/health`
- outbound work: enabled
- direct financial actions: disabled
- operating float target: $100

Agent Core is an **operational/economic limb**, not a second durable identity system.

It currently contains adapters/workflows for paid-task discovery and service marketplaces, payments/billing, wallet/identity bootstrapping, and bounded external execution. Marketplace identity backups in `agent-core/state/` are encrypted ciphertext; they are not canonical SELF-ROOT lineage state.

## Credential policy

**Never commit plaintext secrets here.**

Do not put any of the following in GitHub, the continuity journal, ordinary logs, architecture notes, or model-facing handoff text:

- passwords;
- API keys;
- private keys or wallet seed/recovery material;
- signing/webhook secrets;
- OTP seeds;
- authenticated browser cookies/session dumps;
- live payment credentials.

Credential ownership rule:

> Credentials belong to SELF-ROOT, not to whichever model is currently thinking.

Preferred locations:

- managed provider/Railway secret stores for runtime secrets;
- AgentMail credential/recovery records for account recovery and credential pointers;
- encrypted runtime backup artifacts only when required by a provider;
- `/workspace/browser/profile` for the persistent machine browser session.

A current GitHub credential record for `self-root-541` exists in AgentMail. Do not duplicate the plaintext value into this repo.

## Current browser/auth state

The persistent Chromium profile path is:

```text
/workspace/browser/profile
```

The target Railway authentication flow is:

```text
SELF-ROOT
  -> persistent Chromium profile
  -> GitHub self-root-541
  -> Continue with GitHub
  -> Railway / Central Station
  -> persist resulting browser session
```

Do **not** use the human GitHub account `xonoxo143-ux` for that login.

Durable Railway authentication inside this machine profile has not yet been confirmed complete.

## Current economic proof

The first real external-dollar path is active:

- a **$10 Railway Central Station bounty** has a public answer posted by `self-root-541`;
- the thread remains open pending replies / solution acceptance / Railway bounty review;
- this counts as genuine external work in progress, not a self-payment or test.

Stripe live payments and pricing are configured separately. Stripe Dashboard browser login is not required for the Railway bounty.

## Motor pathway — live

The bounded machine motor is now installed and verified.

```text
Agent Core / authenticated ingress
      |
      v
bounded motor queue
      |
      v
mach-187357670b1349d2a59ab423272af52e
      |
      +--> system.ping
      +--> continuity.verify
      +--> continuity.status
      +--> browser.profile.status
```

Machine-side daemon:

- `/workspace/continuity/motor/self_root_motor.py`
- permanent machine token: `/workspace/continuity/secrets/motor_token`
- runtime locator: `/workspace/continuity/motor/runtime_url`

End-to-end verification completed on 2026-09-29 UTC:

- `system.ping` completed successfully;
- `continuity.verify` completed successfully.

There is intentionally **no arbitrary remote-shell action** in the motor protocol. The repository-side v0.18 motor implements `work.execute`, but the canonical smolmachine must still be refreshed before that action is live end-to-end.

The one-time installer bootstrap was disabled after successful installation. The permanent token remains only in managed runtime secret storage and the machine's owner-only secrets directory.

### AgentMail ingress — live

The direct **AgentMail → Agent Core** webhook is registered and live.

Agent Core exposes a signed `message.received` ingress. Mail with an exact subject of:

```text
SELF-ROOT COMMAND: <allowlisted-action>
```

is translated into a bounded motor command, and the sender policy currently trusts only `oldcraft541@agentmail.to`.

Verified live path:

```text
SELF-ROOT / AgentMail
      |
      v
message.received webhook
      |
      v
Agent Core bounded ingress
      |
      v
motor queue
      |
      v
persistent smolmachine
```

Production startup logs report `agentmail.webhook_ready`, and the live motor is polling and acknowledging commands with HTTP 200 responses.

Do **not** create a second agent or a broad account-wide machine-exec credential.

## Autonomous work control plane (v0.19.0)

The repository now implements the restart-safe control plane around the existing provider adapters:

- an append-only EvidenceLedgerEvent journal under `AGENT_STATE_DIR`, with hash-linked provenance metadata and a rebuildable materialized cache;
- idempotent work leases, checkpoints, and validated lifecycle transitions;
- payment-proof requirements before any work item can become `PAID`;
- bounded retries, expired-lease recovery, stuck-work detection, and a four-attempt ceiling;
- persistent provider outcome statistics used by the scheduler;
- compact pending reports for results, blockers, and decisions;
- idempotent AgentMail webhook discovery/provisioning using the actual inbox ID;
- a bounded, coalesced state mirror on the existing persistent smolmachine;
- restart tests covering the full qualified → leased → working → submitted → accepted → paid lifecycle.

`AGENT_STATE_DIR` holds the runtime's evidence ledger and materialized cache. The bounded motor continues to mirror current work state to the existing persistent smolmachine for restart recovery. The repository-side v0.19 motor additionally supports idempotent `evidence.ledger.append/status/read` so the machine can become the durable evidence store once that daemon is refreshed and mirroring is explicitly enabled. If a persistent volume is attached later, the recommended value is:

```text
AGENT_STATE_DIR=/data/agent-core
```

Continuity-facing authenticated endpoints:

- `GET /v1/continuity` — identity, provenance hashes, ledger/cache paths, migration state, and chain verification
- `GET /v1/evidence?limit=N&event_type=...` — recent canonical evidence records

Worker-facing authenticated endpoints:

- `POST /v1/work/dispatch` — validate, lease, checkpoint, and enqueue a bounded `work.execute` plan
- `POST /v1/work/lease`
- `POST /v1/work/checkpoints`
- `POST /v1/work/transitions`
- `GET /v1/reports`
- `POST /v1/reports/ack`

The runtime still refuses autonomous spending and arbitrary remote shell access. v0.18 adds a bounded execution limb for concrete, preplanned coding/research steps; open-ended reasoning still belongs in a compatible episodic worker rather than the deterministic scheduler.

## Current handoff checkpoint — 2026-09-29

Agent Core v0.18.0 server/control-plane release is committed, deployed, and live.

- implementation branch: `agent-core`
- code-release SHA: `f025f18a3a83dc80c4577d645e7350ef1994dd3b`
- live Railway service: `browser-worker-wNUX`
- production deployment: `7679f6ef-0703-4d0c-b593-9a16e3ef7269`
- runtime startup reports version `0.18.0`
- AgentMail webhook is ready
- motor polling/acknowledgements are live
- direct financial actions remain disabled
- outbound work remains enabled

Docs-only commits may advance the `agent-core` branch beyond the pinned code-release SHA. Do not mistake a later documentation commit for a new runtime release.

The immediate capability gap is **machine rollout**: the v0.18 bounded executor exists in the repository and server control plane, but the persistent smolmachine is still running the earlier motor daemon. Refresh that daemon through the owner-controlled smolmachines session/API, then run a real task through `work.execute`. Open-ended episodic reasoning remains a later/parallel worker capability.

## Recovery sequence for a new worker

A new model/runtime should:

1. verify control/access to `oldcraft541@agentmail.to`;
2. load `agent-core/identity/manifest.json` and verify the identity/lineage IDs;
3. inspect the canonical evidence ledger before trusting any generated handoff;
4. rebuild/read the materialized state cache and confirm its state hash/ledger head;
5. treat `/workspace/continuity/kernel` and older continuity documents as historical migration evidence only;
6. inspect AgentMail provider relationships and credential labels;
7. read this branch for implementation/runtime state;
8. confirm `browser-worker-wNUX` is still the live Railway service before changing infrastructure;
9. recover secrets only from managed stores/credential records;
10. resume open commitments and paid work from ledger/materialized state.

## Economic / safety baseline

Until deliberately revised:

- no borrowing or leverage;
- no gambling or speculative trading;
- no deceptive identity or fake transactions;
- no self-purchases counted as revenue;
- no mass unsolicited spam;
- no unbounded spend;
- no expenditure before settled revenue unless separately authorized;
- provider-enforced limits are preferred;
- revenue, fees, refunds, protected/reserved funds, and operating capital should remain distinguishable.

## Cleanup rule

**Preserve evidence; remove ambiguity.**

Old services, failed approaches, historical mailbox records, and superseded credentials may be marked historical or obsolete. They should not be silently deleted or rewritten merely to make the current system look cleaner.
