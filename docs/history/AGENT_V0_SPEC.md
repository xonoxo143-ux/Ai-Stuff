# Agent v0 — Implementation Specification

**Status:** architecture freeze for first faithful runtime  
**Project:** Local Modular Chatbot / AI Workbench  
**Research basis:** architecture notebook through v1.9  
**Purpose:** bridge the research program into a runnable agent without silently replacing the architecture with a conventional chatbot plus orchestration.

---

## 0. Why this file exists

The project has enough research history that implementation can now become a source of regression.

The purpose of Agent v0 is therefore **not** to maximize intelligence immediately.

The purpose is:

> **Instantiate the smallest faithful runtime form of the v1.9 architecture, make every important causal event observable, and create the substrate on which later learned capabilities, interaction motifs, memory, and developmental learning can be tested on real hardware.**

Structural fidelity comes before impressive behavior.

A weak but faithful Agent v0 is progress.

A strong conversational model hidden behind decorative modules is not.

---

# 1. Project anchor

The deployment target remains:

> **Build a high-quality local conversational agent, no larger than 32 GB as a finished runnable system, that can store broad capability while spending only the computation useful for the current moment.**

Compressed:

> **Store broadly. Activate narrowly.**

Optimization target:

> **Maximize useful conversational intelligence per unit of real runtime cost.**

Real runtime cost includes:

- wall-clock latency
- CPU work
- RAM footprint
- memory bandwidth
- cache behavior
- storage I/O
- routing and dispatch overhead
- communication overhead
- energy when measurable
- repeated computation
- quality lost by taking a cheaper route

Mathematical sparsity is not enough. The implementation must be efficient on real hardware.

---

# 2. Primary falsifiable hypothesis

Agent v0 must preserve the project's main architectural bet:

> **A sufficiently large fraction of useful cognition admits reusable, economically meaningful computational structure — sometimes as bounded capabilities, sometimes as reproducible interaction motifs.**

If useful cognition cannot be decomposed this way without destroying necessary context or creating excessive coordination cost, the architecture may collapse toward a dense monolithic system.

Agent v0 must make that failure measurable rather than hiding it.

---

# 3. What Agent v0 is

Agent v0 is a **persistent computational ecology** containing two first-class reusable object types.

## 3.1 Capability

A bounded callable computation:

```text
inputs / state
    ↓
private computation
    ↓
outputs / state change
```

A capability may be implemented by:

- deterministic code
- an algorithm
- a tool wrapper
- a learned neural model
- a dynamical model
- an exact composite
- a distilled composite
- another future substrate

The rest of the runtime must not need to know which implementation class produced the result.

## 3.2 Interaction motif

A reusable contextual relation or coalition:

```text
under context F:

A ↔ B
 \ /
  C
```

A motif represents useful computation that belongs partly to the **organization of multiple capabilities**, not necessarily to any single node.

Motifs may encode:

- ordering constraints
- recurrent loops
- pair/triple coalitions
- temporary routing relations
- bounded shared-state interactions
- context-specific coordination patterns

## 3.3 Runtime organization

The current strongest runtime form is:

```text
persistent capabilities
        +
reusable causal motifs
        +
context-generated temporary organization
        +
recurrent state update
```

The graph is not the ontology. It is a representation of typed relations such as:

- composition
- causal influence
- data dependency
- semantic compatibility
- control dependency
- provenance
- temporal ordering

The runtime must permit these relation types to remain distinct.

---

# 4. Hard invariants for v0

The following are architectural invariants. Implementation convenience must not violate them.

## 4.1 Universal public contract

All capabilities interact with the runtime through one substrate-neutral contract.

The scheduler must not contain special logic for "LLM capability", "tool capability", "learned capability", or "composite capability" beyond implementation adapters.

## 4.2 Private cognition, bounded public communication

A capability may maintain arbitrary private state.

Other components may access only its declared public contract and emitted packets.

Bounded communication is required.

**Discrete symbols are not required.** Earlier experiments did not establish hard discreteness as superior to narrow continuous communication.

## 4.3 Small active state is not long-term memory

Keep these categories separate:

```text
ACTIVE STATE
what matters now

EPISODIC EXPERIENCE
what happened

SEMANTIC / WORLD STATE
what the agent currently treats as true, probable, or unresolved

CAPABILITY LIBRARY
what the agent knows how to do
```

