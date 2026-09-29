# Agent Research Synthesis — Integrated Possibility Model

**Date:** 2026-09-29  
**Status:** LIVING RESEARCH MODULE — PROJECT INFERENCE  
**Pair:** `AGENT_RESEARCH_FINDINGS.md`

## Purpose

This file answers:

> **When the external findings are linked together with our own experiments, what architecture or mechanism appears possible — and how does that belief change when we test it?**

This file is allowed to hypothesize.

It must **never disguise synthesis as established science**.

```text
external literature
        ↓
AGENT_RESEARCH_FINDINGS.md
        +
our immutable experiment/result records
        ↓
this synthesis
        ↓
discriminating experiment
        ↓
AGENT_CURRENT.md only if the mechanism survives
```

A dedicated research chat should normally load **FINDINGS + SYNTHESIS together**.

---

## Strategic scope correction — whole-agent objective

The compositional-OOD work produced useful causal information, but it began to dominate the research agenda beyond its role in the actual project.

The project target is not:

> maximize performance on synthetic compositional reasoning.

It is:

> build a self-contained, from-scratch conversational agent that can move across topics, remember, reason, retrieve knowledge, and generate each response from its own learned machinery.

Current whole-agent audit shows larger missing capabilities than the latest cognition benchmark:

1. the from-scratch perception/cognition/production stack is not yet closed into the runtime;
2. the language/semantic interface is still bounded/toy-scale;
3. broad knowledge acquisition/retrieval is not integrated with the homegrown language system;
4. multi-turn topic switching and thread resumption are not yet demonstrated by the homegrown stack.

Therefore:

> compositional generalization remains an important diagnostic stress test, but it is **not currently the primary research target**.

The research loop should now prefer questions whose answers plausibly unlock the whole conversational system: from-scratch language/state interfaces, memory-conditioned generation, broad knowledge access without a pretrained LLM, and integrated multi-turn control.

Research on isolated cognition should regain priority only when a whole-agent failure points back to it.

---
## Current integrated model

### S1. The missing thing is probably not “a better monolithic core”

Our largest cognitive gain came from changing internal organization:

```text
flat MLP          23.9% OOD
factor one-pass   59.8% OOD
```

But the shared factor processor later showed:

```text
task-6 transfer IID   96.0%
task-6 transfer OOD   40.5%
```

It can fit a new composition but does not reliably extrapolate it.

External research independently keeps finding that systematic reuse depends on decomposition, specialization, binding, routing, and the training distribution.

**Current synthesis:**

> Keep a structured relational state, but stop expecting one undifferentiated learned processor to become a general compositional engine merely through multitask exposure.

**Confidence:** high.

---

### S2. Reusable computation probably has to become identifiable during learning

Our failed frozen-HOW experiment assumed that ordinary multitask training had already embedded reusable computation in a form that a tiny adapter could access.

That assumption failed:

```text
fresh final OOD        28.0%
frozen-how final OOD   21.0%
```

The literature gives a coherent explanation: reusable components often appear only when the training regime **forces specialization/reuse** through compositional curricula, routing pressure, competition, predictive structure, low-rank componentization, or explicit task inference.

**Revised synthesis:**

> Do not train a generic processor first and search for modules afterward. Train the system under conditions where reusable computation is useful during acquisition.

**Confidence:** high.

---

### S3. There are four distinct problems that must not be collapsed into “modularity”

The research frontier separates:

```text
1. DECOMPOSITION
   What reusable computations exist?

2. BINDING / STATE
   What entities, variables and roles are those computations acting on?

3. ROUTING / SEQUENCING
   Which computation acts next, and where?

4. EXECUTION / PLASTICITY
   How is the selected computation executed repeatedly without rewriting everything else?
```

A model can succeed at one and fail at another.

Our previous transfer experiment mostly tested whether useful decomposition already existed inside a shared processor. It did **not** independently test binding or routing.

**Current synthesis:**

> Future tests should isolate these variables rather than comparing vaguely “modular” versus “non-modular” architectures.

**Confidence:** very high.

---

### S4. The factor graph is currently our best candidate for the binding/state layer

The factor representation gave a step-change gain and naturally preserves:

- entities;
- relations;
- event/query roles;
- shared identity;
- local message paths.

