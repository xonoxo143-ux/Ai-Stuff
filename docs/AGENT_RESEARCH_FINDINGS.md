# Agent Research Findings — Scientific Frontier

**Date:** 2026-09-29  
**Status:** LIVING RESEARCH MODULE — EXTERNAL EVIDENCE  
**Pair:** `AGENT_RESEARCH_SYNTHESIS.md`

## Purpose

This file answers one question:

> **What does the external scientific literature currently support that is relevant to building this agent?**

It does **not** contain our architecture preferences, project conclusions, or speculation. Those belong in `AGENT_RESEARCH_SYNTHESIS.md`.

A dedicated research chat should normally load **this file and SYNTHESIS together**.

## Update rule

For each research question:

1. search exact and neighboring terminology;
2. prefer recent primary work plus canonical precedent;
3. record effect direction, conditions, and failure modes;
4. distinguish demonstrated results from author interpretation;
5. update the current frontier rather than accumulating redundant summaries;
6. keep a short change log when the literature changes materially.

The target is not “all papers.” It is the **best current map of what is known, what is uncertain, and what remains open**.

## Current research question

> What mechanisms have the strongest evidence for **recombining learned operations into genuinely new OOD compositions**, while avoiding destructive retraining?

## Current frontier

### F1. Pattern matching alone is structurally limited for compositional OOD generalization

Recent work formalizes a **coverage** problem: if a model solves composition mainly by matching training fragments, generalization remains bounded by which fragments and contexts were covered during training.

In controlled two-hop tasks, required training coverage can grow rapidly with vocabulary size, and simply scaling model size does not automatically fix data efficiency. Path ambiguity is especially damaging because multiple computational routes can induce context-dependent internal representations.

**Current status:** strong evidence that better architecture/training mechanisms are needed when test-time composition goes beyond recombining already-covered fragments.

### F2. Meta-learning can produce systematicity in narrow controlled task families, but the scope of “human-like” claims is disputed

Meta-Learning for Compositionality (MLC) showed that a standard neural network trained across a stream of related compositional tasks can match human patterns on controlled instruction-learning tasks and improve several compositional benchmarks.

Follow-on criticism argues that this success depends on a restricted meta-learning setup and should not be generalized into a claim that neural networks now possess unrestricted human-like systematic compositionality.

**Current status:** meta-training explicitly for composition works in some controlled settings; general human-like systematicity remains unresolved.

### F3. Modularity is useful only when useful specialization is actually learned

The literature increasingly separates **structural modularity** from **functional specialization**.

Simply dividing a network into modules does not guarantee that different modules learn different reusable computations. Controlled theory/experiments show that specialization depends on the data structure, optimization dynamics, resource constraints, and inductive biases.

Work on discovering modular solutions further shows that compositional generalization depends on identifying the latent reusable components, not merely having more isolated parameter blocks.

**Current status:** “make it modular” is not a mechanism by itself. The important problem is **how reusable computations become identifiable and specialized**.

### F4. Routing/sequencing is emerging as a first-class bottleneck

Several independent approaches improve compositional generalization by explicitly learning **which computation should act on which state, and in what order**.

Examples include:

- modular routing over blocks of activation;
- learnable allocation of latent skills/modules to tasks;
- task/context inference that selects reusable computations;
- low-rank recurrent components composed according to inferred context.

These systems often outperform fully shared, task-specific, or ordinary mixture-of-experts baselines on their respective controlled tasks.

**Current status:** there is converging evidence that routing is not incidental plumbing; it is part of the compositional reasoning problem.

### F5. Reusable computation can emerge as learned neural dynamics

Multitask recurrent networks can spontaneously develop recurring **dynamical motifs** implementing reusable computations such as memory, rotations, and decision structures. Lesion studies show that some motifs have localized causal roles and can be reused across tasks.

Very recent predictive-learning work reports that recurrent networks trained only to predict future sensory input can develop modular clusters corresponding to independent latent dynamics and recombine those clusters in unseen combinations.

**Current status:** reusable computation does not need to be symbolic or hand-authored. Learned neural dynamics can become modular under the right training conditions.

### F6. Separating “what computation?” from “how to execute it” has direct empirical support

Two recent lines are especially relevant:

- probabilistic task inference represents a new task as a structured combination of previously learned computations and can infer solutions from very few examples, sometimes without parameter updates;
- a two-system architecture separates context/task inference (“what”) from reusable recurrent computation (“how”), enabling continual learning and compositional reuse of low-rank recurrent components in controlled task families.