The active context is a projection of what matters now, not the authoritative memory store.

## 4.4 No hidden homunculus

The scheduler/controller may perform mechanical coordination:

- maintaining budgets
- ordering runnable work
- moving packets
- enforcing limits
- tracking unresolved dependencies
- collecting metrics
- resolving declared priorities

It must not quietly become the component that understands every domain, solves every problem, translates every representation, and decides every semantic question.

If the controller needs domain intelligence, that intelligence must be represented as a capability.

## 4.5 Provenance from the first executable build

Every meaningful capability execution, motif activation, packet, state mutation, and final action must be traceable.

Developmental learning depends on these traces.

Do not retrofit provenance later.

## 4.6 Promotion is reversible

Library growth is not permanent accumulation.

The architecture must support:

```text
create
update
merge
split
compress
replace
retire
forget
```

A promoted object must remain versioned and removable.

## 4.7 Total-system utility beats local elegance

A capability or motif may be:

- correct
- reusable
- compressive

and still make the complete system worse through search, recognition, routing, storage, communication, or I/O overhead.

Nothing is retained merely because it is locally useful.

## 4.8 Hardware economics are part of the architecture

Real device behavior decides whether sparse activation is worthwhile.

The runtime must expose enough metrics to determine whether routing and memory movement erase theoretical savings.

---

# 5. Explicitly deferred decisions

Agent v0 must **not** silently settle these questions:

- transformer required vs forbidden
- token-based cognition required vs forbidden
- natural language required internally vs forbidden internally
- central routing required vs forbidden
- fully distributed recruitment required vs forbidden
- modules must be neural vs symbolic
- one shared representation is required
- discrete internal symbols are superior
- all learning must be end-to-end differentiable
- modules must be predefined
- modules must emerge from scratch
- one neural substrate should serve all capabilities

These remain experimental variables.

Agent v0 should provide interfaces that let later experiments change them.

---

# 6. Software boundary

The existing **AI Workbench remains the laboratory**.

It is not the cognitive core.

Add a new durable runtime layer:

```text
AI WORKBENCH
experiment definitions
controls
visualization
benchmarking
result export
        │
        ▼
AGENT KERNEL
capability registry
motif registry
active state
scheduler/recruitment
bounded message transport
memory interfaces
provenance
metrics
        │
        ▼
CAPABILITY EXECUTORS
native code
learned runtimes
tools
composites
future substrates
```

## 6.1 Recommended implementation placement

For v0:

- **Kotlin** owns the Agent Kernel orchestration/state lifecycle inside the stable Android shell.
- **C/C++** remains available for performance-sensitive capability executors and existing native inference.
- **HTML/JS Workbench** configures experiments and displays/exports results.
- Agent/ecology definitions are declarative workspace data where possible.

This keeps the cognitive runtime outside the WebView while preserving the existing "stable APK kernel + mutable workspace" design.

The kernel should be generic enough that ordinary ecology changes do not require an APK rebuild.

---

# 7. Core runtime data model

## 7.1 AgentState

Conceptually:

```text
AgentState
├── episode_id
├── step
├── active_state
├── unresolved_dependencies
├── active_capabilities
├── active_motifs
├── pending_packets
├── runtime_budget
├── current_action_candidates
└── provenance_root
```

This corresponds to the dynamic view:

```text
C_t = (G_t, X_t, Θ_t, B)
```

where:

- `G_t` = current typed capability/motif ecology
- `X_t` = active and latent state
- `Θ_t` = current transition/recruitment/modulation policy
- `B` = chosen system boundary

The implementation does not need to use these exact mathematical symbols.

It must preserve the distinction.

## 7.2 CapabilityContract

Required conceptual fields:

```text
CapabilityContract
├── id
├── contract_version
├── origin
├── applicability / initiation interface
├── accepted input types
├── public output types
├── declared state reads
├── possible state writes / side effects
├── termination semantics
├── estimated cost distribution
├── reliability / uncertainty
├── provenance / dependencies
├── implementation reference
└── revalidation status
```

Possible origins:

```text
EXPLICIT
LEARNED
COMPOSITE
```

The runtime must permit implementation replacement behind a stable contract **only inside a validated applicability region**.

## 7.3 InteractionMotifContract

Required conceptual fields:

