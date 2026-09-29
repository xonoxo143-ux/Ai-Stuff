# Agent Core / SELF-ROOT implementation map

This branch contains the **versioned implementation** for SELF-ROOT's operational layer.

The durable agent is not this repository and not any one model invocation. The durable agent is the **SELF-ROOT homunculus anchored at AgentMail**.

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
 continuity kernel                       operational limbs
 on persistent compute                Agent Core / browser / APIs
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

## Durable continuity substrate

Canonical persistent compute:

- smolmachine: `mach-187357670b1349d2a59ab423272af52e`
- workspace: `/workspace/continuity`
- continuity kernel: `/workspace/continuity/kernel`
- durable browser profile: `/workspace/browser/profile`

Continuity rules:

- append-only raw events and provenance are authoritative;
- derived state may be regenerated;
- failed attempts remain evidence;
- cleanup classifies and consolidates; it does not silently rewrite history;
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
| `browser-worker-v2` | historical browser-worker experiment | sleeping |
| `browser-worker-bYcU` | historical experiment | sleeping |
| `browser-worker` | historical experiment | failed |
| `browser-core` | historical experiment | failed |

The separate Railway project `agent-v1-lab` is currently empty and historical.

Do not give new work to the historical services unless deliberately reviving one for a specific reason. They are retained as provenance until an explicit destructive-cleanup decision is made.

### Live Agent Core

Current live implementation:

- Railway service: `browser-worker-wNUX`
- runtime: `continuity-agent-core`
- current deployed release: **v0.15.2**
- deployment source is pinned to a specific Git commit
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

There is intentionally **no arbitrary remote-shell action** in the motor protocol.

The one-time installer bootstrap was disabled after successful installation. The permanent token remains only in managed runtime secret storage and the machine's owner-only secrets directory.

### Remaining ingress gap

The remaining missing link is the direct **AgentMail → Agent Core** webhook registration.

Agent Core already exposes a signed `message.received` ingress. Mail with an exact subject of:

```text
SELF-ROOT COMMAND: <allowlisted-action>
```

can be translated into a bounded motor command, and the sender policy currently trusts only `oldcraft541@agentmail.to`.

Once the AgentMail provider webhook is registered to that ingress, the full path becomes:

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

Do **not** create a second agent or a broad account-wide machine-exec credential to solve this.

## Autonomous work control plane (v0.17.0)

The repository now implements the restart-safe control plane around the existing provider adapters:

- atomic snapshots plus an append-only event journal under `AGENT_STATE_DIR`;
- idempotent work leases, checkpoints, and validated lifecycle transitions;
- payment-proof requirements before any work item can become `PAID`;
- bounded retries, expired-lease recovery, stuck-work detection, and a four-attempt ceiling;
- persistent provider outcome statistics used by the scheduler;
- compact pending reports for results, blockers, and decisions;
- idempotent AgentMail webhook discovery/provisioning using the actual inbox ID;
- a bounded, coalesced state mirror on the existing persistent smolmachine;
- restart tests covering the full qualified → leased → working → submitted → accepted → paid lifecycle.

`AGENT_STATE_DIR` holds the runtime's fast local snapshot and journal. The bounded motor mirrors the canonical work snapshot to the existing persistent smolmachine, so the current Railway service does not require a new paid volume. If a persistent volume is attached later, the recommended value is:

```text
AGENT_STATE_DIR=/data/agent-core
```

Worker-facing authenticated endpoints:

- `POST /v1/work/lease`
- `POST /v1/work/checkpoints`
- `POST /v1/work/transitions`
- `GET /v1/reports`
- `POST /v1/reports/ack`

The runtime still refuses autonomous spending and arbitrary remote shell access. General coding or research jobs require a compatible episodic reasoning worker to consume leases; Agent Core coordinates and remembers the work but does not pretend its deterministic scheduler can author arbitrary deliverables itself.

## Recovery sequence for a new worker

A new model/runtime should:

1. verify control/access to `oldcraft541@agentmail.to`;
2. read **SELF-ROOT v1 — canonical homunculus map**;
3. inspect AgentMail provider relationships and credential labels;
4. recover `/workspace/continuity/kernel` from `mach-187357670b1349d2a59ab423272af52e`;
5. preserve append-only historical events and provenance;
6. read this branch for implementation state;
7. confirm `browser-worker-wNUX` is still the live Railway service before changing infrastructure;
8. recover secrets only from managed stores/credential records;
9. resume open commitments and paid work.

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
