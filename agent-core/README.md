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
- current deployed release: **v0.14.11**
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

## Main missing motor pathway

The highest-value architectural gap is not another account or another machine. It is the action channel from the homunculus to its persistent runtime:

```text
SELF-ROOT / AgentMail
      |
      v
authenticated bounded command/wake receiver
      |
      v
mach-187357670b1349d2a59ab423272af52e
      |
      +--> /workspace/continuity/kernel
      |
      +--> /workspace/browser/profile
      |
      v
browser / tools / external services
```

Do **not** create a second agent to solve this. Extend the existing SELF-ROOT system.

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