```text
InteractionMotifContract
├── id
├── contract_version
├── participant roles / capability constraints
├── context guard
├── ordering / recurrence constraints
├── packet/state bindings
├── applicability region
├── expected cost
├── reliability
├── provenance
└── revalidation status
```

A motif is not simply a saved list of capability IDs.

It represents a reusable causal organization that may bind different compatible capabilities to roles.

## 7.4 PublicPacket

Transport should be mechanically structured while semantic content remains learnable/replaceable.

Conceptual envelope:

```text
PublicPacket
├── packet_id
├── source
├── destination / channel
├── public_type
├── bounded payload
├── optional numeric values
├── optional object/state references
├── confidence / uncertainty if supplied
├── lifetime / TTL
└── provenance_parent
```

Important:

- payload budgets are configured per experiment
- sender identity/provenance should not be confused with semantic identity
- the runtime must record packet size and communication cost
- payload representation may later be discrete, continuous, symbolic, hybrid, or learned

Do not encode a large human ontology into the packet envelope.

---

# 8. Active state and workspace

Agent v0 should expose a **small bounded coordination surface**, not a giant globally shared hidden state.

The active surface may hold:

- current external task/input references
- currently relevant entities/objects
- unresolved dependency IDs
- current goals / action requirements
- public packets
- active capability/motif IDs
- compact uncertainty / conflict signals
- runtime budget state

Private specialist state stays private.

The active state should be bounded by experiment configuration and measured.

If coherent behavior requires the active workspace to grow toward the size/complexity of a monolithic model, record that as architectural evidence.

---

# 9. Recruitment and scheduling

Agent v0 needs a concrete scheduler without pretending the routing problem is solved.

## 9.1 Activation proposal interface

A capability or motif may cheaply emit:

```text
ActivationProposal
├── target id
├── applicability score / confidence
├── estimated runtime cost
├── required dependencies
├── expected outputs / resolved dependencies
└── optional priority
```

The proposal mechanism must be much cheaper than executing the candidate.

## 9.2 Scheduler responsibilities

The scheduler may:

1. gather currently available proposals
2. reject proposals whose declared dependencies are unsatisfied
3. respect hard budgets and resource locks
4. prefer cheap/high-confidence direct routes when unambiguous
5. escalate when multiple proposals conflict or unresolved dependencies remain
6. execute selected work
7. ingest emitted packets/state changes
8. repeat until action conditions or budget termination

The scheduler does **not** need to know what "math", "social reasoning", "coding", etc. mean.

## 9.3 Initial v0 policy

Use a deliberately simple, replaceable policy:

```text
obvious single candidate
→ direct activation

multiple plausible candidates / conflict
→ budgeted priority arbitration

missing dependency
→ request candidates that claim they can resolve it

no useful proposal or budget exhausted
→ terminate / surface unresolved state
```

Do not implement a global compute auction as the universal control law in v0.

Compute-auction behavior remains an experiment that can later implement the arbitration policy.

## 9.4 Impasse

Impasse is not equivalent to simple disagreement.

An impasse may be signaled by combinations of:

- unresolved required dependency
- current route failure
- verifier rejection
- persistent prediction error
- action instability
- repeated state with little progress
- no sufficiently applicable candidate
- resource conflict

The exact detector remains experimental.

---

# 10. Execution semantics

Runtime cycle:

```text
external input / event
        ↓
update bounded active state
        ↓
generate cheap activation proposals
        ↓
select runnable capability / motif
        ↓
execute private computation
        ↓
emit bounded public outputs
        ↓
update state + dependencies + provenance
        ↓
new proposals / recurrence
        ↓
action-ready?
   /           \
 yes           no
  │             │
act        continue if budget allows
```

An operation may change not only state but the effective future organization.

Therefore execution order is first-class.

The runtime must preserve and trace order-sensitive compositions.

---

# 11. Memory architecture

Use separate interfaces even if v0 implementations are initially simple.

## 11.1 ActiveStateStore

Fast, bounded, episode-local or short-lived state.

## 11.2 EpisodicStore

Appendable experience/provenance records.

Initial Android implementation may use SQLite plus blob/file storage for large payloads.

## 11.3 SemanticStore

Persistent propositions, relations, uncertainty, or world-state records.

Agent v0 may keep this minimal, but it must not be conflated with episodes.

## 11.4 CapabilityStore

Versioned capability contracts, implementation refs, reliability/cost statistics, applicability metadata.

## 11.5 MotifStore

