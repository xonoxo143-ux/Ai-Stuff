# Agent v1 remote lab — Floot VM

**Date:** 2026-09-27  
**Status:** usable CPU experiment backend

## Observed environment

Through the connected Floot project VM:

```text
CPU cores: 4
RAM: ~8 GB
filesystem: ~7.8 GB total
Python: 3.11
architecture: aarch64
network access: available
```

The VM does not ship with pip or git.

A persistent working area was established at:

```text
/tmp/agent-v1-lab
```

Persistence was observed across separate tool calls, but GitHub remains canonical because VM lifetime is not treated as guaranteed durable storage.

## Python environment

Use a persistent user base:

```text
PYTHONUSERBASE=/tmp/agent-v1-lab/pyuser
```

PyTorch must come from the CPU-only index. Installing ordinary Linux aarch64 `torch` attempted to pull CUDA dependencies and exhausted disk.

Working stack:

```text
torch 2.14.0+cpu
numpy 2.4.6
pytest 9.1.1
```

## Source provenance

No git binary is available.

Experiments therefore download a GitHub source archive pinned to an exact commit SHA and extract it under:

```text
/tmp/agent-v1-lab/src/
```

Never run an experiment from an unpinned branch archive.

## Verified gate

Pinned commit:

```text
b48f14bbf7d61968d45f0d2b5457bb4135559317
```

passed:

```text
tests/test_v1_causal_isolation.py
2 passed
```

## Role

Use Floot for CPU training/diagnostic runs.

Use GitHub for:

- canonical code;
- accepted results;
- architecture documents;
- durable evidence.

Do not treat Floot temporary files as canonical project history.
