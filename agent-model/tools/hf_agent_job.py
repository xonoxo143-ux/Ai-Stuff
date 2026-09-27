# /// script
# requires-python = ">=3.11"
# dependencies = ["pip>=24"]
# ///
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


REPO = "xonoxo143-ux/Ai-Stuff"
ARCHIVE_URL = "https://github.com/{repo}/archive/{commit}.zip"
ARTIFACT_PREFIX = "AGENT_ARTIFACT_GZIP_BASE64 "
META_PREFIX = "AGENT_JOB_META "
RESULT_PREFIX = "AGENT_JOB_RESULT "


def _emit(prefix: str, payload: dict) -> None:
    print(prefix + json.dumps(payload, sort_keys=True), flush=True)


def _install_cpu_stack() -> None:
    # Match the CI stack closely while forcing a CPU-only PyTorch wheel.
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
            "torch>=2.4,<3",
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "numpy>=1.26,<3",
            "pytest>=8",
        ],
        check=True,
    )


def _download_source(commit: str, destination: Path) -> Path:
    archive = destination / "source.zip"
    url = ARCHIVE_URL.format(repo=REPO, commit=commit)
    print(f"Downloading pinned source: {url}", flush=True)
    urllib.request.urlretrieve(url, archive)

    extract_root = destination / "source"
    extract_root.mkdir()
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extract_root)

    roots = [path for path in extract_root.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"expected one archive root, found {len(roots)}")
    return roots[0]


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        raise ValueError("a command is required after --")
    if command[0] in {"python", "python3"}:
        return [sys.executable, *command[1:]]
    return command


def _persist_artifact(workdir: Path, requested: str, max_bytes: int) -> None:
    path = (workdir / requested).resolve()
    if not path.is_relative_to(workdir.resolve()):
        raise ValueError(f"artifact escapes workdir: {requested}")
    if not path.is_file():
        raise FileNotFoundError(f"artifact not found: {requested}")

    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError(
            f"artifact {requested} is {len(raw)} bytes; "
            f"log persistence limit is {max_bytes}"
        )

    compressed = gzip.compress(raw, compresslevel=9)
    payload = {
        "path": requested,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "encoding": "gzip+base64",
        "data": base64.b64encode(compressed).decode("ascii"),
    }
    _emit(ARTIFACT_PREFIX, payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproducible Hugging Face Jobs runner for Agent v1."
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Small result file, relative to agent-model, to persist in logs.",
    )
    parser.add_argument(
        "--max-artifact-bytes",
        type=int,
        default=2_000_000,
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip installing the CPU PyTorch/test stack.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command after --, e.g. -- python -m pytest ...",
    )
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    command = _resolve_command(command)

    _emit(
        META_PREFIX,
        {
            "schema": 1,
            "repo": REPO,
            "commit": args.commit,
            "platform": platform.platform(),
            "python": sys.version,
            "command": command,
            "artifact_paths": args.artifact,
        },
    )

    with tempfile.TemporaryDirectory(prefix="agent-hf-job-") as tmp:
        tmp_path = Path(tmp)
        root = _download_source(args.commit, tmp_path)
        workdir = root / "agent-model"
        if not workdir.is_dir():
            raise RuntimeError("agent-model directory missing from pinned source")

        if not args.skip_install:
            _install_cpu_stack()

        env = os.environ.copy()
        old_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(workdir)
            if not old_pythonpath
            else str(workdir) + os.pathsep + old_pythonpath
        )
        env["PYTHONUNBUFFERED"] = "1"

        print(
            "Running from pinned source "
            f"{args.commit} in {workdir}",
            flush=True,
        )
        completed = subprocess.run(
            command,
            cwd=workdir,
            env=env,
        )

        if completed.returncode == 0:
            for artifact in args.artifact:
                _persist_artifact(
                    workdir,
                    artifact,
                    args.max_artifact_bytes,
                )

        _emit(
            RESULT_PREFIX,
            {
                "commit": args.commit,
                "returncode": completed.returncode,
                "success": completed.returncode == 0,
            },
        )
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
