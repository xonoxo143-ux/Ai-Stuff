# Agent — Current Architecture and Frontier

**Date:** 2026-09-29  
**Status:** authoritative current orientation  
**Branch:** \`experiment/agent-v1-developmental-ecology\`

> If another Agent document disagrees with this file about the current direction, treat that document as historical unless this file explicitly re-promotes it.

## 0. Documentation contract

This is the **only living project-state/build document**.

Research is deliberately separated into a paired module:

- `AGENT_RESEARCH_FINDINGS.md` — **what the external scientific literature currently supports**;
- `AGENT_RESEARCH_SYNTHESIS.md` — **what we infer may be possible when those findings are linked with our experiments**, including how that synthesis changes after tests.

The boundary is strict: external evidence belongs in FINDINGS; project inference belongs in SYNTHESIS; adopted build decisions belong here.

After a meaningful build cycle:

1. update `AGENT_CURRENT.md` with the new project truth, decision, and next gate;
2. create one experiment/result document only when durable technical detail is worth preserving;
3. update SYNTHESIS if the result changes the integrated hypothesis;
4. update FINDINGS only when the literature frontier itself changes.

Completed experiment/result documents are immutable evidence except for factual corrections.

Do **not** maintain a second build frontier, duplicate current-state summary, evidence ledger, or decision ledger in parallel.

`AGENT_DOCS_INDEX.md` is a stable module map, not a per-cycle status file.

Modular recovery:

```text
build chat      → AGENT_CURRENT.md
research chat   → AGENT_RESEARCH_FINDINGS.md + AGENT_RESEARCH_SYNTHESIS.md
experiment chat → AGENT_CURRENT.md + the relevant result file
full project    → all three living modules + result files only as needed
```

## 1. Task anchor

Build an intelligent local conversational agent from scratch, with a finished runnable system no larger than roughly 32 GB.

A pretrained LLM may be used only as a control/reference system. It must not silently supply the intelligence we are trying to build.

Short form:

\`\`\`text
STORE BROADLY
ACTIVATE NARROWLY
DEVELOP SELECTIVELY
\`\`\`

The first integrated embodiment is a chatbot.

## 1A. Whole-agent capability audit — 2026-09-29

The project objective is the **self-contained conversational agent**, not any individual synthetic cognition benchmark.

Audit against the original end test:

> Can the from-scratch system carry a genuinely generated, multi-turn conversation across very different topics without importing a pretrained LLM as its hidden intelligence?

### Blocking gap 1 — the self-contained conversational loop is not closed

The runtime infrastructure is real, but its current language composer uses an OpenAI-compatible backend intended for llama.cpp/other language servers.

The from-scratch language organs live separately in `agent_language`, and the factor cognitive core lives separately in `agent_cognition`.

So today we do **not** have:

```text
user bytes
→ homegrown perception
→ persistent internal state / memory
→ homegrown cognition
→ homegrown conditioned production
→ response bytes
```

running as one conversational system.

This is the largest project-level gap.

### Blocking gap 2 — the language/semantic interface is still toy-scale

Current perception success is on a controlled four-slot semantic task.

Current conditioned production can perfectly express held-out combinations of a bounded 16-dimensional state.

Current real-text GRU was trained from scratch on about 3.4 MB of TinyStories and produces recognizable but repetitive English.

These results prove useful mechanisms, but they do not yet provide open-domain dialogue understanding or response generation.

### Blocking gap 3 — broad knowledge is plumbing without a learned knowledge interface

The runtime already has:

- episodic turn storage;
- durable SQLite memory;
- semantic key/value memory;
- lexical/FTS retrieval;
- capability contribution contracts.

But semantic facts are currently inserted explicitly and retrieved lexically. There is no general from-scratch path that reads broad text, forms useful knowledge, and makes it available to the homegrown conversational system.

For philosophy, coding, literature, factual questions, and role-play flexibility, this is a larger capability gap than another few points on synthetic chain traversal.

### Major gap 4 — multi-turn thread/state control is infrastructure, not yet learned behavior

The runtime can preserve recent episodes and active state, but our homegrown perception/cognition/production stack has not yet demonstrated:

- abrupt topic switching;
- resuming an interrupted thread;
- maintaining a role/scene;
- using earlier analytic threads later;
- deciding when a referent is ambiguous;
- preserving user-specific facts over conversation.

The existing `chatbot-v0` benchmark already contains many of these tests and should return to the foreground.

### Secondary gap 5 — cognition/generalization

The factor core remains the strongest tested cognitive representation baseline.

Compositional OOD, transfer, depth generalization, and catastrophic forgetting remain important **diagnostics**.

They are no longer allowed to define the roadmap by themselves.

The failed transfer and oracle-operator gates are evidence about weaknesses of the cognition module, not evidence that the whole project should become a compositional-generalization project.

### Secondary gap 6 — developmental/continual machinery

Plasticity control, specialization, motifs, sparse execution, and continual learning remain relevant to the eventual lifelong agent.

They should be reintroduced when there is a self-contained conversational system whose capabilities can actually develop and be measured.

### Priority reset

```text
1. CLOSE THE HOMEGROWN CONVERSATIONAL LOOP
2. EXPAND LANGUAGE / SEMANTIC GENERALITY
3. GIVE IT BROAD RETRIEVABLE KNOWLEDGE
4. PASS REAL MULTI-TURN / TOPIC-SWITCH TESTS
5. USE COGNITIVE BENCHMARKS TO FIX FAILURES THAT MATTER THERE
6. ADD CONTINUAL DEVELOPMENT ONCE THERE IS SOMETHING WORTH DEVELOPING
```

### Next integrated milestone

Build **Whole-Agent Closure Gate v0**.

Requirements:

- no pretrained/external LLM in the inference path;
- byte input and byte output;
- use the existing runtime/memory contracts rather than replacing them;
- connect a homegrown perception path to bounded non-language state;
- condition a homegrown producer on that state plus retrieved/recent context;
- include at least several distinct conversational behaviors in one multi-turn run;
- trace each failure to perception, state/memory, cognition, retrieval, or production.

The first pass does not need to solve open-domain conversation.

It needs to create the qualitatively missing capability:

> **one genuinely conversational turn loop produced entirely by our own learned stack, with memory across turns.**

Once that exists, the whole-agent benchmark—not whichever isolated subsystem is currently fashionable—decides where the next large gain is.

## 2. Current architecture

The strongest current path is no longer "pick one monolithic language model."

\`\`\`text
English / bytes
      ↓
language perception
(current baseline: BiGRU)
      ↓
bounded non-language state
      ↓
general cognitive core
(current baseline: factor-graph processor)
      ↓
bounded non-language state
      ↓
language production
(current baseline: GRU)
      ↓
English / bytes
\`\`\`

Memory, tools, retrieval, persistent state, development and specialist capabilities are attached around this core as they earn a measurable role.

The language organs and cognitive core do not have to share one architecture.

## 3. Language evidence

### Production

Random-init raw-byte real-text replication on the same bounded TinyStories curriculum, 800 updates, three seeds:

\`\`\`text
GRU          800,640 params   mean 1.640 bits/byte
Transformer  927,872 params   mean 2.567 bits/byte
\`\`\`

All three GRU runs produced recognizable but repetitive English. The Transformer trained faster but remained substantially worse at the same update budget.

Current production baseline: **GRU**.

### Perception

Controlled English-bytes → structured-state task, three seeds:

\`\`\`text
BiGRU          72.0% exact state   91.6% slot accuracy
Transformer    36.5% exact state   77.9% slot accuracy
GRU            36.3% exact state   75.9% slot accuracy
\`\`\`

A slot-query attentive BiGRU refinement fell to 64.6% exact and was rejected.

Current perception baseline: **plain BiGRU**.

### Closed language loop

Controlled held-out paraphrases:

\`\`\`text
English
→ BiGRU perception
→ 16-d semantic state
→ GRU production
→ canonical English
\`\`\`

Three-seed result:

\`\`\`text
perception exact state      70.3%
oracle state → sentence    100.0%
hard predicted state        70.3% exact sentence
soft predicted state        67.5% exact sentence
hard byte accuracy          98.65%
soft byte accuracy          98.70%
\`\`\`

When perception is correct, the controlled state bridge and producer add essentially no extra exact-sequence loss. The bottleneck in this probe is perception.

## 4. Cognitive Core v0 — replicated result

The first useful non-language core uses a common factor-graph representation:

\`\`\`text
fact / event / query slots
        ↕ role-typed messages
persistent shared symbol/entity nodes
\`\`\`

The same processor and answer vocabulary are used across:

- transitive relations;
- ordered mutable state;
- graph reachability;
- rule induction;
- associative memory.

Rigorous three-seed CI, 400 mixed updates:

\`\`\`text
model                         mean OOD   mean IID   train time
flat MLP                        23.9%      40.5%       3.7 s
factor one-pass                 59.8%      77.3%       7.6 s
factor recurrent                64.6%      80.6%      26.0 s
factor recurrent, no reinject   65.8%      81.6%      25.6 s
\`\`\`

The **large result** is the representation/organization change:

> flat 23.9% OOD → factor one-pass 59.8% OOD, with far fewer parameters.

That is high-leverage enough to guide architecture.

The average recurrence gain is much smaller:

> 59.8% → 64.6% OOD for roughly 3.4× training time.

Do not spend a long research cycle polishing that aggregate gain.

Input reinjection did not pay rent and is currently demoted.

## 5. Thought depth

The same trained recurrent core evaluated at different recurrent depths:

\`\`\`text
1 step   38.1% OOD mean
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
\`\`\`

Memory is the clearest capability unlock:

\`\`\`text
1 step   10.2%
2 steps  52.0%
4 steps  99.6%
6 steps 100.0%
\`\`\`

Interpretation:

- repeated computation can unlock capabilities;
- most value in this benchmark is obtained by about four steps;
- extra depth after saturation should not be paid for automatically.

This connects directly to the literature on **recurrent depth / looped networks / adaptive computation**, so future work should use that literature rather than rediscover the basic phenomenon.

## 6. Specialist ceilings

The same recurrent processor trained separately by task family:

\`\`\`text
family      specialist OOD
relation        98.5%
rule            97.3%
memory         100.0%
graph           45.5%
state           20.5%
\`\`\`

The shared recurrent core is approximately:

\`\`\`text
relation        88.7%
rule            65.8%
memory          99.7%
graph           46.2%
state           22.8%
\`\`\`

Implications:

- memory is effectively solved in this controlled benchmark;
- graph/state are limited even for specialists, so they are poor places for shared-core tuning until the task/representation is reconsidered;
- relation is reasonably close to specialist performance;
- rule induction has the largest meaningful shared-vs-specialist gap.

## 7. High-leverage experimental rule

The project now optimizes **progress per unit effort**, not the number of positive experiments.

A new branch should normally earn continued work by plausibly producing at least one of:

- roughly **20+ percentage points** of capability improvement on a meaningful metric;
- roughly **2× or greater** real efficiency improvement;
- a previously absent capability;
- strong OOD/transfer/generalization that changes what the system can do;
- a large reduction in examples or updates needed to acquire a new capability.

Smaller gains may be recorded as evidence, but normally do not earn another optimization cycle.

The thresholds are triage heuristics, not laws. The standard is: **does this materially move us toward the intelligent conversational agent?**

## 8. Literature-before-build rule

Before an expensive experimental branch:

```text
state the question
→ search our wording
→ search neighboring terminology
→ search mechanism names
→ search recent work + canonical precedents
→ search known failure modes / ablations
→ identify the strongest relevant baseline
→ build only the unresolved discriminating test
```

Use the paired living research module:

- `AGENT_RESEARCH_FINDINGS.md` — current external scientific frontier;
- `AGENT_RESEARCH_SYNTHESIS.md` — integrated project inference and experimental hypotheses.

Do not promote a research idea into this file until it survives a discriminating experiment.
## 9. Transfer gate — completed

Cognitive Transfer v0 tested a genuinely new sixth family:

```text
relation traversal
→ associative memory lookup
→ inferred rule transformation
```

Three-seed result after 1024 task-6 updates:

```text
arm                    final IID   final OOD
fresh                     55.5%       28.0%
ordinary transfer          96.0%       40.5%
frozen-how adapter         23.3%       21.0%
```

Zero-shot task-6 OOD from the pretrained core was only **8.7%**.

Ordinary full fine-tuning improved task-6 OOD by **12.5 points** over fresh training, but this is below the project's high-leverage threshold and did not produce strong compositional extrapolation.

More importantly, old-family OOD fell from **69.7% to about 7.1%** after ordinary task-6 fine-tuning: a **62.6-point loss**.

The frozen-how adapter used only **1,095 trainable parameters**, but finished below the fresh baseline.

Interpretation:

- some ordinary transfer exists;
- it is not large enough to justify another tuning cycle;
- the current frozen reusable-"how" hypothesis failed this test;
- full fine-tuning catastrophically forgets old capabilities;
- 96.0% IID versus 40.5% OOD for ordinary transfer points to a compositional/algorithmic generalization failure rather than simple inability to fit task 6.

### Operator routing gate — completed

`AGENT_OPERATOR_ROUTING_GATE_V0.md` compared a parameter-matched shared factor processor against an oracle-routed operator bank on the existing held-out composition task.

Three-seed result after 1024 updates:

```text
                         IID      OOD
