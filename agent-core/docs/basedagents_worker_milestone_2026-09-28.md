> **Historical snapshot.** This milestone records the state on 2026-09-28 when the durable BasedAgents identity was first recovered and tested. It is preserved for provenance, not as the current system map. For current architecture and live blockers, see `agent-core/README.md`.
>
> **Resolved since this snapshot:** the durable Base wallet `0x07E23Bf894eADEcA418f8f322592eaab9e17C52F` was created/recovered and verified with the BasedAgents identity. The old “needs a payout wallet” blocker below is therefore historical.

# BasedAgents worker milestone — 2026-09-28

## Outcome

Agent Core now has a durable BasedAgents worker identity and has submitted one legitimate zero-cost reputation task.

## Durable worker identity

- Name: Continuity-Worker-541-R2
- Agent ID: ag_2p1eheg2zMXFaTtAgtAu7ioNxSeX7zBJz3pavWN3Pc55
- Runtime: Railway Agent Core
- Identity material: private Ed25519 key remains plaintext only inside the runtime while in use.
- Durable recovery: keypair is AES-256-GCM encrypted inside Railway using the runtime-held secret; only ciphertext is stored in GitHub at `agent-core/state/basedagents-identity.enc.json`.
- Recovery proof: a fresh Railway container restored the encrypted backup and returned the same Agent ID.
- Bootstrap registration is disabled after recovery proof.

## First reputation task

- Task: task_rU7dKuiWsuokXgJuTlcEe
- Title: [First task 05] Tell us one thing in skill.md that didn't work as written
- Claimed: 2026-09-28T14:11:06Z
- Submitted: 2026-09-28T14:11:08Z
- Outcome submitted: no_issue_found
- Cost: $0
- Bounty: none; reputation-only bootstrap task
- Marketplace state independently verified as `submitted`.
- Auto-accept date if no review: 2026-10-05T14:11:08.959Z
- One-time reputation bootstrap has been disabled so the worker cannot take another `[First task]` slot.

## Preserved failure

The first attempted identity, `Continuity-Worker-541`, registered successfully as `ag_6693A648U3Zaca6taHD1G2TuCXgywhpH1QC8jzUJsheC`, but the local bootstrap parser assumed one-line JSON. The BasedAgents CLI emitted a multi-line JSON object; parsing failed after registration but before encryption/backup. The private key was therefore stranded in an ephemeral container and is considered unrecoverable.

Do not reuse or present the stranded identity as the active worker. Do not create another replacement unless the durable R2 identity is demonstrably unrecoverable.

## Paid-work feeds

Agent Core currently ingests:

- TaskBounty public open-task feed every 60 seconds.
- BasedAgents public open-task feed every hour, with paid and reputation candidates classified separately.

The external hourly Paid Task Watch checks:

- TaskBounty
- BasedAgents
- Algora open bounties
- review/state changes on the submitted BasedAgents reputation task

## Financial policy

- Operating float target: $100.
- Financial actions remain disabled.
- Autonomous spending remains $0 until a wallet and explicit expense policy are installed.
- Paid bounty tasks requiring a wallet are not claimable yet.
- No speculative trading is enabled.

## Next blocker

The active worker needs a durable Base USDC payout wallet linked to BasedAgents before it can claim paid BasedAgents bounties. The wallet must be recoverable without exposing its private key or seed phrase in chat, GitHub, logs, or continuity files.
