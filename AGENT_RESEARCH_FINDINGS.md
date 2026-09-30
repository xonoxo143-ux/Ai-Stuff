# AGENT_RESEARCH_FINDINGS

Updated: 2026-09-29

This file contains external evidence, mechanisms, limitations, contradictions, failure modes, and closure records only.

## Closure record — external knowledge vs parametric factual storage
**Status:** provisionally settled.

**Supported conclusion:** broad factual competence does not require all facts to be stored in model parameters. Retrieval-augmented language models demonstrate that external addressable knowledge can materially improve factual/open-domain performance and can substitute for part of parametric factual storage.

**Evidence strength:** strong at medium/large model scales; weaker at the tiny homegrown scale targeted here.

**Scope/limitations:** retrieval does not remove the need for learned language, query/relevance machinery, evidence integration, and rejection of irrelevant/conflicting evidence. Retrieval failures can induce errors.

**Unresolved edge case:** whether the same parameter-efficiency benefit remains large for a very small generator trained entirely from scratch.

**Would overturn/reopen:** controlled small-model evidence showing retrieval consistently harms whole-agent quality/cost even with learned relevance filtering, or that comparable factual breadth is cheaper to internalize parametrically at our target scale.

## 2026-09-29 — Narrow question: minimum viable language substrate

### Token-free input/output
- ByT5 shows standard Transformers can operate directly on bytes and be competitive with token-level counterparts, with better noise robustness and spelling/pronunciation-sensitive behavior. Limitation: byte sequences are longer and efficiency is substantially worse in straightforward implementations.
- CANINE shows tokenization-free character encoders can be competitive and efficient when local composition plus downsampling compresses the fine-grained sequence. Ablations report quality degradation when the local encoder is removed or downsampling becomes too aggressive.
- MEGABYTE uses local/global multiscale byte patches; published results establish that tokenization-free autoregressive modeling can be competitive while reducing the cost of long byte sequences.
- Byte Latent Transformer (ACL 2025) provides FLOP-controlled evidence up to 8B parameters / 4T training bytes that dynamically patched byte models can match tokenized LMs at scale and improve inference efficiency/robustness.

### Recurrent / state-space language spines
- Mamba demonstrates selective SSM language models with linear sequence scaling, recurrent inference, and strong language-model performance; the original work reports a 3B Mamba outperforming same-size Transformers and matching Transformers about twice its size on the evaluated setup.
- A controlled NVIDIA study comparing 8B Transformer, Mamba, Mamba-2, and Mamba-2-Hybrid models on matched data found pure Mamba variants competitive on many tasks but weaker on strong copying, in-context learning, and long-context reasoning.
- In that controlled study, the Mamba-2-Hybrid (mostly Mamba-2 with a small fraction of self-attention layers) exceeded the matched Transformer across 12 standard tasks on average and was projected to retain major inference-speed advantages.
- RWKV provides an independent recurrent language-model path with constant-state recurrent inference and parallelizable training; later RWKV-X work adds sparse attention specifically to improve long-context retrieval, reinforcing the pattern that precise access and recurrent compression can be complementary.

### Contradictions / negative evidence
- Naive byte/character processing is not a free win: sequence expansion can make training and inference much slower than subword models.
- Pure recurrent/SSM compression is not a free replacement for attention: controlled evidence exposes deficits in copying and in-context retrieval-like behavior.
- Large-scale BLT evidence does not establish that dynamic byte patching is optimal at very small parameter/data budgets.
- Large-model architecture rankings may not transfer to our local, small-from-scratch regime.

## Closure record — fixed subword tokenization requirement
**Status:** provisionally settled.

**Supported conclusion:** a fixed learned subword vocabulary is not required for high-quality language modeling. Raw byte/character interfaces are viable, but successful systems generally amortize the longer sequence using local composition, downsampling, or patches.

**Evidence strength:** strong for feasibility; moderate for the best design at small scale.

**Scope/limitations:** this does not show that linguistic/token-like abstractions should disappear internally. It only removes fixed external tokenization as a requirement.

**Unresolved edge cases:** patching rule and granularity at small scale; whether learned dynamic patches repay their complexity versus simple byte-local compression.

**Would overturn/reopen:** robust compute-controlled evidence that token-free models are consistently dominated at our target scale and hardware even after multiscale compression.

## 2026-09-29 — Small-scale hybrid evidence

### Independent evidence
- Griffin/Hawk (De et al., 2024, arXiv:2402.19427) compare pure gated recurrence, recurrence + local attention, and Transformer baselines from roughly 100M parameters upward. Griffin's hybrid has lower reported validation loss than the matched MQA Transformer across compute budgets, while pure Hawk is competitive but weaker. This is evidence that hybrid gains are not only an 8B-scale effect.
- Zoology/MQAR (Arora et al., arXiv:2312.04927) shows efficient recurrent/convolutional models can have acceptable language-model loss while retaining serious associative-recall deficits. Attention is robust on multi-query associative recall; aggregate perplexity alone can hide retrieval weakness.
- Mechanistic associative-recall work (2024) finds Transformers and Based fully solve associative recall, Mamba comes close, and H3/Hyena fail; similar aggregate behavior can arise from materially different mechanisms.
- Taipan (2024, arXiv:2410.18572) independently combines Mamba-2 with budgeted selective attention specifically because pure SSMs are weaker on retrieval-heavy context. It demonstrates that precise access need not mean dense attention on every token.
- Nemotron-H (NVIDIA, 2025) corroborates the pattern at larger scale: most attention can be replaced by Mamba-2 while retaining a small attention fraction and competitive quality.

### Negative evidence / limitations
- The strongest Griffin small-scale points are still around 100M parameters, above the smallest local model we may want.
- Griffin's local attention does not guarantee precise access beyond its window; selective/sparse attention is an independent alternative.
- Real speed depends on kernels and hardware. A theoretically efficient recurrence can lose to a tiny Transformer on generic CPU implementations.
- Language loss alone is not an adequate architecture gate because recall failures can remain hidden.

## Closure record — pure recurrence/SSM vs hybrid precise-access spine
**Status:** provisionally settled at the architecture-family level.

**Supported conclusion:** for evidence-grounded conversation, a pure recurrent/SSM spine is not the best-supported default. Bounded recurrent state plus a limited precise-access mechanism is better supported. The attention path may be local, sparse, selective, or occasional; dense global attention everywhere is not established as necessary.

**Evidence strength:** moderate-to-strong at the family level; moderate around 100M parameters; weak below that and on our exact hardware.

**Scope/limitations:** this does not settle the recurrent cell, attention type/budget, layer ratio, patching rule, or tiny-scale crossover.

**Unresolved edge cases:** sub-100M crossover, selective vs fixed local attention, generic-CPU efficiency, and the effect of external retrieval on the optimal attention budget.

**Would overturn/reopen:** a matched tiny-model study where pure recurrence/SSM matches or beats hybrid models simultaneously on language loss, exact copying, retrieval with distractors, multi-turn retention, and target-hardware latency/RAM.