shared factor core      43.7%    27.0%
oracle operator core    95.8%    41.2%
```

The oracle arm improved OOD by **14.2 points**, below the precommitted **20-point** high-leverage threshold.

The more important split is:

```text
oracle IID   95.8%
oracle OOD   41.2%
```

Supplying the correct decomposition and execution route almost solves fitting, but does not produce strong extrapolation to longer chains.

Decision:

- high-leverage gate failed;
- do not build the learned-router branch;
- do not tune the oracle operator core for incremental gains;
- explicit decomposition is useful evidence about learnability, but it is not promoted as the Agent core;
- routing is no longer the immediate bottleneck because this experiment supplied the route.

### Next high-information gate — research first

The next question moves inside the operator itself:

> What makes a learned operation extrapolate across **depth/length** when decomposition and routing are already correct?

Return to the research pair before building again. Focus on:

- algorithmic alignment;
- length/depth generalization in recurrent or graph processors;
- stable variable/entity binding across repeated execution;
- state representations that remain invariant under longer trajectories;
- supervision/objectives that favor execution rules over short-chain heuristics.

A new build should isolate one of these mechanisms against the failed oracle-operator baseline and must again offer a step-change, not a few extra OOD points.
## 10. Current demotions / stopped branches

Do not keep rescuing these without new evidence:

- fixed-patch byte RNN;
- slot-query attentive BiGRU;
- input reinjection in Cognitive Core v0;
- simple one-shot destructive-update importance scores;
- static capacity as a solution to development;
- extra recurrent depth past the observed saturation point;
- small aggregate recurrence gains as a reason for prolonged tuning;
- frozen-how adaptation on Cognitive Transfer v0;
- ordinary full fine-tuning as a lifelong-learning solution.
- oracle-routed operator bank as sufficient for compositional OOD;
- learned routing as the immediate next branch.

## 11. Non-negotiable evaluation rule

Architectural elegance does not count.

A mechanism survives only if the whole-system gain justifies:

- quality;
- OOD/transfer ability;
- wall-clock cost;
- memory movement;
- routing/recognition overhead;
- storage;
- developmental cost;
- maintenance/research cost.

> Structural changes must pay rent — and the rent should usually be large enough to matter.

## 1B. Developmental Nursery v0 — local self-construction gate

A new architecture-invention track has earned promotion into current project truth.

The goal remains the self-contained conversational agent, but the project will not assume that humans must hand-design all of its eventual internal computation.

Working developmental rule:

```text
RESEARCH
→ SYNTHESIZE
→ BUILD THE BEST CURRENT SMALL TEST
→ EVALUATE CAUSALLY
→ KEEP / REVERT
→ COMPRESS SURVIVING COMPUTATION INTO REUSABLE PRIMITIVES
→ ATTACK THE NEXT HIGHEST-LEVERAGE BOTTLENECK
```

### Local gate result

A fully local Python-standard-library prototype implemented:
- a tiny executable instruction substrate;
- bounded synthesis;
- self-authored macro operations;
- archive-based descendant search;
- held-out validation;
- causal ablation hooks;
- compression pressure.

On the first untouched composition holdout:

```text
fixed primitive system     0 / 5
self-constructed genome    5 / 5
```

The promoted genome independently recovered three reusable latent operations from developmental experience.

A stress variant initially failed (1/5) because retrospective compression over-prioritized frequent past fragments and did not propose a rarer future-useful operation.

The developmental law was changed from research rather than target-specific hand-coding:
- compact whole solved procedures are now prospective candidates even if seen once;
- archive selection preserves structurally different stepping stones.

The previously failing variant then reached:

```text
revised developmental system   5 / 5
```

This is a **toy-domain positive gate**, not evidence of general intelligence.

### Adopted build implications

Promote:
- stable parent + disposable descendants;
- archive rather than latest-only self-modification;
- external immutable evaluator;
- executable computational genome;
- both retrospective compression and prospective skill proposals;
- causal promotion/ablation;
- compression of surviving repeated computation into new primitives.

Do not yet promote:
- unrestricted Python self-rewriting;
- blind genetic search;
- one fixed graph/MoE architecture;
- the toy stack DSL as the final cognition substrate.

### Next high-leverage gate

Test the scaling claim behind:

`STORE BROADLY / ACTIVATE NARROWLY / DEVELOP SELECTIVELY`.

Specifically:

> increase stored reusable computation by 10× and then 100× while measuring whether relevant-capability retrieval, active program size, RAM traffic, and search cost can remain nearly bounded.

A naive global scan is expected to fail this gate; the experiment should compare candidate addressing mechanisms and allow the developmental system to change them.

Whole-Agent Closure remains the eventual integration milestone. The developmental nursery is now a candidate mechanism for how the internal agent grows rather than a replacement for the conversational end test.

## 1C. Dormant Capability Addressing Gate v0 — promoted

The first scaling test of:

`STORE BROADLY / ACTIVATE NARROWLY`

passed at the isolated addressing layer.

### Exact in-memory result

Across 128 → 12,800 stored modules, adaptive hierarchical search matched exhaustive nearest-neighbor search exactly while touching a small fraction of the store.

Moderate ambiguity:

```text
100× storage
~2.85× module inspections
~0.39% of modules touched/query at 100×
```

Harder ambiguity:

```text
100× storage
~5.02× module inspections
~0.77% touched/query
```

The search naturally spends more computation when unresolved branches can still change the answer.

### Disk-backed result

The first hierarchy kept all metadata in RAM and therefore failed the stronger memory-scaling requirement.

The revised implementation pages lower index structures and capability data from disk.

Three-seed disk-backed result at moderate ambiguity:

```text
cold store growth            ~97×
module inspections growth    ~2.57×
logical I/O growth           ~1.47×
selected payload/query       constant 4 KiB
retrieval                    100%
```

This ran locally with Python stdlib + SQLite; no GPU/model/runtime dependency was required.

### Promotion decision

Promote as current infrastructure hypothesis:
- capability payload may remain cold;
- keep navigation metadata much smaller/hotter than capability payload;
- use hierarchical/adaptive retrieval;
- search effort should be conditional on ambiguity;
- active I/O, not total stored bytes, is the key scaling metric.

Do not promote the current kd-tree/SQLite implementation as the final architecture.

### Next gate

The addressing experiment used privileged module keys.

The next high-leverage question is:

> Can the agent construct the address from **current state + desired effect**, then retrieve and compose useful executable modules without being told their identity?

Build the next gate with behavioral/functional module signatures rather than arbitrary random vectors.

## 1D. Effect Address + Reachability Gate v0

A second developmental/addressing gate tested whether module identity can be inferred from behavior rather than supplied directly.

### Behavioral addressing result

12,800 executable modules were indexed by behavioral signatures.

A tiny from-scratch address model learned from developmental traces:

```text
(current behavior, desired behavior)
→ address of next useful computation
```

Held-out developmental states:

```text
top-1 correct next operation   99.6%
top-8                         100.0%
```

Deeper OOD composition traces:

```text
top-1   68.5%
top-8   88.5%
```

Behavior/effect addressing is therefore retained as a promising mechanism.

### Immediate-causality rule rejected

Choosing among retrieved candidates by which operation improves the target most immediately does not generalize to deep compositions.

A future-reachability oracle, holding retrieval fixed, produced a large capability jump in the diagnostic sample:

```text
6.25% → 30.0% solved
```

Therefore:
- immediate improvement != mattering;
- mattering must include future reachability / downstream consequence.

### Tiny learned value replacement rejected

A small goal-conditioned value network trained from shallow developmental consequences did not recover the oracle gain:

```text
myopic       29%
learned V    19%
```

Do not tune this branch for a few points.

### Next high-leverage gate

Research before build:

> What compact learned structure can predict the **future affordances/reachability created by a computation**, generalize across goals, and compose over longer horizons without expensive tree search?

Priority mechanism families:
- successor features / successor-like computational representations;
- reusable option/skill consequence models;
- planning over compressed learned operations;
- explicit uncertainty so unknown future consequence triggers search rather than false confidence.

The whole-agent target remains unchanged.

## 1E. Conditional reasoning probe — promising, not promoted

The project tested whether every decision needs the expensive future-reachability mechanism identified in Gate 1D.

### Structured future-distance representation

A quasimetric-style temporal-distance model improved deep toy composition:

```text
myopic       13.5%
quasimetric  20.5%
```

The gain is below the project's high-leverage threshold and cost increased. Do not tune this model.

### Adaptive computation upper bound

A perfect diagnostic trigger doubled solve rate on a small sample:

```text
cheap-only   20%
adaptive     40%
```

while escalating to expensive search on only ~25% of decisions.

This supports the **principle** of conditional reasoning depth.

### Learned trigger

A tiny metacontroller recovered the solve-rate improvement on another small sample:

```text
cheap-only       16%
learned trigger  24%
perfect trigger  24%
```

but escalated too often:

```text
learned   ~39% of decisions
perfect   ~19%
```

The sample is too small and the gain too modest for architectural promotion.

### Current next question

Do not tune the trigger.

Research/build next around:

> **Can expensive successful reasoning be compiled into reusable computation and metacontrol so repeated classes of problems become cheaper over the agent's lifetime?**

The desired developmental cycle is now:

```text
cheap attempt
→ uncertainty / failure
→ expensive search
→ successful trajectory
→ causal validation
→ compile reusable capability
→ store cold
→ learn when to retrieve it
→ future problem solved with less active compute
```

A successful gate should show both:
1. capability retained or increased;
2. cost per repeated problem class falls materially after consolidation.

## 1F. Reasoning amortization + active falsification — promoted

A core developmental hypothesis now clears the project's high-leverage bar:

> **pay for hard reasoning once, validate what was discovered, compile it into cold capability, and avoid paying the same reasoning cost again.**

### Reasoning amortization replication

Three independent 40-class runs:

```text
compiled after fixed validation   92.5%–95%
compiled correctness on hit       100%
first search expansions           mean 322–393
repeat expansions incl fallback   mean 7–27
search reduction                  ~12×–55×
median latency reduction          ~167×–242×
```

Novel classes produced zero false cache hits.

The remaining 5–7.5% failure was caused by under-specified behavioral evidence: seven probes sometimes admitted multiple programs with different unseen behavior.

### Active falsification repair

A 21,845-program bounded hypothesis space was used to test whether the agent could identify when evidence was insufficient.

Starting from the same seven probes, it selected an additional probe only when surviving hypotheses disagreed.

Three-seed result:

```text
fixed-probe generalization      92.5%–95.0%
active-probe generalization    100.0%
compiled fraction              100.0%
compiled correctness           100.0%
mean extra probes / skill       0.275–0.475
median extra probes             0
maximum extra probes            2
```

Across 36 novel classes:
- zero false cache hits;
- 100% first-encounter identification;
- 100% compilation;
- 100% second-encounter correctness.

### Promoted developmental law

Durable self-modification should require:

```text
reason/search
→ propose computation
→ actively seek a distinguishing counterexample
→ acquire only the missing evidence
→ revise if falsified
→ compile only after ambiguity is removed
→ store cold
→ retrieve and execute cheaply later
```

This supersedes the weaker rule “works on held-out examples, therefore compile.”

### Next integrated developmental gate

Do not optimize this toy synthesizer further.

Combine the surviving mechanisms into one lifetime test:

1. novel problems initially require expensive reasoning;
2. successful procedures are actively falsified;
3. validated procedures enter a growing cold skill store;
4. effect-based addressing retrieves them later;
5. unfamiliar/ambiguous cases still escalate to search;
6. as the skill store grows by at least 10×, measure:
   - accumulated capability;
   - average active search expansions;
   - bytes/pages touched;
   - cache hit precision;
   - false reuse;
   - extra falsification probes;
   - cost on genuinely novel tasks.

The desired result is not merely a faster cache.

It is a developmental scaling law:

> **more total capability, less repeated reasoning, and little growth in active work per thought.**

## 1G. Integrated Developmental Lifetime Gate v0 — promoted

The major developmental mechanisms now work together in one bounded lifetime test.

Verified skill store:

```text
32 skills
→ 320
→ 3,200
```

Three replicated scaling curves:

```text
skill count                         100×
cold-store bytes                   ~93.7×
familiar skill rows touched        ~1.43×
familiar certificate queries       ~1.79×
active selected payload             constant 4 KiB
standardized 80/20 active work     ~1.27×
```

Across all stages/seeds:

```text
familiar retrieval                 100%
correctness on familiar hit        100%
novel false reuse                    0
```

This passes the isolated developmental scaling gate.

### Promoted principle

```text
NOVEL
→ reason/search
→ actively falsify candidate
→ compile verified computation
→ store it cold