Recent variable-binding work shows that even generic neural architectures can learn addressable binding mechanisms, but our factor representation already supplies an explicit relational scaffold that has paid rent experimentally.

**Current synthesis:**

> For the next gate, hold the factor-state representation fixed. Do not change representation and execution simultaneously.

This lets us ask whether the failure lives in the processor/routing layer.

**Confidence:** high.

---

### S5. Routing was not the immediate bottleneck we thought it might be

The research refresh elevated routing because many successful compositional systems explicitly select and sequence reusable computation.

Operator Routing Gate v0 then supplied the correct semantic decomposition and route directly.

Result:

```text
shared factor core      43.7% IID   27.0% OOD
oracle operator core    95.8% IID   41.2% OOD
```

The oracle route massively improved fitting but only added **14.2 OOD points**, below the high-leverage gate.

**Revised synthesis:**

> Routing matters in the general problem, but it is not the next bottleneck in this benchmark. Even with the route solved, the learned operators do not extrapolate strongly to longer execution depth.

The immediate question becomes whether the operation learned on short chains is an actual reusable algorithm or a short-horizon approximation.

**Confidence:** high.

---
### S6. Recurrent depth remains useful, but as an executor

Our own depth probe:

```text
1 step   38.1%
2 steps  51.2%
4 steps  62.0%
6 steps  63.0%
8 steps  62.8%
```

External work also supports iterative execution, but the strongest recent OOD results combine recurrence with structured latent state, algorithmic supervision, task inference, or error correction.

**Current synthesis:**

> Recurrence is a clock/execution resource. The interesting question is **what operation is repeated or selected at each step**, not whether recurrence exists.

**Confidence:** high.

---

### S7. Global full fine-tuning is incompatible with the developmental goal

Our transfer result:

```text
old-task OOD before transfer   69.7%
old-task OOD after transfer     7.1%
loss                           62.6 points
```

This is decisive.

A developing agent cannot use global full-network adaptation as its default way to add a skill.

The external literature's modular, task-inference, local-component and parameter-isolation mechanisms all attack this same problem from different directions.

**Current synthesis:**

> Long-lived capability should reside in reusable components whose selection/composition can change faster than the components themselves.

**Confidence:** very high.

---

### S8. The four-layer loop remains a possibility, but the operator layer is now the weak link

The broad decomposition remains conceptually useful:

```text
STRUCTURED STATE / BINDINGS
          ↓
CONTROL / TASK INFERENCE
          ↓
ROUTER / SEQUENCER
          ↓
REUSABLE LEARNED OPERATIONS
          ↓
ITERATIVE EXECUTION
          ↺
```

But Operator Routing Gate v0 prevents us from treating this as the next architecture to build.

Supplying the operator boundaries and sequence produced near-solved IID fitting while OOD stayed weak. Therefore the unresolved issue is more basic:

> Can a learned operation preserve the same semantics when it must execute for more steps, on longer paths, or under new bindings?

Until that is demonstrated, an operator bank risks becoming a collection of specialized short-horizon functions rather than reusable cognition.

**Confidence in the broad loop:** medium-low.

**Confidence that depth-generalizing operator semantics are the next research target:** high.

---
## What changed over the project

### Stage A — developmental recurrent ecology

Early experiments showed that sparse execution, shallow recurrence, specialization and local developmental structure can matter.

**Revision:** keep those mechanisms as options; do not force the whole agent into one cell ecology.

### Stage B — language separated from cognition

Different architectures won perception and production.

**Revision:** language organs and cognition may be separate learned systems.

### Stage C — relational organization produced the first large cognitive jump

Factor organization massively beat a flat core.

**Revision:** representational inductive bias became a primary architectural variable.

### Stage D — more thought helped, then saturated

Repeated computation unlocked some capabilities but mostly saturated around four steps.

**Revision:** recurrence is conditional compute, not general intelligence by itself.

### Stage E — shared-core transfer failed

The shared processor showed modest transfer, weak zero-shot composition, poor OOD extrapolation and catastrophic forgetting.

**Old hypothesis weakened:**

> ordinary multitask learning may create a hidden general HOW that can be frozen and cheaply redeployed.

**Revised hypothesis:**

> reusable computation probably needs to be made identifiable **during training**, and composition requires learned binding/routing rather than a tiny adapter over a generic frozen processor.

