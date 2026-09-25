#!/usr/bin/env python3
"""Verify an AI Workbench APK is signed by the pinned stable certificate."""

from __future__ import annotations

import re
import subprocess
import sys

EXPECTED_SHA256 = "E2E3D6D0FE17D97FE76855F5758D923DBA2A5F7D95EA59DA257B38B042C907EF"


def normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value).upper()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_android_signing.py <apksigner> <apk>")

    apksigner, apk = sys.argv[1], sys.argv[2]
    result = subprocess.run(
        [apksigner, "verify", "--verbose", "--print-certs", apk],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    match = re.search(
        r"certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)",
        result.stdout,
    )
    if not match:
        print(result.stdout)
        raise SystemExit("Could not read APK signing certificate SHA-256")

    actual = normalize(match.group(1))
    if actual != EXPECTED_SHA256:
        print(result.stdout)
        raise SystemExit(
            "APK is not signed by the pinned AI Workbench identity. "
            f"expected={EXPECTED_SHA256} actual={actual}"
        )

    print(f"Stable signing certificate verified: {actual}")


if __name__ == "__main__":
    main()