**Current status:** strong controlled evidence that **task inference and execution can be usefully separated**. Generality to open-ended cognition is unproven.

### F7. Variable binding can be learned as an internal routing/memory mechanism

In controlled symbolic-program tasks, Transformers can learn a systematic variable-dereferencing procedure rather than only memorizing surface patterns.

Mechanistic analysis shows specialized attention heads routing information through the residual stream as an addressable memory, supporting multi-step binding chains.

**Current status:** variable binding need not always be hard-coded, but the evidence is currently from tightly controlled symbolic tasks.

### F8. Recurrent/iterative execution helps OOD only when paired with stronger constraints

Recent latent-reasoning work combines:

- input-adaptive recurrence;
- algorithmic supervision;
- anchored/discrete latent representations;
- explicit error correction.

Together these mechanisms improve OOD algorithmic generalization on controlled computational-graph tasks.

This is consistent with a wider neural-algorithmic-reasoning literature in which algorithmic alignment, structured intermediate states, and iterative processors support size/depth extrapolation.

**Current status:** recurrence alone is not the result. **Structured recurrence plus supervision/representation constraints** is the stronger pattern.

### F9. Training distribution matters as much as architecture

Across several papers, compositional generalization improves when training exposes the learner to:

- varied compositions of shared primitives;
- curricula/meta-training over changing task grammars;
- compound traces containing reusable operations;
- structurally diverse problem instances;
- explicit held-out recombinations.

Recent work also suggests that training only isolated primitives can be worse than training compound examples from which reusable pieces can be discovered.

**Current status:** a model cannot be judged “compositional” from architecture alone. The training distribution must make reusable structure identifiable.

### F10. No current mechanism solves open-ended compositionality

Nearly all positive results use controlled domains where:

- primitive operations recur across tasks;
- task boundaries or latent factors are relatively clean;
- compositional structure exists by construction;
- OOD splits are deliberately designed;
- the number and complexity of primitives are far below open-ended conversation and reasoning.

**Current status:** the literature now contains several credible mechanisms for pieces of compositional reuse, but no demonstrated general-purpose solution.

## Cross-paper convergence

The strongest common pattern across otherwise different research programs is:

```text
learn/discover reusable operations
        +
maintain explicit or stable bindings/state
        +
infer what operation is relevant
        +
route/sequence operations over state
        +
train on distributions that force reuse
        +
evaluate on genuinely unseen compositions/depths
```

This is a description of the **research frontier**, not a claim that this combination is sufficient.

## Known failure modes

1. **High IID / low OOD:** models fit the training composition while failing on longer or novel compositions.
2. **Modules without specialization:** structural separation does not guarantee functional decomposition.
3. **Coverage dependence:** apparent composition can collapse when required fragments or contexts were absent from training.
4. **Path ambiguity:** multiple computational paths can destabilize reusable internal state.
5. **Global retraining:** broad fine-tuning can improve a new task while destroying prior skills.
6. **Benchmark overclaiming:** success on restricted grammars/tasks is sometimes described more broadly than the evidence warrants.
7. **Routing failure:** reusable components may exist but remain inaccessible if selection/sequencing does not generalize.
8. **Topology/depth shift:** a mechanism that handles new combinations may still fail when problem size or reasoning depth grows.

## Current open research questions

1. Can reusable operations be **discovered automatically** without a known task vocabulary?
2. What learning signal causes useful functional specialization instead of arbitrary module partitioning?
3. What is the best representation for persistent variable/entity binding across operator sequences?
4. Can a router learn novel **sequences**, not only select familiar modules?
5. How should new operations be added without globally rewriting old ones?
6. Which mechanisms extrapolate simultaneously across **composition, depth, and size**?
7. Can predictive/self-supervised objectives induce reusable causal operators in more general environments?
8. How much explicit structure is necessary before the system becomes a disguised hand-built program?
9. Can all of this remain computationally cheaper than a large monolithic model?

## Key current references

1. Brenden M. Lake, Marco Baroni (2023), *Nature*: **Human-like systematic generalization through a meta-learning neural network**  
   DOI: 10.1038/s41586-023-06668-3

2. Tim Nelson Woydt et al. (2025), arXiv: **Fodor and Pylyshyn's Legacy — Still No Human-like Systematic Compositionality in Neural Networks**  
   arXiv: 2506.01820

3. Hoyeon/Hao-Hsiang Chang et al. (2025), arXiv: **The Coverage Principle / Characterizing Pattern Matching and Its Limits on Compositional Task Structures**  
   arXiv: 2505.20278

