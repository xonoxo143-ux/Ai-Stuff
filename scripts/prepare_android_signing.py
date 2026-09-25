#!/usr/bin/env python3
"""Prepare the private Android signing identity from one GitHub Actions secret.

The repository stores no private signing material. The secret value is a base64
encoded JSON envelope containing the PKCS#12 bytes, alias, and password.

Expected secret:
  AI_WORKBENCH_SIGNING_BUNDLE

This script writes the keystore to RUNNER_TEMP and exports only file/alias/password
variables through GITHUB_ENV. It never prints private material.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path


def main() -> None:
    raw = os.environ.get("AI_WORKBENCH_SIGNING_BUNDLE", "").strip()
    if not raw:
        raise SystemExit(
            "AI_WORKBENCH_SIGNING_BUNDLE is not configured. "
            "Refusing to build an APK with an ephemeral signing key."
        )

    try:
        envelope = json.loads(base64.b64decode(raw))
    except Exception as exc:
        raise SystemExit(f"Invalid signing bundle: {exc}") from exc

    if envelope.get("schema") != 1:
        raise SystemExit("Unsupported signing bundle schema")

    alias = str(envelope["alias"])
    password = str(envelope["password"])
    keystore_bytes = base64.b64decode(envelope["keystore_b64"])

    runner_temp = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    keystore = runner_temp / "aiworkbench-stable-signing.p12"
    keystore.write_bytes(keystore_bytes)
    keystore.chmod(0o600)

    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        raise SystemExit("GITHUB_ENV is unavailable")

    with open(github_env, "a", encoding="utf-8") as env:
        env.write(f"AI_WORKBENCH_KEYSTORE_FILE={keystore}\n")
        env.write(f"AI_WORKBENCH_KEY_ALIAS={alias}\n")
        env.write(f"AI_WORKBENCH_KEYSTORE_PASSWORD={password}\n")
        env.write(f"AI_WORKBENCH_KEY_PASSWORD={password}\n")

    # Only non-sensitive confirmation.
    print(f"Stable Android signing identity prepared: alias={alias}")


if __name__ == "__main__":
    main()
