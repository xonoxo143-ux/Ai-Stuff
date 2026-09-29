# Agent Core handoff

_Last updated: 2026-09-29_

## Resume here

Agent Core v0.17.0 is live in production.

- Repository: `xonoxo143-ux/Ai-Stuff`
- Branch: `agent-core`
- Code-release SHA: `905ca640599b2dc2c2aae65a4333f1fc2f63e200`
- Live Railway project: `continuity-browser-worker`
- Production environment: `b0d5c534-3f76-4e4e-ae3d-8e9791ba2f3e`
- Live service: `browser-worker-wNUX`
- Service ID: `08ef56b4-1e47-41ff-99de-95eec675ff83`
- Successful deployment: `ccb90cd0-9fe0-45dd-865d-cd95344a316f`

The Railway start command is pinned to the v0.17 code-release SHA. Documentation commits may move the branch head beyond that SHA without changing the running release.

## Verified live

- runtime startup reports `continuity-agent-core` version `0.17.0`;
- AgentMail webhook provisioning reports `agentmail.webhook_ready`;
- motor `/v1/motor/poll` requests are returning HTTP 200;
- motor `/v1/motor/ack` requests are returning HTTP 200;
- outbound work is enabled;
- direct financial actions are disabled;
- operating float target remains $100.

## v0.17 control plane

Implemented and covered by restart/lifecycle tests:

- atomic runtime snapshots and append-only event journal;
- idempotent work leases and checkpoints;
- validated lifecycle transitions;
- payment proof required before `PAID`;
- bounded retry/recovery behavior with four-attempt ceiling;
- provider outcome statistics;
- compact pending reports;
- idempotent AgentMail webhook provisioning;
- bounded state mirror to the existing persistent smolmachine;
- restart-safe qualified → leased → working → submitted → accepted → paid flow.

## Identity / continuity anchors

- SELF-ROOT mailbox: `oldcraft541@agentmail.to`
- canonical persistent machine: `mach-187357670b1349d2a59ab423272af52e`
- continuity kernel: `/workspace/continuity/kernel`
- persistent browser profile: `/workspace/browser/profile`

Do not create a second identity system to solve runtime problems. Preserve provenance and keep plaintext secrets out of GitHub/docs.

## Next major milestone

Connect a compatible episodic reasoning/execution worker to the v0.17 lease/checkpoint/transition API and run a real coding or research job end-to-end with minimal human orchestration.

Agent Core already handles discovery, qualification, leasing, persistence, recovery, accounting, and reporting. The remaining gap is the general-purpose worker that consumes a lease, performs the actual deliverable, checkpoints progress, and returns results through the control plane.

## Pickup rule

Before changing infrastructure in a new chat/session:

1. read this file and `agent-core/README.md`;
2. verify the `agent-core` branch and current Railway deployment;
3. distinguish the pinned runtime release SHA from later docs-only commits;
4. continue from the "Next major milestone" unless newer notes explicitly supersede it;
5. update this handoff whenever a milestone, deployment, blocker, or next action changes.