4. Devon Jarvis, Richard Klein, Benjamin Rosman, Andrew M. Saxe (2024), arXiv: **On The Specialization of Neural Modules**  
   arXiv: 2409.14981

5. Gabriel Béna, Dan F. M. Goodman (2025), *Nature Communications*: **Dynamics of specialization in neural modules under resource constraints**  
   DOI: 10.1038/s41467-024-55188-9

6. Simon Schug et al. (2023), arXiv: **Discovering modular solutions that generalize compositionally**  
   arXiv: 2312.15001

7. Florian Dietz, Dietrich Klakow (2024), arXiv: **Block-Operations: Using Modular Routing to Improve Compositional Generalization**  
   arXiv: 2408.00508

8. Edoardo Maria Ponti et al. (2023), EACL: **Combining Parameter-efficient Modules for Task-level Generalisation**  
   DOI: 10.18653/v1/2023.eacl-main.49

9. Laura N. Driscoll, Krishna V. Shenoy, David Sussillo (2024), *Nature Neuroscience*: **Flexible multitask computation in recurrent networks utilizes shared dynamical motifs**

10. Gauthier Boeshertz, Claudia Clopath (2025 preprint): **Predictive learning enables compositional representations**  
    DOI: 10.1101/2025.09.26.678731

11. Haozhe Shan, Minni Sun, Lea Duncker (2025), arXiv: **Separating the what and how of compositional computation to enable reuse and continual learning**  
    arXiv: 2510.20709

12. Jacob J. W. Bakermans et al. (2025), arXiv: **Compositional meta-learning through probabilistic task inference**  
    arXiv: 2510.01858

13. Yiwei Wu, Atticus Geiger, Raphaël Millière (2025), arXiv: **How Do Transformers Learn Variable Binding in Symbolic Programs?**  
    arXiv: 2505.20896

14. Awni Altabaa et al. (2025), arXiv: **Unlocking Out-of-Distribution Generalization in Transformers via Recursive Latent Space Reasoning**  
    arXiv: 2510.14095

15. Thaddäus Wiedemer et al. (2023), NeurIPS/arXiv: **Compositional Generalization from First Principles**  
    arXiv: 2307.05596

16. Lingjing Kong et al. (2026), arXiv: **From Reasoning Traces to Reusable Modules: Understanding Compositional Generalization in Language Model Reasoning**  
    arXiv: 2606.18089

17. Devon Jarvis et al. (2026), *PNAS*: **Compositionality and systematicity emerge from iterated learning in deep linear networks**  
    DOI: 10.1073/pnas.2509739123

## Search vocabulary

- systematic compositional generalization
- coverage principle
- shared-operator generalization
- modular routing
- module specialization
- modular meta-learning
- compositional meta-learning
- neural algorithmic reasoning
- processor transfer
- dynamical motifs
- variable binding
- addressable neural memory
- role-filler representation
- task inference
- program induction
- independent mechanisms
- predictive compositional representation
- recurrent / recursive latent reasoning
- continual compositional learning

## Change log

### 2026-09-29 — research phase 1: compositional OOD frontier

Expanded the initial map into a mechanism-level frontier using Consensus, Scite citation/context search, and current arXiv/web search.

Material changes:

- routing/sequencing promoted from a sub-detail to a first-class research variable;
- variable binding added as a distinct mechanism, not just a representation keyword;
- training-distribution/coverage constraints promoted to equal importance with architecture;
- modularity narrowed: structural modules alone are insufficient without learned specialization;
- recurrence narrowed: strongest evidence is for structured/anchored iterative execution, not recurrence by itself;
- MLC-style “human-like” systematicity explicitly marked as contested rather than settled;
- predictive learning added as an emerging route for spontaneously discovering reusable dynamics.

The current frontier is now mature enough for a separate synthesis pass.

## Developmental self-construction research refresh — 2026-09-29

New research question:

> What mechanisms let a small system progressively author reusable computation without blind whole-program search, catastrophic drift, or a pretrained LLM inside the agent?

### F18. Empirical self-modification works better with an archive than latest-only hill climbing

Darwin Gödel Machine (Zhang et al., 2025; revised 2026, arXiv:2505.22954) iteratively modifies an agent's own code, evaluates descendants empirically, and keeps an archive of prior agents as stepping stones. Its reported coding-agent performance rose from 20.0% to 50.0% on SWE-bench and 14.2% to 30.7% on Polyglot; ablations in the paper support both self-modification and open-ended archive exploration as contributors.

