# Agent Core continuity — v0.18 bounded work execution

Date: 2026-09-30 UTC

## Material outcome

Agent Core v0.18.0 server/control-plane release is deployed successfully to the production `browser-worker-wNUX` Railway service.

- Code-release SHA: `f025f18a3a83dc80c4577d645e7350ef1994dd3b`
- Railway deployment: `7679f6ef-0703-4d0c-b593-9a16e3ef7269`
- Runtime startup log confirms version `0.18.0`.
- `financialActionsEnabled=false`
- `outboundWorkEnabled=true`

## Added capability

A new typed `work.execute` motor action is implemented without adding arbitrary remote shell access.

Server/control-plane:
- `POST /v1/work/dispatch` validates a bounded plan.
- Existing work items are leased to `self-root-motor`, moved/checkpointed through the existing lifecycle, and enqueued through the durable motor.
- Motor acknowledgements reconcile artifacts, completion/failure, transitions, and work reports.
- AgentMail ingress can accept `SELF-ROOT COMMAND: work.execute` when the message body is a valid bounded JSON plan.
- Job payloads reject credential-like fields and known prohibited/risky scope.

Machine executor:
- repository file `agent-core/motor/self_root_motor.py` implements per-job workspaces and typed handlers for:
  - mkdir
  - write_text / read_text
  - public HTTPS fetch with private-address rejection
  - public GitHub clone
  - git patch application
  - git status/diff/head inspection
  - JSON/Python/Node syntax checks
  - local no-hook git commit
- no push operation and no arbitrary command/shell step exists.

## Verification

- Node syntax check: passed.
- Python motor compilation: passed.
- Motor state/snapshot test: passed.
- Bounded `work.execute` executor test: passed.
- Path-traversal rejection test: passed.
- End-to-end runtime dispatch → lease → motor poll → acknowledgement → SUBMITTED lifecycle test: passed.
- Existing restart/payment-proof lifecycle test passed in isolation. A concurrent Android full-suite run showed one startup-timeout flake when two runtime integration tests ran together; no behavioral failure reproduced in isolation.

## Remaining rollout boundary

The persistent smolmachine `mach-187357670b1349d2a59ab423272af52e` is still running the pre-v0.18 motor daemon. The repository and Railway server are updated, but direct machine-control credentials for smolmachines are not available through the current connected tools or AgentMail records. No attempt was made to weaken the motor boundary or add arbitrary self-update shell access.

Next action:
1. recover/use the existing owner-controlled smolmachines console/API credential;
2. replace `/workspace/continuity/motor/self_root_motor.py` with the pinned v0.18 file;
3. restart the existing motor service;
4. dispatch a harmless `work.execute` smoke job and verify its acknowledgement;
5. then hand it the first real paid coding/research task.

No money was spent and no credentials were exposed.
