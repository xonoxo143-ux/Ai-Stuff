# Agent Model Research

This directory contains the from-scratch learned-model experiments for the
homegrown worker agent.

## Current status

The original sparse ecology and BytePatchHybrid V0 remain historical evidence.
The corrected GRU/patch language hybrid is no longer the mainline architecture:
it lost to the parameter-matched causal byte Transformer under a
compute-normalized T4 comparison.

The Transformer is now the performance baseline/control, not the intended final
architecture.

The active challenger is DeltaHybrid V1:
- raw-byte input for the first controlled comparison;
- Gated-Delta-style persistent/state-heavy blocks;
- occasional exact-attention blocks;
- parameter scale matched to the ~1.05M Transformer baseline;
- streaming state preserved as a first-class runtime property.

See DELTA_HYBRID_V1.md.
## Compute policy

Substantive model computation runs on Kaggle.

- Kaggle CPU: reference implementations, correctness, equivalence, gradient and
  long-context CPU probes.
- Kaggle 2×T4: training, architecture races, throughput and equal-compute gates.
- Optiplex: storage/control/scheduling only.
- Phone: optional interface/target; not a compute or continuity dependency.

Historical phone and Android experiments remain valid measurements of those
older artifacts, but they do not define the present research workflow.

## Scientific rule

A new architecture must earn promotion under controlled comparisons.

At minimum:
1. correctness/invariant gates;
2. same-data/step comparison;
3. compute-normalized comparison;
4. state/long-context tests where applicable;
5. deployment-state/memory accounting.

Do not scale an architecture merely because it is novel or elegant.