Limitation for this project: DGM uses frozen pretrained foundation models to propose code changes. The relevant transferable mechanism is the archive + empirical validation loop, not the pretrained model.

### F19. Evaluator-guided code evolution can discover nontrivial algorithms

AlphaEvolve (Novikov et al., 2025, arXiv:2506.13131) evolves executable code against automated evaluators and reports discoveries/optimizations in mathematics and computing. This supports treating executable programs plus objective evaluators as a viable search substrate.

Limitation for this project: AlphaEvolve also uses large pretrained language models as mutation generators.

### F20. Library learning provides a concrete route from solved programs to new reusable primitives

DreamCoder (Ellis et al., 2021, DOI: 10.1145/3453483.3454080) alternates program synthesis with library learning, progressively extracting reusable abstractions that make later synthesis faster and deeper.

This is directly relevant to a self-authoring computational genome: repeated solved structures can become new first-class operations rather than remaining long instruction sequences.

### F21. Purely syntactic abstraction mining is brittle; equivalence-aware library learning is materially stronger

Babble (Cao et al., 2023, DOI: 10.1145/3571207) uses e-graphs, equality saturation and anti-unification to learn abstractions modulo equational theories. Its reported evaluations show better compression than DreamCoder on tested domains and substantially faster library learning.

Stitch / Top-Down Synthesis for Library Learning (Bowers et al., 2023, DOI: 10.1145/3571234) provides another efficient compression-oriented library-learning route with strong guarantees for its single-abstraction search.

Implication from the external evidence only: retaining alternative equivalent programs or equivalence classes is important when useful abstractions can be hidden by superficial syntactic variation.

### F22. Retrospective compression is not identical to future usefulness

Prospective Compression in Human Abstraction Learning (Cano et al., 2026, arXiv:2605.09985) explicitly studies online library learning under non-stationary future task demands and contrasts retrospective compression of past programs with prospective abstraction selection.

This supports treating frequency/compression as one proposal signal rather than the sole criterion for whether a new primitive should exist.

### F23. Greedy continual skill acquisition has a known long-horizon failure mode

PowerPlay (Schmidhuber, 2013, DOI: 10.3389/fpsyg.2013.00313) proposed continually extending a solver with new skills or cheaper solutions while preserving previous skills. The paper also identifies a drawback directly relevant here: greedy preference for the simplest next improvement can sacrifice larger long-term gains.

This is a reason to preserve diverse stepping stones and occasionally test high-upside changes rather than only accepting the easiest local improvement.

### F24. Modularity helps continual learning, but module selection and overlap remain separate problems

Continual-learning work on local module composition and sparse/modular architectures supports isolating updates and recombining reusable components, while also showing that modularity alone does not remove routing, overlap, or specialization problems.

External-science summary for the developmental track:

```text
empirical evaluator
+ archive of diverse descendants
+ program/library learning
+ equivalence-aware abstraction
+ prospective as well as retrospective utility
+ continual causal re-evaluation
```

is better supported than blind whole-program mutation or single-lineage hill climbing.

## Dormant-capability addressing research refresh — 2026-09-29

Research question:

> Can total stored capability grow much faster than active retrieval work and RAM residency?

### F25. Hierarchical navigable search can make lookup grow much slower than corpus size

Malkov & Yashunin's HNSW (IEEE TPAMI 2020, DOI: 10.1109/TPAMI.2018.2889473) uses a hierarchical proximity graph and reports logarithmic search-complexity scaling in its setting while preserving high approximate-nearest-neighbor quality.

This supports a general architectural principle relevant here: a large cold capability store need not be globally scanned if it has a navigable hierarchical address structure.

### F26. SSD-resident vector indices demonstrate that large stores can stay mostly cold

DiskANN (Subramanya et al., NeurIPS 2019) demonstrated billion-point nearest-neighbor search on a single machine with SSD-backed index/data and bounded RAM.

SPANN (Chen et al., NeurIPS 2021, arXiv:2111.08566) uses a memory/disk hybrid: centroid/navigation information stays resident while large posting lists live on disk, with query-aware pruning of unnecessary disk accesses.

Starling (ACM SIGMOD/PACMMOD 2024, DOI: 10.1145/3639269) likewise optimizes disk-resident graph layout and block search to reduce I/O.

The externally supported conclusion is not that one specific ANN system should become our cognition architecture. It is that:
- large addressable stores can be mostly disk-resident;
- a small hot navigation structure can locate cold entries;
- query cost can depend much more on local search difficulty than on total stored bytes.