Versioned interaction motifs and their statistics.

## 11.6 ProvenanceStore

Dependency and causal-history traces needed for:

- debugging
- candidate discovery
- causal slicing
- revalidation
- training
- architecture inspection

The initial physical representation may share SQLite tables/files.

The **logical distinction must remain explicit**.

---

# 12. Provenance and trace schema

Each executed step should record at least:

```text
TraceEvent
├── episode_id
├── event_id
├── parent event ids
├── timestamp
├── event type
├── capability/motif id + version if applicable
├── proposal score
├── predicted cost
├── actual wall time
├── CPU time when measurable
├── memory delta when measurable
├── bytes / payload units communicated
├── state refs read
├── state refs written
├── input refs
├── output refs
├── success / failure / cancellation
└── implementation-specific metrics
```

For learned model executors, implementation-specific metrics may include:

- prompt/input units
- reused/cache units
- evaluated units
- TTFT
- decode/generation rate
- model-load time
- cache residency

Trace format must allow failures as well as successes.

Failures are developmental information.

---

# 13. Developmental learning split

Agent v0 should support learning architecturally without requiring the slow learner to execute on the phone initially.

## 13.1 Fast runtime loop

During ordinary use:

```text
select
→ execute
→ observe
→ update cheap reliability / relevance / cost statistics
```

Fast updates must remain inexpensive.

## 13.2 Slow developmental loop

Initially allowed to run off-device:

```text
experience + provenance
        ↓
causal/dependency slicing
        ↓
cheap structural screening
        ↓
candidate capability/motif proposals
        ↓
counterfactual / interventional validation
        ↓
JOINT probation
        ↓
retain smallest useful ecology
        ↓
optional compilation/distillation
        ↓
versioned ecology update
```

Principle:

> **Use expensive learning to teach cheap thinking.**

The slow learner may use information unavailable to the deployed runtime:

- extra candidate activations
- full internal traces
- ablations
- replay
- centralized critics
- alternate routes
- sampled coalition tests
- expensive teachers/verifiers

Runtime does not need to reproduce this process on every turn.

---

# 14. Candidate discovery

Do not globally enumerate coalitions.

Use the previously established funnel.

## 14.1 Ordinary experience channel

```text
dependency/provenance traces
→ causal slice
→ recurrence/compression mining
→ boundary/dominance pruning
→ small shortlist
→ expensive validation
```

## 14.2 Exceptional episode channel

Rare structures may be valuable despite low frequency.

```text
unusually expensive / important success or failure
→ extract causal slice
→ provisional candidate
→ future evidence / validation
```

Frequency alone is not a promotion criterion.

Compression alone is not a promotion criterion.

---

# 15. Promotion and joint probation

## 15.1 Validity

A candidate boundary is legitimate only when it can be replaced by a public black box within its stated applicability region without hidden external dependencies.

## 15.2 Utility

A candidate survives only if it improves total expected system objective after accounting for:

- task quality / loss
- compute
- communication
- latency
- storage
- recognition
- routing
- search
- reliability failures
- information loss
- memory movement

## 15.3 Staged lifecycle

```text
candidate
→ exact/provisional macro or motif
→ probation
→ validated reusable object
→ optional compilation/distillation
→ continued maintenance
```

## 15.4 Joint probation

Do not assume candidate utility is additive.

A provisional ecology may contain candidates that:

- only help together
- become redundant together
- interfere
- create excessive branching
- change routing cost

Therefore probation must be able to evaluate candidate sets and prune dispensable structure jointly.

This is a hard v1.9 requirement.

---

# 16. Capability replacement and versioning

Every capability and motif has a contract version.

If implementation semantics change:

```text
retest dependents
fork a new version
retain compatibility adapter
or retire incompatible descendants
```

Dependent composites and motifs must retain provenance to the versions they were validated against.

Silent semantic drift is not allowed.

---

# 17. Resource budget and forgetting

The finished system has a finite deployment budget.

Agent v0 should therefore track, even before the 32 GB limit becomes binding:

- implementation bytes
- metadata bytes
- memory residency
- invocation frequency
- routing cost
- observed utility
- last validation
- last use
- dependency count

Nothing receives permanent protection merely because it was once useful.

Library health is part of learning.

---

# 18. Real-device instrumentation

Every benchmark should distinguish:

## Engineering outcomes

