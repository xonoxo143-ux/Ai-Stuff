# Agent Memory Map

**Version:** 2.1  
**Date:** 2026-09-28  
**Status:** READ THIS FIRST  
**Purpose:** route a cold reader/model to the smallest authoritative source.

## Authority order

When two notes conflict, use this order:

1. `agent_current_frontier_v21.md` — what is happening now.
2. `agent_decision_ledger_v21.md` — what the architecture currently commits to.
3. `agent_evidence_ledger_v21.md` — what experiments actually support/reject.
4. `agent_architecture_handbook_v20.md` — integrated current conceptual model.
5. exact GitHub experiment specs/results — provenance and detailed measurements.
6. `chatbot_architecture_notebook_v19.md` — historical archive.
7. `agent_historical_archive_index_v21.md` — exact line navigation into the archive.

A newer exact experiment result may supersede a summary; when that happens, update tiers 1–4 immediately.

---

## Topic router

| Question | Read first | Then |
|---|---|---|
| What are we building? | `agent_architecture_handbook_v20.md` | Decision Ledger |
| What are we doing right now? | `agent_current_frontier_v21.md` | latest GitHub result |
| What has actually been proven? | `agent_evidence_ledger_v21.md` | exact result docs |
| Why did we choose this architecture? | `agent_decision_ledger_v21.md` | archive/history |
| What failed? | Evidence Ledger | archive/result docs |
| What did Agent v0 establish? | Evidence Ledger `E-V0-*` | `AGENT_V0_CLOSEOUT.md` |
| What did v1 interference tests establish? | Evidence Ledger `E-V1-*` | `AGENT_V1_A1_*` results |
| What is the current chatbot architecture? | Handbook §§2–6, 11 | Decision Ledger |
| What is the memory model? | Handbook §5 | Decision Ledger D-004 |
| What is the build loop? | Frontier | Handbook §15 |
| Where did an old idea come from? | archive index | v19 archive |
| What is still open? | Decision Ledger | Frontier |

---

## Stable search tags

Use these exact strings when searching:

- `E-V0-` — Agent v0 evidence
- `E-V1-` — Agent v1 evidence
- `E-ARCH-` — architecture-level evidence/synthesis
- `D-` — current commitments
- `H-` — strong hypotheses
- `R-` — rejected/demoted claims
- `Track A` — developmental mechanism
- `Track B` — chatbot integration
- `Structural changes must pay rent`
- `Store broadly. Activate narrowly. Develop selectively.`

---

## Cold-start procedure

A future model or collaborator should:

1. read this file;
2. read Current Frontier;
3. read Decision Ledger;
4. read only the relevant Evidence Ledger entries;
5. read the Handbook section needed for architecture context;
6. open exact experiment docs only when numbers/provenance matter;
7. use the historical archive only when reconstructing why an idea changed.

This prevents the archive from silently overriding current state.

---

## Maintenance rule

Never let the project accumulate multiple unlabeled "current" sections.

Every meaningful cycle must produce one of:

- **no architectural change** — Frontier only;
- **new durable evidence** — Frontier + Evidence;
- **changed architectural decision** — Frontier + Evidence + Decision;
- **historical detail** — exact result/archive, not current files.

The top-level memory system should stay compact.