### F27. Sparse expert models validate capacity/active-compute decoupling but routing remains a failure point

Sparse mixture-of-experts work, including Expert Choice Routing (Zhou et al., NeurIPS 2022, arXiv:2202.09368), shows that total parameter capacity can grow without activating all parameters per input.

However, routing quality, load balance, redundancy and specialization remain separate constraints. This supports sparse activation as a capacity mechanism but does not solve how a general agent should construct the right address.

### F28. Program synthesis suggests functional/behavioral addresses rather than human labels

BUSTLE (Odena et al., ICLR 2021) guides bottom-up program search using semantic information from executing intermediate programs, including property signatures derived from behavior.

Neural-Guided Deductive Search (Kalyan et al., ICLR 2018, arXiv:1804.01186) similarly uses current synthesis state/specification to prioritize branches while retaining deductive correctness.

Neural Program Synthesis with Query (Huang et al., 2022, arXiv:2205.07857) explicitly identifies hand-designed input/output examples as privileged information and learns informative probes in a functional space.

Provisional external-science implication:

> For reusable computation, an address can be based on **what a component does under informative probes**, and the system can potentially learn which probes make components distinguishable.

This is closer to goal/effect-conditioned retrieval than static semantic similarity.

## Goal-conditioned consequence research refresh — 2026-09-29

Research question:

> If an operation can look locally useful but destroy future solvability, what established mechanisms represent downstream consequence rather than immediate similarity/progress?

### F29. Goal-conditioned value functions explicitly represent long-horizon usefulness relative to a goal

Universal Value Function Approximators (Schaul et al., ICML 2015) extend value functions from V(s) to V(s,g), allowing one learned estimator to generalize over both states and goals.

This is directly relevant to selecting computation by expected future usefulness rather than immediate state-distance reduction.

### F30. Successor features separate dynamics/consequences from changing objectives

Successor Features (Barreto et al., NeurIPS 2017; extended ICML 2018) factor expected future feature occupancy from task reward and combine reusable policies through generalized policy improvement.

The relevant transferable idea is not an RL-specific commitment. It is the separation:

```text
what future states/features this computation tends to enable
                    ×
what the current goal values
```

instead of scoring an operation only by immediate effect.

### F31. Long-horizon goal-conditioned systems often need explicit planning structure

Successor Feature Landmarks and related goal-conditioned planning work combine learned future representations with higher-level graph/planning structures for long-horizon tasks.

External evidence therefore supports treating downstream reachability as a distinct mechanism rather than assuming one-step similarity or one-step causal improvement will compose automatically.

## Adaptive reasoning and reachability-geometry refresh — 2026-09-29

### F32. Goal-reaching value has exploitable directed-distance structure

Quasimetric RL (Wang et al., ICML 2023) models optimal goal-reaching value with quasimetric geometry rather than a generic unconstrained scalar value function.

TLDR (Bae et al., CoRL 2024/2025) learns temporal-distance-aware representations and uses temporal distance both for exploration and goal reaching.

Multistep quasimetric work at ICLR 2026 further reports that temporal-distance/quasimetric representations can support long-horizon behavior stitching.

External implication: long-horizon consequence can be represented as structured directed distance, but successful methods typically require objectives/curricula designed around temporal structure rather than generic regression.

### F33. Adaptive computation is an established route to reasoning efficiency

Adaptive Computation Time (Graves, 2016, arXiv:1603.08983) lets recurrent networks learn how many computation steps to spend and showed strong gains on several algorithmic tasks, while not universally improving language modeling.

Rational metareasoning treats computation itself as a costly action whose value is the expected improvement in external decision quality minus computation cost.

Callaway et al. (UAI 2018) learn approximate computation-selection policies, and Chen et al. (2026 preprint, DOI: 10.64898/2026.04.14.718499) combine rational metareasoning with recurrent meta-learning so a network learns to select costly mental computations.

The externally supported principle is:

> computation should be allocated according to expected value, not fixed depth.

This does not imply that existing metareasoning algorithms directly solve open-ended AI reasoning.

## Active falsification / reliable compilation refresh — 2026-09-29

Research question:

> How should a self-constructing agent decide that a newly synthesized procedure is specified well enough to become durable code?

### F34. Counterexample-guided synthesis turns failed verification into better specifications

Solar-Lezama's CEGIS formulation (Program Synthesis by Sketching, 2008; later Program Sketching, DOI: 10.1007/s10009-012-0249-7) alternates:
1. synthesize a candidate from the examples/counterexamples known so far;
2. attempt to falsify the candidate with a validator;
3. add a discovered counterexample to the specification;
4. resynthesize.