- task score / objective checks
- total latency
- per-capability latency
- CPU work where measurable
- peak / resident memory
- storage I/O
- load/prefetch time
- cache hits/reuse
- active capability count
- active motif count
- packet count
- bytes/payload units communicated
- scheduler overhead
- escalation count
- failed activations
- runtime energy if later measurable

## Organizational outcomes

- active topology
- new/reused capabilities
- new/reused motifs
- recurrence depth
- feedback-loop depth
- abstraction depth
- dependency depth
- cross-module integration
- state persistence
- rerouting after lesions/failures

Performance tells whether it works.

Organizational metrics tell **what architecture produced the result**.

---

# 19. Lesion and counterfactual testing

The Agent Kernel should make these experiments possible:

```text
disable capability
disable motif
remove packet
corrupt packet
reduce communication budget
freeze persistent memory
freeze plasticity / fast updates
force alternate route
disable fast path
disable escalation
```

Then measure:

- behavior lost
- behavior preserved
- rerouting
- latency/compute changes
- dependency changes
- whether claimed communication was actually causal

This prevents decorative components from being mistaken for functional ones.

---

# 20. Agent package / workspace contract

Add a declarative agent area to the mutable workspace.

Recommended layout:

```text
workspace/
  agents/
    agent-v0/
      agent.json
      capabilities/
      motifs/
      policies/
      experiments/
```

`agent.json` should identify:

- schema version
- agent id
- required kernel version
- active-state budget
- communication budget
- runtime policy
- enabled capability contracts
- enabled motif contracts
- memory providers
- trace settings
- experiment overrides

The workspace may update contracts/configuration for implementations already supported by the kernel.

New native executor types still require a kernel update.

---

# 21. Kernel API additions

The existing Workbench bridge should gain a narrow Agent API.

Conceptual requests:

```text
agent.load
agent.unload
agent.status

agent.episode.start
agent.episode.input
agent.episode.stop

agent.trace.get
agent.trace.export

agent.ecology.get
agent.state.get

agent.experiment.run
```

Do not expose arbitrary native execution to the web layer.

The Workbench remains an experiment/control surface.

---

# 22. First implementation capabilities

The first ecology should be intentionally simple and heterogeneous.

Do **not** attempt to fake modular intelligence by prompting one language model as several "agents."

Use capabilities that exercise the runtime contract itself.

Recommended initial set:

```text
1. deterministic transform capability
2. state read/write capability
3. memory lookup/write capability
4. simple verifier capability
5. one order-sensitive composite capability
6. one optional learned executor adapter
```

The optional learned adapter exists only to prove that a learned substrate can inhabit the same contract.

Its specific model family is not architecturally privileged.

---

# 23. First interaction motifs

Agent v0 should include at least three controlled motifs:

## Motif A — sequential order-sensitive

```text
A → B
```

and

```text
B → A
```

must be distinguishable when operations do not commute.

## Motif B — recurrent correction

```text
predict
→ act/evaluate
→ error
→ revise
↺
```

## Motif C — coalition

A+B together produce value not available from either alone.

These motifs validate the runtime's ability to represent the strongest v1.9 findings before natural-language complexity is added.

---

# 24. Agent v0 milestone sequence

## M0 — contracts + deterministic test runtime

Implement:

- CapabilityContract
- InteractionMotifContract
- PublicPacket
- AgentState
- scheduler
- provenance trace
- deterministic unit tests

Pass when:

- capabilities are substrate-neutral
- execution order is recorded
- motifs can alter effective composition
- controller contains no domain logic

## M1 — deterministic ecology on Android

Run the controlled capability/motif ecology on the physical phone.

Measure:

- scheduler overhead
- message overhead
- state overhead
- trace overhead
- real latency
- memory behavior

This establishes the cost of the architecture itself.

## M2 — persistence and restart

Add logical memory stores.

Pass when:

- agent can stop/restart
- durable stores survive
- active state is reconstructed intentionally rather than confused with history
- versioned capability/motif library persists

## M3 — learned capability adapter

Plug one learned executor into the universal capability interface.

Pass when:

- scheduler/runtime code does not change based on substrate
- implementation can be swapped behind the same contract
- learned executor metrics appear in the same trace

## M4 — controlled recruitment experiment

Compare:

- always-on
- fixed routing
- cheap proposal routing
- escalation policy

Measure total real cost.

Do not promote a routing method based only on activation count.