### Stage F — 2026-09-29 research refresh

The literature review split the vague idea of “modularity” into four independently testable mechanisms:

```text
decomposition
binding/state
routing/sequencing
execution/plasticity
```

It also elevated two constraints:

- training coverage/distribution can determine whether apparent composition is genuine;
- successful modularity requires functional specialization, not just structural separation.

**Revision:**

> The next experiment should hold state representation fixed and isolate whether explicit reusable operators + sequencing solve the failure.

---

## Completed hypothesis H1 — oracle operator decomposition

H1 asked whether explicit reusable operators could produce a large OOD advantage over a shared processor when the route was supplied.

Rigorous three-seed result:

```text
                         IID      OOD
shared factor core      43.7%    27.0%
oracle operator core    95.8%    41.2%

OOD delta                       +14.2 points
required gate                   +20.0 points
```

**H1 failed the high-leverage gate.**

The architecture clearly improves optimization/sample acquisition on the training distribution, but it does not solve depth extrapolation.

Per the precommitted decision rule:

- learned routing is not built next;
- automatic operator discovery is not built next;
- the positive IID result is retained as evidence, not promoted into architecture.

## Next research hypothesis — depth-invariant learned operations

The next cycle returns to research before another build.

Working question:

> What mechanism makes a learned computation behave like the **same operation at depth 5 as at depth 1**, rather than learning a short-chain approximation?

Candidate mechanism families to research, not yet adopt:

- algorithmic alignment / neural algorithmic reasoning;
- recurrent processors trained on execution traces or intermediate invariants;
- stable variable/entity binding across repeated updates;
- equivariant or state-machine-like transition structure;
- training distributions that force length extrapolation rather than finite coverage;
- error-correcting / anchored latent execution.

The next experiment should change **one** of these while holding decomposition and route fixed, so the failure remains interpretable.
## Research-to-build promotion rule

```text
EXTERNAL FINDING
→ SYNTHESIS / POSSIBILITY
→ EXPERIMENTAL HYPOTHESIS
→ SURVIVING BUILD DECISION
```

FINDINGS owns external science.

This document owns synthesis and experimental hypotheses.

`AGENT_CURRENT.md` changes only after experimental survival.

---

## Evolution log

### 2026-09-29 — after Cognitive Transfer v0

**Prior synthesis:** a shared multitask factor processor might contain reusable computation accessible by cheap adaptation.

**Prediction:** frozen-HOW adaptation should substantially beat learning task 6 from scratch.

**Result:** frozen-HOW underperformed fresh training; ordinary fine-tuning gave only modest OOD transfer and destroyed old-task performance.

**What survived:** factor state organization; recurrence as useful compute.

**What failed:** hidden reusable-HOW assumption; global fine-tuning as developmental mechanism.

**Revised synthesis:** reusable computation must likely become more identifiable/specialized during training.

### 2026-09-29 — after research phase 1

**Prior synthesis:** build an operator-composition core.

**New evidence:** modularity itself is insufficient; literature separates specialization, binding, routing, training coverage and iterative execution. Routing and task inference repeatedly appear as explicit mechanisms.

**What survived:** operator-system direction.

**What changed:** the next experiment must not confound operator representation with routing or automatic module discovery.

**Revised synthesis:** first establish an oracle-decomposition upper bound, then test learned routing, then — only if both pass — test automatic discovery.

**Next discriminating question:**

> Does explicit operator decomposition produce a large compositional-OOD gain over the current shared factor processor, and if so, can a learned router recover most of that gain?

---

### 2026-09-29 — after Operator Routing Gate v0

**Prior synthesis:** explicit decomposition plus an oracle route should reveal whether routing/decomposition was the main obstacle to compositional OOD.

**Prediction:** if operatorization was the missing organization, the oracle arm should beat the shared core by at least 20 OOD points.

**Result:** oracle operators reached 95.8% IID but only 41.2% OOD versus 27.0% OOD for the shared core; +14.2 points, below gate.

**What survived:** explicit decomposition strongly improves learnability/fitting; factor state remains useful.

**What failed:** the claim that decomposition/routing is sufficient for strong compositional extrapolation.

**Revised synthesis:** the learned operation itself lacks robust depth/length invariance. Routing is demoted as the immediate bottleneck.