The important mechanism is that a failed candidate does not merely die: its counterexample removes an entire family of similarly wrong candidates.

### F35. Active synthesis can ask the question that most reduces program ambiguity

Neural Program Synthesis with Query (Huang et al., 2022, arXiv:2205.07857) treats fixed, hand-designed input/output examples as privileged information and learns to generate informative queries.

Barnaby et al. (2025), Active Learning for Neurosymbolic Program Synthesis, DOI: 10.1145/3763102, repeatedly refines a hypothesis space with targeted questions and terminates when the surviving programs are observationally indistinguishable. The reported system identifies the ground-truth program on 98% of its evaluated benchmarks with fewer than five interaction rounds on average, while earlier active-learning techniques reached at most 65% in that neurosymbolic setting.

External-science implication:

> A developing system should not equate “fits current evidence” with “safe to compile.” It can actively search for a discriminating observation and spend additional evidence only when multiple behaviorally distinct hypotheses remain.

This connects naturally to library learning: synthesis proposes reusable computation; active falsification determines whether it is sufficiently identified to enter the durable library.

## Novel reasoning + pointer language refresh — 2026-09-29

### F36. Learned guidance is strongest when paired with explicit search rather than greedy commitment

ExeDec (Shi et al., ICLR 2024; arXiv:2307.13883) predicts execution subgoals and repeatedly synthesizes/executes partial programs. It reports substantially improved compositional generalization over direct synthesis baselines.

DeepCubeAI (Agostinelli & Soltani, RLC 2024) combines a learned discrete world model and learned goal-conditioned heuristic with explicit heuristic search; the authors report >99% solve rates across their evaluated planning domains and large gains over greedy policies.

External implication:

> a learned model can be a proposal/priority mechanism while explicit search preserves multiple future possibilities. Greedy next-step control is not the only or generally strongest way to use a learned heuristic.

### F37. Pointer/copy mechanisms decouple linguistic structure from rare or unseen lexical content

Pointer Sentinel Mixture Models (Merity et al., ICLR 2017; arXiv:1609.07843) lets a recurrent language model either generate from its vocabulary or copy from context, improving rare/unseen-word handling while using fewer parameters than large-softmax baselines in its setting.

Later external-memory language work, including Neurocache (Safaya & Yuret, NAACL 2024), similarly separates a compact active language model from a larger external store/cache.

External implication:

> exact lexical content does not necessarily have to be memorized inside the hot language generator; a small learned generator can learn linguistic scaffolding while exact entities/content remain externally addressable.

### F38. Structured span parsing is materially stronger than flat token tagging when compositional structure matters

Herzig & Berant (ACL 2021, DOI: 10.18653/v1/2021.acl-long.74) report that a span-tree semantic parser improves average accuracy from 61.0 to 88.9 versus seq2seq baselines on their compositional-generalization splits while remaining comparable on random splits.

Zhang, Strubell & Hovy (SPNLP 2021, DOI: 10.18653/v1/2021.spnlp-1.8) find structured span decoding consistently outperforms BIO tagging when using static word-type representations across their semantic-role-labeling experiments.

External implication for a from-scratch low-resource parser:

> role/value binding should probably be represented as structured spans/composition rather than independent per-byte labels or unconstrained independent boundaries.

## Lexical acquisition / semantic bootstrapping refresh — 2026-09-29

Research question:

> When a from-scratch agent encounters a genuinely new word or construction, what evidence supports acquiring its meaning without globally retraining the language system?

### F39. Fast mapping can emerge when new lexical bindings use prior conceptual structure plus external/episodic memory

Hill et al. (2020), *Grounded Language Learning Fast and Slow* (arXiv:2009.01719), show one-shot novel word-object binding in an embodied agent using a dual-coding external memory. The new word can immediately participate in later instructions while long-term lexical and motor knowledge remains stable.

The transferable mechanism is the separation between:
- fast episodic binding of a new surface form to an existing concept/referent;
- slower long-term representation learning.

### F40. Cross-situational evidence can identify lexical meaning from ambiguous repeated contexts

Vong & Lake (2021/2022), *Cross-Situational Word Learning With Multimodal Neural Networks*, show that generic multimodal neural systems can learn word-referent mappings by accumulating co-occurrence evidence across ambiguous situations, though some human-like biases such as mutual exclusivity are not automatic.