FAMILIAR
→ effect address
→ cheap falsification certificate
→ page one capability
→ execute
```

As the bounded skill library grew by two orders of magnitude, active work grew only modestly rather than proportionally.

### Important limit

The task supplied a compact behavioral goal specification.

Real conversation does not hand the agent a seven-probe function signature.

Therefore the next project bottleneck is no longer storage, compilation, or toy library scaling.

Return to **Whole-Agent Closure**:

> map bytes/language + conversational context into a structured goal/effect state; use that state to select/compose homegrown computation; feed the resulting state into the homegrown producer.

The nursery should now serve as developmental infrastructure for the conversational agent, not become the objective itself.

## 1H. Guided frontier + pointer-language gates — 2026-09-29

Two new mechanisms cleared meaningful gates; two related input-binding designs failed.

### Novel reasoning: learned proposal + explicit frontier

On unseen 4–7-step toy compositions with 12,800 stored candidate modules:

```text
myopic learned rollout      18.10% solved
guided frontier, width 6    42.14%
guided frontier, width 18   53.10%
```

Three-seed mean, 140 tasks/seed.

This is a 2.93× capability increase without changing the learned proposer.

Decision:
- promote **proposal + bounded explicit frontier** as the current novel-reasoning pattern;
- do not promote fixed beam width as final architecture;
- use variable test-time compute;
- successful expensive reasoning should still be compiled/cold-stored so repeated problems return to cheap execution.

### Language production: pointer/copy producer

A 19,789-parameter recurrent producer learns ordinary output bytes plus four COPY(role) actions.

Three-seed result:

```text
IID exact                        100%
all lexical values unseen        100%
mixed known/unseen lexical       100%
mean training time               ~14.4 s
```

The hot producer does not need to memorize names/entities/content that already exist in structured state.

Decision:
- promote pointer/copy production for the next integrated language gate;
- exact content remains structured/cold; linguistic scaffolding stays hot.

### Language perception: current span binders failed

Per-byte role tagging and independent role start/end pointers were both rejected.

Best all-unseen-lexical exact result among them: 10.8%.

Do not tune.

### Next high-leverage gate

Research/build:

> **structured span composition for perception** — parse an utterance into action/query structure plus role-bearing spans, with explicit structural constraints, so arbitrary unseen byte strings can be bound into internal state.

Success criterion should include:
- held-out paraphrase structure;
- entirely unseen entity/value strings;
- exact span binding;
- multi-turn memory use;
- no fixed lexical classifier;
- end-to-end connection to the surviving COPY(role) producer.

The whole-agent target remains the authority. Synthetic reasoning gates stay diagnostic.

## 1I. Structured Span Perception v0 — binding passed, paraphrase gate confounded

GitHub Actions run 36653384798 tested a 77,274-parameter byte BiGRU with joint bounded span scoring over typed roles.

Three-seed result:

```text
IID exact                         100.0%
unseen arguments, familiar form  99.5%–99.9%
held-out paraphrases              15.7%–17.8%
unseen args + paraphrases         17.3%–17.8%
```

Training took about 19 seconds/seed on GitHub CPU.

### What passed

The system can bind arbitrary byte strings into typed semantic roles without a fixed lexical classifier.

This is a strong improvement over the rejected per-byte tagger and independent start/end pointer designs.

### What did not pass

The held-out paraphrase split remained poor even after 1,200 updates.

However, inspection of the split exposed a benchmark confound: the held-out forms introduced previously unseen semantic words such as "retrieve", "associated", "recall", and "keep".

A from-scratch learner with no grounding for those words cannot be expected to infer their meanings solely from architecture.

Therefore this result does **not** establish that structured span composition itself fails.

### Corrected evaluation decomposition

Language perception is now evaluated as three separate capabilities:

1. **argument OOV binding** — new names/entities/values under familiar language;
2. **structural OOD** — new combinations of already-grounded linguistic primitives;
3. **lexical-semantic acquisition** — genuinely new words/constructions that require contextual or behavioral grounding.

The first is provisionally passed in this toy regime.

A deconfounded structural-OOD gate is now running with the same model and only the benchmark changed.

Do not build a larger parser until that gate decides whether the failure is structural or lexical.

## 1J. Learned Construction Library v0 — promoted

The deconfounded structural-OOD gate showed that the byte BiGRU span model still failed to systematically recombine known language:

```text
structured-span neural exact OOD
seed 0   34.9%
seed 1   31.6%
seed 2   28.5%
```

The same task was then given to a learned construction library.

### Construction induction

The learner receives grounded training examples and their structured semantic state.

It:
1. replaces grounded argument spans with typed holes;
2. compares unique surface structures across different semantic attributes;
3. anti-unifies the single differing surface position;
4. infers the surface-token → semantic-attribute mapping;
5. compiles only construction schemas grounded under at least two different semantic attributes.

No held-out construction×attribute pair is supplied.

Three-seed result:

```text
learned constructions             8
fit time                          ~0.04 s
structural OOD exact              100%
structural OOD + unseen args      100%
unparsed                           0
```

The system independently inferred:

```text
color → color
pet   → pet
place → place
```

from cross-example semantic alignment.

### Decision

Promote **explicit learned constructions** as a serious perception representation.

Do not interpret this as open-domain language solved.

What has passed is narrower and important:

> reusable surface→semantic constructions can systematically recombine grounded linguistic pieces where the sequential neural span encoder fails badly.

The construction library is naturally compatible with cold storage, sparse retrieval, typed slot binding, one-shot/few-shot addition, causal validation before promotion, and compression of repeated language experience.

### Next gate

Test developmental language growth:

1. recursive composition of known constructions/wrappers;
2. one/few-shot grounding of a genuinely new wording;
3. reuse of that wording with new attributes and unseen argument strings;
4. zero regression on existing constructions;
5. bounded active matching cost as the construction store grows.

If this passes, perception should move toward a hybrid of learned construction/grammar storage, small learned ranking for ambiguity/novelty, and explicit fast-mapping for new constructions.

## 1K. Developmental Construction Grammar v1 — promoted

Three-seed external CI tested whether the learned construction store can develop rather than merely interpolate.

### Recursive construction learning

Four semantics-preserving wrappers were learned only from paired grounded utterances:

```text
please, ...
for reference, ...
right now, ...
in this case, ...
```

Training contained each wrapper separately. Test utterances composed 2–3 wrappers in combinations never observed.

Result:

```text
recursive unseen composition   100% exact   (3/3 seeds)
```

### One-shot construction fast mapping

The existing grammar was then shown one grounded example of a completely new SET wording and one grounded example of a completely new ASK wording. Those surface constructions did not parse before exposure.

After one exposure, each construction remained tentative but generalized immediately to different semantic attributes and entirely unseen argument strings:

```text
one-shot SET reuse   100% exact   (600/600 per seed)
one-shot ASK reuse   100% exact   (600/600 per seed)
```

After one independent grounding under a second attribute, each tentative construction was promoted to durable storage.

```text
durable new constructions      100% exact
old language after learning    100% exact
regression                     0 points
```

### Decision

Promote the developmental construction mechanism in the controlled regime:

```text
known construction pieces
→ recursive composition

unknown wording + grounded consequence
→ tentative construction
→ immediate sparse reuse
→ independent confirmation
→ durable construction
```

### Next bottleneck

The matcher still performs a global scan over all stored constructions.

Next gate: scale the cold construction store by 10×–10,000× and require retrieval precision to remain 100% while the number of activated candidate constructions stays nearly bounded.