**Next discriminating question:** what training/representation constraint makes a learned operator execute an invariant rule over longer trajectories?

---
## Current synthesis frontier

The present best hypothesis is narrower than before:

> Structured state and modular control may still be useful, but **reusable cognition requires learned operations whose semantics remain stable across execution depth, path length, and binding changes**. Decomposition and routing cannot compensate for operators that only approximate short training trajectories.

The next job is research, not architecture expansion:

> identify the strongest demonstrated mechanisms for **depth/length-generalizing learned execution**, then design one cheap test that can distinguish a genuinely invariant operator from a short-horizon heuristic.

## Developmental synthesis S9 — guided self-construction

The project now has a stronger interpretation of "develop selectively":

> We should hand-build the developmental laws and external evaluator, while allowing increasingly large portions of useful computation to be authored by the agent's own computational genome.

The current synthesis is not blind evolution and not unrestricted source rewriting.

```text
immutable experimental physics
    ↓
stable parent / archive
    ↓
candidate computational mutations
    ↓
automatic evaluation + ablation
    ↓
promotion only when capability or efficiency materially changes
    ↓
compression / library learning
    ↓
new reusable primitive
```

Human/project research remains active. Literature-derived mechanisms enter as candidate mutations or diagnostic prostheses rather than permanent architectural commandments.

### Why the archive matters

PowerPlay's known greedy failure mode and Darwin Gödel Machine's archive results point in the same direction: a single latest-only lineage is too easy to trap in small local improvements.

Current project hypothesis:

> preserve a tree/archive of useful but different computational genomes; select both for quality and for stepping-stone diversity.

### Why compression is not enough

DreamCoder/Babble/Stitch support extracting reusable abstractions from solved programs, but prospective-compression work suggests that a primitive can be valuable for future composition even when it was rare in the past.

Current project hypothesis:

> generate primitive proposals from both repeated/compressible structures and compact whole skills; let held-out prospective utility decide which survive.

### Why this connects to "what matters"

The promotion criterion should be causal rather than correlational:

- remove the candidate;
- rerun capability/efficiency tests;
- keep it only when its presence changes reachable performance or cost;
- preserve the failure conditions and dependencies.

This is a concrete implementation path for the earlier project concept that a structure "matters" when intervention on it changes future capability.

### Local Developmental Nursery v0 result

A Python-standard-library-only nursery was built and run in the local container.

Generation-0 substrate:
- 9 primitive stack-machine instructions;
- bounded program synthesis;
- solved-program traces;
- self-authored macro primitives;
- descendant archive;
- external immutable validation;
- final untouched composition holdout.

Initial hidden motif set:
- fixed primitive library: 0/5 final held-out compositions under the short-program constraint;
- evolved three-macro genome: 5/5.

A three-motif-family stress pass exposed a failure:
- two families: 5/5;
- third family: 1/5.

Failure analysis:
- retrospective compression and a narrow candidate queue preferred frequent past fragments;
- a less-frequent but prospectively valuable operation was never given a fair promotion test.

Research-backed revision:
- propose both frequent compression candidates and compact whole solved procedures;
- preserve structurally diverse archive branches;
- let validation decide prospective utility.

On the previously failing family, the revised nursery reached 5/5 final held-out compositions and promoted the three useful procedures without the missing procedure being manually inserted.

### What this result does and does not support

Supported:
- a tiny local system can author new reusable executable operations from experience;
- those operations can unlock compositions unavailable under the same active program-depth limit;
- research-guided developmental laws can repair a discovered failure without hand-coding the target skill;
- this loop runs comfortably without a pretrained model, GPU service, or external training infrastructure.

Not supported yet:
- open-domain intelligence;
- language;
- neural self-development;
- reasoning-per-FLOP superiority;
- asymptotically constant active compute as stored capability grows;
- automatic invention of fundamentally new representation languages.

### Revised high-leverage question

> Can stored computational capability grow by 10×–100× while the active working set/search cost stays nearly bounded, and can the developmental system learn the addressing structure needed to make that true?

This directly links self-construction to the project's broader hypothesis: store broadly, activate narrowly, develop selectively.

## Developmental synthesis S10 — dormant capacity and effect-addressed computation

The Developmental Nursery established that reusable executable primitives can be self-authored in a toy domain. The next question was whether storing many such capabilities necessarily makes every thought expensive.