Human and computational CSWL work therefore supports treating lexical meaning as an evidence-accumulation problem rather than a property that must already exist in a sentence encoder.

### F41. Structured semantic bootstrapping can jointly accelerate word and syntax learning

Abend et al. (2017), *Bootstrapping language acquisition*, model language acquisition from sentences paired with structured but noisy meaning representations. Their incremental Bayesian learner jointly learns lexical mappings and grammar, exhibiting syntactic bootstrapping and one-shot lexical learning phenomena.

External implication:

> known constructions can constrain the possible meaning of a novel word, while newly grounded words can in turn support learning new constructions.

### F42. Construction grammars are computationally learnable as schematic, partially filled patterns

Dunn (2016; extended computational treatment in 2024) presents corpus-driven construction-grammar induction in which learned constructions may mix fixed items with open slots, recur, and organize into a network.

This supports a possible language representation compatible with the project's sparse cold-store architecture: many learned constructions can remain dormant while only locally matching constructions activate for an utterance.

### F43. Hierarchical / symbolic scaffolding has repeatedly improved systematic language generalization in controlled settings

SpanBasedSP (Herzig & Berant, ACL 2021) explicitly composes semantic programs over spans and reports a large compositional-generalization advantage over seq2seq baselines on targeted splits.

Neural-Symbolic Stack Machine (Chen et al., 2020) and related recursive neural-symbolic work likewise report strong systematic generalization when learned perception/control is coupled to explicit compositional execution.

These results do not prove that one grammar formalism is best for open-domain language, but they support testing explicit reusable constructions rather than only increasing sequential encoder capacity.

## Large rule / construction matching refresh — 2026-09-29

### F44. Large learned rule systems have a classic utility problem

Forgy's Rete algorithm (1982) addresses the many-pattern/many-object matching problem by compiling shared conditions into a discrimination network rather than repeatedly scanning every rule.

Doorenbos (1995), *Production Matching for Large Learning Systems*, explicitly studies systems that learn 100,000+ rules and identifies linear growth in match cost as a utility problem; Rete/UL is designed to reduce or eliminate that scaling failure over broader production-system classes.

### F45. Constructional language processing faces the same combinatorial search problem

Van Eecke, Nevens & Beuls (2022), *Neural heuristics for scaling constructional language processing*, frame construction processing as a combinatorial search problem that becomes intractable as grammars grow and report substantial search-space/time reductions from learned heuristics.

Computational Construction Grammar work also represents constructions as networks rather than an unstructured global list.

External implication:

> A growing learned grammar needs compiled discrimination/index structure and/or learned search guidance; merely learning more constructions is not scalable if every utterance scans the whole grammar.

## Execution-grounded language acquisition refresh — 2026-09-29

### F46. Semantic parsers can be learned from execution outcomes rather than fully labeled programs

Liang et al. (2017), *Neural Symbolic Machines: Learning Semantic Parsers on Freebase with Weak Supervision*, combines a learned language-to-program proposer, explicit program execution, search-space pruning, and answer-level reward. The parser is trained from question/answer pairs rather than gold programs.

Transferable mechanism for this project:

> successful executable traces can serve as latent semantic explanations for language when only outcome-level supervision is available.

### F47. Joint syntax/semantics induction is stronger than treating them as independent learning problems

Portelance, Reddy & O'Donnell (2025), *Reframing linguistic bootstrapping as joint inference using visually-grounded grammar induction models*, reports stronger grammar induction, lexical category learning and novel sentence/verb interpretation when syntax and semantics are learned jointly from grounded evidence.

Abend et al. (2017), *Bootstrapping language acquisition*, likewise shows incremental joint learning of lexicon and grammar from utterance-level structured meanings, including syntactic bootstrapping and one-shot lexical effects.

### F48. Explicit latent compositional structure remains useful under weak/broad supervision

Work on span-aligned and latent-tree semantic parsing reports improved compositional generalization when input spans are explicitly tied to output subprograms/modules rather than represented only by a monolithic sequence state.

External-science implication:

```text
utterance
+ grounded context / outcome
+ candidate executable computations
→ infer a successful latent program
→ align language fragments to program fragments
→ compile reusable constructions
```

This is a plausible route for broadening the project's construction grammar without requiring hand-authored semantic labels for every utterance.

## Constraint reasoning / information-gain refresh — 2026-09-29

### F49. Constraint reasoning benefits from maintaining an explicit hypothesis space

Logic-puzzle systems commonly separate natural-language interpretation from a formal constraint model, then solve by exact logical/constraint inference rather than free-form generation.

