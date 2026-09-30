# Agent Core handoff

_Last updated: 2026-09-29_

## Project boundary — do not merge these

This handoff is for the **AgentMail / SELF-ROOT operational agent** only.

It is **not** the separate homegrown/custom-agent research project whose goal is to build an intelligent conversational agent from scratch without importing another LLM. That project has its own architecture, experiments, and continuation state.

For this project, references to a "reasoning worker", "episodic worker", or "replaceable model worker" mean an execution component used by SELF-ROOT to complete work. They do **not** mean that the homegrown-agent research project should be folded into Agent Core.

Keep the two projects separate unless the human explicitly decides to integrate them later.

## Resume here

Agent Core v0.18.0 control plane is live in production.

- Repository: `xonoxo143-ux/Ai-Stuff`
- Branch: `agent-core`
- Code-release SHA: `f025f18a3a83dc80c4577d645e7350ef1994dd3b`
- Live Railway project: `continuity-browser-worker`
- Production environment: `b0d5c534-3f76-4e4e-ae3d-8e9791ba2f3e`
- Live service: `browser-worker-wNUX`
- Service ID: `08ef56b4-1e47-41ff-99de-95eec675ff83`
- Successful deployment: `7679f6ef-0703-4d0c-b593-9a16e3ef7269`

The Railway start command is pinned to the v0.18 code-release SHA. Documentation commits may move the branch head beyond that SHA without changing the running release.

## Verified live

- runtime startup reports `continuity-agent-core` version `0.17.0`;
- AgentMail webhook provisioning reports `agentmail.webhook_ready`;
- motor `/v1/motor/poll` requests are returning HTTP 200;
- motor `/v1/motor/ack` requests are returning HTTP 200;
- outbound work is enabled;
- direct financial actions are disabled;
- operating float target remains $100.

## v0.18 control plane

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

## v0.18 bounded execution

The control plane now accepts a typed `work.execute` motor command and `POST /v1/work/dispatch`. A job may use only bounded operations: public GitHub clone, public HTTPS fetch, per-job file read/write, patch application, git inspection, syntax checks, and a local no-hook commit. It does not expose arbitrary shell execution, secrets in job payloads, financial actions, or credential-bearing clone URLs.

The server-side lifecycle is live and tested: dispatch leases the existing work item, checkpoints it, routes the typed payload through the motor queue, and reconciles the acknowledgement back into the same work ledger/reporting system.

**Machine rollout boundary:** the canonical smolmachine daemon has not yet been refreshed to the v0.18 motor file. The repository contains the new handler, but direct smolmachines machine control is currently unavailable because no usable smol cloud API key is present in the connected tools/AgentMail records. Do not claim end-to-end machine execution is live until that daemon is updated and a real `work.execute` command is acknowledged successfully.

## Next major milestone

Refresh `/workspace/continuity/motor/self_root_motor.py` on `mach-187357670b1349d2a59ab423272af52e` using the existing owner-controlled smolmachines session/API, restart the motor service, then run one real coding or research job end-to-end through `/v1/work/dispatch` without manual orchestration.

## Pickup rule

Before changing infrastructure in a new chat/session:

1. read this file and `agent-core/README.md`;
2. verify the `agent-core` branch and current Railway deployment;
3. distinguish the pinned runtime release SHA from later docs-only commits;
4. continue from the "Next major milestone" unless newer notes explicitly supersede it;
5. update this handoff whenever a milestone, deployment, blocker, or next action changes.