### Addressing Gate v0

A local pure-Python gate compared:
- exhaustive global scan;
- flat content buckets;
- hierarchical metric routing.

Store size increased:

```text
128 → 1,280 → 12,800 modules
1×      10×       100×
```

With exact adaptive branch-and-bound search, the hierarchy always returned the same nearest module as exhaustive scan in the validation runs.

At moderate query noise:

```text
store growth                  100×
hierarchy inspections growth  ~2.85×
active inspected fraction     ~0.39% at 100×
```

At harder noise:

```text
hierarchy inspections growth  ~5.02×
active inspected fraction     ~0.77% at 100×
```

Search effort increased with ambiguity rather than being fixed per query.

### Disk-backed gate

The in-memory hierarchy exposed a new failure: its Python index memory still grew roughly linearly with store size.

A second local gate moved lower hierarchy records and functional keys into SQLite with a capped cache and kept capability payloads in a separate disk file.

At moderate noise, across three seeds:

```text
cold store growth             ~97.2×
module inspections growth     ~2.57×
logical bytes/query growth    ~1.47×
payload bytes/query           4,096 → 4,096
target retrieval              100%
```

At harder noise:

```text
module inspections growth     ~4.85×
logical bytes/query growth    ~2.25×
target retrieval              100%
```

Opening the 100× disk index produced no measurable RSS increase in these runs with the SQLite cache capped; this is only a coarse process-level measurement, not a hardware cache proof.

### What survives

The project now has local evidence for:

> **stored capability can grow much faster than the amount of capability metadata/payload touched by one retrieval.**

This supports the broader STORE BROADLY / ACTIVATE NARROWLY hypothesis at the addressing layer.

### What does not survive yet

The gate supplied a good query address: a noisy vector near the target module key.

That is privileged information.

Therefore the important unresolved problem is no longer raw indexing.

It is:

> **How does the agent construct an address for computation that will matter from its current goal/state?**

### Revised hypothesis: effect-addressed computation

Static semantic similarity is probably insufficient.

The next candidate mechanism is to index reusable computation by compact descriptions of its **causal effect / behavioral signature**, then let the active reasoner construct a desired-effect query such as:

```text
current state
+ goal
→ desired state change
→ retrieve operations whose learned effects could cause that change
```

Program-synthesis work on property signatures and learned query selection gives external precedent for behavior-based addresses, but it does not yet establish this mechanism for open-ended cognition.

Next gate:

> Replace arbitrary module vectors with executable modules whose addresses are derived from observed behavior. Test whether unseen tasks can retrieve and compose useful modules from a goal specification without being given module identity.

## Developmental synthesis S11 — effect addresses work locally; myopic mattering fails

### Effect-address Gate v0

The arbitrary-vector addressing test was replaced with executable unary modules whose addresses were derived from observed input/output behavior on probes.

A tiny from-scratch address MLP was trained from developmental traces to map:

```text
current behavior + desired behavior
→ predicted behavioral address of the next useful operation
```

The cold library contained 12,800 executable modules.

On held-out developmental trace states:

```text
correct next operation top-1   99.6%
correct next operation top-8  100.0%
```

On deeper OOD composition traces:

```text
top-1   68.5%
top-8   88.5%
```

This is positive evidence that computation can be addressed by learned behavioral consequence rather than a human module ID, but the address model degrades with composition depth.

### Myopic causal selection failure

The active agent then retrieved eight candidates and executed each one to see which produced the largest immediate movement toward the target.

This failed badly on deeper tasks.

Reason:

> operations that improve the target metric immediately can move the system into states from which the goal is no longer reachable.

This revises the project's meaning of "what matters":

```text
not:
    immediate favorable causal change

but:
    causal contribution to desirable reachable futures
```

### Future-reachability oracle diagnostic

Holding the address model fixed, a bounded future-reachability oracle was used only as a diagnostic prosthesis.

On one deep-task sample:

```text
myopic selector              6.25% solved
future-reachability oracle  30.00% solved
```

On tasks solvable by the original useful-operation teacher:

```text
5.6% → 66.7%
```

The oracle also found alternative solutions using modules originally classified as distractors.

This is a high-leverage localization result: downstream reachability materially changes capability.

### Cheap learned UVFA-like approximation — failed

