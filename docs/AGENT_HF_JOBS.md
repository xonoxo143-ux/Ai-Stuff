# Agent compute backend — Hugging Face Jobs

**Date:** 2026-09-27  
**Status:** project runner added; CPU smoke test is the first gate

## Purpose

GitHub remains the canonical source of code, architecture documents, and accepted evidence.

Hugging Face Jobs becomes the preferred remote compute backend for Agent experiments that are more naturally treated as training/benchmark jobs than CI.

The split is:

```text
GitHub
  source + commits + durable evidence

Hugging Face Jobs
  reproducible CPU/GPU experiment compute

ChatGPT
  experiment design + launch + later result interpretation
```

A job must always be pinned to an exact Git commit. Branch names are not sufficient experiment provenance.

## Runner

Project runner:

```text
agent-model/tools/hf_agent_job.py
```

The runner:

1. records the exact commit and command in the job log;
2. downloads a GitHub archive for that exact commit;
3. installs the CPU Agent test stack unless told not to;
4. runs from `agent-model/` with `PYTHONPATH` set correctly;
5. exits with the experiment command's return code;
6. can persist small result files into the job log as gzip+base64 records with SHA-256.

This avoids giving the compute job a GitHub write credential.

## Small-result persistence

HF Job files are ephemeral.

For current Agent experiments, JSON artifacts are small enough to persist through logs:

```text
AGENT_ARTIFACT_GZIP_BASE64 {...}
```

The record contains:

```text
path
original byte count
sha256
encoding = gzip+base64
data
```

After a job finishes, ChatGPT can read the logs, recover the exact JSON bytes, verify SHA-256, interpret the result, and commit the accepted result/documentation to GitHub.

Default log-artifact limit:

```text
2,000,000 bytes per requested artifact
```

Large model checkpoints or datasets must not be stuffed into logs. If Agent v1 reaches that point, add a dedicated Hub/S3 persistence path with a narrowly scoped write secret.

## Initial hardware policy

Start with CPU unless the workload demonstrates a reason for GPU.

Current official HF Jobs pricing should be checked before each hardware escalation. Every job must have a timeout.

Initial defaults:

```text
smoke / unit test: cpu-basic, 10m timeout
small experiments: cpu-basic or cpu-upgrade
GPU: only after CPU wall-clock evidence justifies it
```

Hardware selection is part of experimental provenance.

## Launch pattern

Use the raw runner at the exact commit being tested.

Conceptually:

```text
hf_jobs(
  uv,
  script = raw GitHub URL for hf_agent_job.py at COMMIT,
  script_args = [
    "--commit", COMMIT,
    "--artifact", "artifacts/result.json",
    "--",
    "python", "-m", "agent_ecology.some_experiment",
    ... experiment args ...
  ],
  flavor = "cpu-basic",
  timeout = "..."
)
```

Because the runner itself is loaded from the same commit that it downloads, source and execution provenance stay aligned.

## First gate

Before migrating substantive experiments:

```text
1. run focused Agent test on CPU Basic
2. confirm pinned commit in logs
3. confirm exit status
4. run a tiny artifact-producing job
5. recover artifact from logs and verify SHA-256
```

Only then use HF Jobs for longer Agent v1 sweeps.

## Polling rule

Jobs are asynchronous.

Do not synchronously wait for them and do not poll in a loop.

Launch the job, retain its job ID, and inspect it on a later turn or when the user asks. A completed state is terminal.

## Original Agent v1 anchor

Changing the compute backend does not change the architecture or experimental gates.

Agent v1 remains a sparse developmental computational ecology whose structural changes must be causally useful and economically justified.