### F50. The best observation/action can be selected by how strongly it distinguishes surviving hypotheses

Recent active-learning and program-synthesis work selects queries to maximize pruning power over a current hypothesis/program space. This is the same structural principle already used successfully by Active Execution-Grounded Language v1.

Project implication:

```text
language
→ explicit candidate worlds
→ hard constraints
→ possible observations per action
→ choose action minimizing worst-case surviving worlds / maximizing information
→ observe
→ solve remaining world
```

This is a stronger target for the boxes benchmark than encoding the folklore rule `draw from MIXED`.

## Dialogue-state / response-planning refresh — 2026-09-29

Research question:

> Once objective language-to-execution tasks are handled, what representation best supports topic switching, reference, role/persona state, open-ended analysis, and coherent response generation without collapsing everything into one dense language model?

### F51. Dialogue systems benefit from separating semantic interpretation, dialogue state, policy/planning, and surface generation

Frame-based dialogue architectures maintain an explicit task/dialogue state between language understanding and response policy/generation. This separation makes reference, slot values, uncertainty and next-action selection inspectable rather than forcing all state into the generator.

RavenClaw similarly separates domain-specific dialogue plans from domain-independent conversational control and explicitly treats discourse history and current task state as inputs to next-action selection.

### F52. Dialogue state can be represented as executable/dataflow structure with explicit reference and revision

*Task-Oriented Dialogue as Dataflow Synthesis* represents dialogue state as a graph extended by programs each turn; metacomputation operators explicitly reuse, revise and refer to prior fragments. This improves representability of complex multi-turn intents and makes reference/revision first-class operations.

### F53. Open-domain and task-oriented dialogue remain meaningfully different regimes

Research integrating task-oriented and open-domain dialogue treats them as distinct but interleavable modes rather than assuming one task representation is sufficient for both.

### F54. Response planning is a separate generalization problem

Dialogue-generation work on sentence planning and discourse structuring shows that selecting propositions and discourse relations is itself a capability distinct from lexical surface realization.

External-science implication:

```text
utterance
→ semantic/dialogue frame
→ explicit discourse + thread state
→ response plan / dialogue act
→ retrieve relevant knowledge/capabilities
→ surface realization
```

is a better-supported next architecture target than expanding the current fixed response scaffolds or forcing all open-ended behavior through executable task programs.

## Clarification / epistemic uncertainty refresh — 2026-09-29

### F55. Clarification is an active uncertainty-reduction action

Recent clarification-question research treats ambiguity and under-specification as uncertainty states and reports improved task success when systems explicitly use uncertainty to decide when to ask rather than always proceeding.

### F56. Evidence insufficiency should be a first-class epistemic state

Recent verification/calibration work separates supported, contradicted and unknown/insufficient-evidence states, with abstention or targeted retrieval when evidence is inadequate instead of forcing a binary answer.

External implication:

```text
underdetermined discourse/evidence state
→ identify missing variable/evidence
→ ask / retrieve / abstain
→ update state
→ answer only after support is sufficient
```

is a reusable control principle across reference resolution and factual assertion.

## Externalized knowledge / content-planning refresh — 2026-09-29

### F57. Factual knowledge can be deliberately externalized from language-model parameters

Limited Memory Language Models (Zhao et al., ICLR 2026) explicitly externalize factual knowledge into an editable database during pretraining, masking retrieved factual values from the training loss so the model learns targeted lookups rather than relying on parametric memorization.

Continuous-query LMLM work extends the idea toward flexible queries over textual knowledge values.

External implication:

> fluency/structure and factual storage do not have to scale together inside one hot parameter set.

### F58. Causal deletion is a stronger test of externalized knowledge than retrieval accuracy

Recent LMLM auditing work varies database state while holding the model fixed to separate parametric leakage from retrieval-mediated correctness. This motivates deletion/intervention tests for our own external-memory architecture.

Project-relevant criterion:

> if a required fact is removed from cold memory, a properly externalized system should lose/abstain on that claim rather than regenerate the deleted value from hot parameters.

### F59. Content planning and surface realization are separable generation problems

Data-to-text work with macro planning explicitly selects and orders important entities/events before text generation, improving content organization and factual precision over less structured generation baselines.

Copy-oriented data-to-text methods likewise support direct insertion of exact structured values during realization, particularly for rare or unseen entities.

External implication:

```text
retrieved evidence
→ content selection / ordering
→ explicit macro plan
→ surface realization with copying
```

is a well-supported architecture pattern for evidence-grounded generation.