A tiny goal-conditioned value MLP was then trained from developmental consequence labels to replace the expensive oracle.

Fresh deep-task sample:

```text
myopic selector        29% solved
learned value selector 19% solved
```

Teacher-solvable subset:

```text
myopic   32%
learned  36%
```

The learned value model also consumed more candidate-selection steps.

Decision:
- do not promote this value network;
- do not tune it for incremental gains;
- preserve the oracle result as evidence that future reachability is the real missing variable;
- research mechanisms that represent reusable downstream consequences more structurally, especially successor-like representations, planning over reusable options, and developmental curricula that expose long-horizon consequences.

### Current synthesis

The strongest current architecture-level hypothesis is now:

> retrieval should propose operations by behavioral/effect address, while selection should depend on **predicted reachable futures**, not immediate similarity or immediate error reduction.

The unresolved invention problem is making that future-consequence estimate cheap, reusable, and able to generalize to deeper unseen compositions.

## Developmental synthesis S12 — conditional deep reasoning

### Quasimetric consequence gate

After the generic goal-conditioned value MLP failed, a directed temporal-distance representation was tested.

The model was constrained so its state-goal score had an asymmetric quasimetric-like form and was trained from multi-step developmental transition distances.

Fresh deep tasks:

```text
myopic selection       13.5%
quasimetric selection  20.5%
```

This is a positive direction but only +7 points and it used substantially more candidate-selection steps.

Decision:
- preserve the evidence that temporal structure helps;
- do not tune or promote this particular quasimetric model.

### Adaptive-compute upper bound

The next test asked whether expensive future search must run constantly.

A perfect diagnostic trigger used the expensive reachability oracle only when the cheap myopic choice would leave the goal unreachable and another retrieved candidate preserved reachability.

Small deep-task sample:

```text
cheap-only solve rate        20%
adaptive upper-bound         40%
expensive escalations        ~25% of decisions
```

This is high-leverage evidence that conditional deep reasoning could improve capability without making every decision expensive.

### Learned metacontroller probe

A tiny logistic metacontroller was trained only on cheap observable signals:
- address confidence/margin;
- immediate improvement;
- candidate disagreement/spread.

Small fresh sample:

```text
cheap-only          16%
learned trigger     24%
perfect trigger     24%
```

But:

```text
learned escalation fraction   ~39%
perfect escalation fraction   ~19%
```

The learned trigger recovered the sample's solve-rate gain but was not selective enough, and the test set was too small for promotion.

### Revised synthesis

The current best hypothesis is no longer one uniform reasoner.

```text
cheap effect-addressed proposal
        ↓
cheap local consequence check
        ↓
confidence / value-of-computation gate
      ↙                         ↘
act cheaply                perform deeper search
                               ↓
                    use result + compile experience
```

The next important question is developmental:

> Can expensive reasoning episodes train or compile structures that make the same class of future decisions cheap?

If yes, computation becomes an investment: hard problems temporarily cost more, but repeated reasoning is converted into new dormant capabilities and better metacontrol.

That directly links:
- self-authored computation;
- dormant capability storage;
- behavioral addressing;
- future reachability;
- adaptive compute.

## Developmental synthesis S13 — reason, falsify, then compile

### Reasoning Amortization Gate v0

The expensive-reasoning hypothesis was tested directly.

For each deep functional problem class:
1. bounded search discovered a procedure;
2. the procedure was tested on held-out inputs;
3. surviving procedures were compiled into a disk-backed skill store;
4. the same functional problem was encountered again.

Across three seeds, 40 developmental problem classes each:

```text
skills surviving fixed-probe validation   92.5%–95.0%
correctness given compiled cache hit      100%
first-encounter mean expansions           322–393
repeat mean expansions incl. fallback     7–27
expansion reduction                       ~12×–55×
median wall-clock reduction               ~167×–242×
```

Novel functional classes produced zero false cache hits. Once a novel class earned a validated skill, a later encounter executed it without synthesis search.

This is strong evidence for the developmental principle:

> expensive successful reasoning can be converted into dormant reusable computation, materially reducing future active compute.

### Failure that prevented full promotion

The fixed seven behavioral probes did not uniquely specify every function.

A synthesized program could match all seven examples yet differ on unseen inputs. Those procedures were correctly rejected by wider validation, leaving roughly 5–7.5% of classes uncompiled.