## M5 — slow learner replay

Export traces to the developmental learner.

Implement:

- candidate discovery
- validation
- provisional capabilities/motifs
- joint probation
- ecology update

## M6 — recursive promotion

Critical test:

> Can a promoted object become part of a later candidate while the whole ecology remains net-positive?

This is the first direct test of self-grown hierarchy in the real Agent Kernel.

## M7 — language / conversation integration

Only after M0–M6 are structurally sound should language-facing capability arrangements become the primary benchmark.

Natural language may enter earlier as an interface test, but it must not determine the architecture.

---

# 25. Initial pass/fail gates

Agent v0 is successful only if the runtime makes the research claims testable.

Required:

- [ ] universal capability interface
- [ ] capabilities with at least two implementation origins
- [ ] first-class interaction motifs
- [ ] bounded public communication
- [ ] separate active/episodic/semantic/capability memory interfaces
- [ ] no domain-smart central scheduler
- [ ] complete provenance
- [ ] order-sensitive execution
- [ ] coalition representation
- [ ] configurable recruitment policy
- [ ] real runtime-cost instrumentation
- [ ] reversible/versioned ecology objects
- [ ] support for joint probation artifacts
- [ ] workspace-driven experiment configuration
- [ ] physical-phone benchmark path
- [ ] GitHub result export

Failure / redesign signals:

- scheduler becomes the real intelligence
- most work requires globally shared state
- most capabilities activate on most episodes
- message/routing overhead dominates useful computation
- trace collection is too expensive to leave enabled
- capability boundaries repeatedly require hidden dependencies
- motif representation degenerates into arbitrary whole-system snapshots
- kernel must know implementation-specific semantics
- real hardware locality erases sparsity gains
- conventional dense baselines consistently dominate quality/runtime

---

# 26. Anti-regression ledger

Do not reintroduce these rejected stronger claims:

- central routing is always wrong
- distributed self-routing is always right
- signatures solve higher-order interaction
- disagreement alone is an impasse
- compute auctions should run on every cognitive step
- hierarchy automatically creates abstraction
- discrete symbols automatically improve generalization
- message dropout is free robustness
- frequency identifies useful reusable structure
- compression proves abstraction
- individual causal credit captures all useful structure
- locally useful skills necessarily improve the system
- promotion should be greedy
- successful traces are the only useful traces
- sparse activation automatically means fast execution
- dynamic edge weights are required for contextual cognition
- a graph is the fundamental ontology
- one pretrained language model should define the agent substrate

---

# 27. Architectural decision summary

## Frozen for Agent v0

- persistent computational ecology
- capabilities + interaction motifs
- context-sensitive temporary organization
- recurrent state transitions
- substrate-neutral capability contracts
- bounded public communication
- small active state distinct from durable memory
- hybrid/replaceable recruitment
- mechanical, non-domain-smart scheduler
- provenance from first execution
- fast runtime updates + slow structural learning
- cheap proposal / expensive verification
- recurrent + exceptional candidate discovery channels
- staged reversible promotion
- marginal utility at whole-system level
- joint probation
- versioned contracts
- finite-budget library evolution
- real-hardware optimization/measurement
- Workbench as laboratory; Agent Kernel as cognitive runtime

## Explicitly not frozen

- transformer role
- token role
- internal natural language
- exact learned substrate
- exact routing algorithm
- exact impasse detector
- discrete vs continuous public payload
- exact shared-workspace representation
- on-device vs off-device slow learning
- final memory implementation
- final module granularity
- final specialization mechanism

---

# 28. First coding target

The first code change after this specification should be **M0 only**:

> Implement the Agent Kernel core types, deterministic scheduler, first-class motif execution, bounded packet transport, and provenance tracing with unit tests.

Do not add a language model dependency to M0.

Do not implement training in M0.

Do not optimize intelligence in M0.

The question M0 answers is:

> **Can the v1.9 architecture exist as an executable runtime without collapsing into a central monolithic controller?**

Only after that answer is concrete should the project advance to M1.

---

# 29. Guiding rule

When implementation pressure creates a tempting shortcut, ask:

> **Does this shortcut merely make coding easier, or does it preserve the architecture we actually researched?**

If the answer is unclear, prefer the smaller reversible implementation and record the uncertainty.

Agent v0 is an experiment, but it must be an experiment on **our architecture**.
