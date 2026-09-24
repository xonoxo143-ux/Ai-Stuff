# Workspace

This directory is the mutable control plane consumed by the Android AI Workbench.

Keep it small and declarative.

Commit here:

- benchmark suites
- prompt/system presets
- experiment recipes
- model manifests
- small configuration files

Do not commit model weights or bulky datasets.

The phone pulls this directory and writes results to its local outbox. Selected small artifacts can then be pushed under `devices/<device-id>/`.