This was not a reason to lower the validation threshold. It exposed a specification problem.

### Active-Probe Compilation Gate v0

The fixed validation scheme was replaced with a bounded hypothesis space of 21,845 candidate programs.

The system begins with the same seven probes. If multiple surviving programs predict different behavior somewhere in a candidate input domain, it chooses a discriminating probe from their disagreement, queries the environment once, filters the hypothesis space, and repeats.

Across three independent seeds:

```text
fixed 7-probe generalization        92.5%–95.0%
active-probe generalization        100.0%
compiled skill fraction            100.0%
correctness given compiled hit     100.0%
extra probes / skill, mean          0.275–0.475
extra probes / skill, median        0
maximum extra probes                2
```

Thirty-six novel problem classes across the three seeds:
- zero false cache hits;
- 100% correct after first active identification;
- 100% compiled;
- 100% correct on the second encounter.

### Revised developmental law

The self-coding loop should be:

```text
expensive reasoning / synthesis
→ candidate procedure
→ attempt to distinguish/falsify it
→ if ambiguous, acquire the most informative missing evidence
→ resynthesize/filter
→ stop only when surviving hypotheses are behaviorally indistinguishable
→ causal/generalization validation
→ compile
→ cold-store
→ direct reuse
```

The system therefore does not merely ask whether a new procedure has worked before.

It asks:

> **What observation could still prove that this procedure means something different from what I think it means?**

This adds epistemic control to self-modification.

### Current synthesis frontier

The major pieces now demonstrated separately in toy form are:
- self-authored reusable computation;
- large cold stores with sublinear active retrieval work;
- behavioral/effect addressing;
- expensive future reasoning as a useful fallback;
- reasoning amortization by compilation;
- active falsification before durable promotion.

The next high-value test should combine these pieces in one developmental lifetime and measure whether:

> **capability accumulates while average active computation per familiar problem falls and cold-store growth does not force active-work growth.**

## Developmental synthesis S14 — integrated lifetime scaling

### Integrated Developmental Lifetime Gate v0

The previously surviving mechanisms were combined:

```text
expensive identification when novel
→ active falsification certificate
→ verified compiled skill
→ disk-backed cold store
→ behavior/effect-keyed lookup
→ certificate check
→ direct payload execution on familiar task
→ reject and escalate when unfamiliar
```

The verified cold library was scaled:

```text
32 → 320 → 3,200 skills
```

Each stored skill had a 4 KiB cold payload and a behavioral retrieval key plus its learned falsification certificate.

Three replicated scaling curves used a fixed 80/20 familiar/novel workload.

Across every stage and seed:
- familiar tasks were retrieved 100% of the time;
- every retrieved familiar skill was correct;
- genuinely novel tasks produced zero false reuse;
- novel tasks therefore still escalated to expensive identification.

Mean scaling result from 32 → 3,200 skills:

```text
skill count growth                100×
cold-store byte growth            ~93.7×
familiar rows touched growth      ~1.43×
familiar verification queries     ~1.79×
selected payload bytes            4 KiB → 4 KiB
80/20 active-work growth          ~1.27×
```

Median lookup latency remained in the ~0.014–0.018 ms range in this local Python/SQLite implementation, but wall-clock microbenchmarks at this scale should be treated as descriptive rather than as a hardware-independent claim.

### Interpretation

This is the first integrated toy result supporting the project's central scaling hypothesis:

> **total durable capability can grow by roughly two orders of magnitude while active work per thought grows only modestly, provided familiar computation is effect-addressed, cold-stored, and protected by compact falsification certificates.**

The result does not show that arbitrary cognition will have the same scaling law.

It does show that the earlier pieces can coexist without immediately destroying one another:
- compilation does not force the whole store into RAM;
- store growth does not force global scan;
- sparse retrieval does not create false reuse on the bounded task family;
- epistemic certificates allow cheap reuse while preserving novelty detection.

### Strategic consequence

Stop extending the toy function world unless a later whole-agent failure requires it.

The next unresolved bottleneck is again the real agent:

> **Can natural language / conversational context be converted into the structured goal/effect state needed to invoke this developmental machinery, and can the selected computation feed a homegrown response generator?**

This reconnects the developmental substrate to Whole-Agent Closure rather than allowing the nursery to become a separate benchmark project.
