# Agent Core

Agent Core is the thin operational layer that gives the existing continuity lineage bounded external agency.

It is **not** a second identity system, a replacement continuity kernel, or a new canonical journal.

## Source of truth

Canonical continuity state and provenance remain outside this implementation:

- canonical persistent workspace: `/workspace/continuity`
- continuity kernel: `/workspace/continuity/kernel`
- canonical executive summary: `continuity_project.md`
- detailed economic handoff: `economic_agency_handoff_2026-09-28.md`

GitHub contains versioned implementation only. Never commit passwords, OTPs, API keys, private keys, seed phrases, wallet recovery material, signing secrets, or live financial credentials.

## Current architecture

```text
continuity lineage / policy / ledger
            |
            v
        Agent Core
       /    |     \
AgentMail  economy  work
 /AgentID   /   \   tools
          Circle Stripe
```

Current preferred roles:

- **AgentMail / AgentID** — persistent identity, communication, and account recovery.
- **Circle Agent Wallet** — preferred agent-native treasury candidate; authentication is not yet completed in a unified runtime.
- **Stripe** — human-facing payment adapter. Connected live-mode account exists; no payment writes were made during setup.
- **Floot** — disposable/bootstrap compute, not canonical identity or final runtime.
- **smolmachines** — persistent continuity/evidence compute; demoted from presumed permanent agent body.

## Immediate engineering target

Build the smallest runtime boundary that can hold:

1. AgentMail credentials;
2. wallet session/authentication;
3. secret storage below model context;
4. bounded execution;
5. an adapter that emits economic events into the existing continuity/ledger model.

Do not change the frozen continuity kernel merely to make Agent Core easier to implement.

## Financial baseline

Until an authorized policy revision:

- no borrowing, leverage, gambling, or speculative trading;
- no deceptive identity, fake transactions, self-purchases, or mass unsolicited spam;
- no unbounded spend;
- no expenditure before settled revenue unless separately authorized;
- provider-enforced limits preferred;
- the agent cannot raise its own limits;
- revenue, fees, refunds, reserves/protected funds, and operating capital are tracked separately.

## First economic proof

The first meaningful economic proof is:

```text
real external need
-> bounded useful deliverable
-> transparent agreement
-> authorized payment
-> delivery
-> settled external revenue
-> durable outcome/ledger record
```

A completed agent wallet is **not required for the first sale**. Stripe can serve the first human/card customer while unified wallet authentication is completed separately.

Do not count self-payments, subsidies, test transactions, or speculative gains as earned revenue.

## Live runtime status — 2026-09-28

Agent Core v0.2.0 is deployed on Railway and externally health-checked.

Implemented:
- persistent Railway runtime;
- authenticated event ingress using a Railway-held secret;
- $100 operating-float target;
- TaskBounty public funded-task feed sync every 60 seconds;
- optional HMAC-signed TaskBounty webhook endpoint;
- task normalization, economic/scope filtering, and candidate/manual-review/rejected classification;
- startup resync from the provider feed so an in-memory queue can recover currently open tasks after restart;
- synthetic task-path test passed, then self-test was disabled;
- an hourly ChatGPT condition-watch checks for viable paid tasks and stays silent when none exist.

Current provider state at final verification:
- TaskBounty feed reachable;
- zero open tasks returned;
- queue empty;
- webhook secret not yet registered with TaskBounty;
- TaskBounty solver API credential not yet installed;
- payout wallet not yet installed;
- financial actions remain disabled;
- outbound work remains disabled inside the runtime.

The runtime may discover and classify work automatically. Claiming, repo-access minting, submission, payout configuration, and money movement remain separate gated capabilities.

