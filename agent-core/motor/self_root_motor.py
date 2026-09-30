#!/usr/bin/env python3
"""SELF-ROOT bounded motor daemon.

Polls Agent Core for allowlisted commands and executes only local handlers
defined in this file. There is intentionally no arbitrary-shell command type.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("/workspace/continuity")
MOTOR_DIR = ROOT / "motor"
SECRETS_DIR = ROOT / "secrets"
TOKEN_FILE = SECRETS_DIR / "motor_token"
URL_FILE = MOTOR_DIR / "runtime_url"
LOG_FILE = MOTOR_DIR / "motor.log"
STATE_DIR = ROOT / "state"
EVIDENCE_DIR = ROOT / "evidence"
EVIDENCE_LEDGER_FILE = EVIDENCE_DIR / "evidence-ledger-v1.jsonl"
EVIDENCE_INDEX_FILE = EVIDENCE_DIR / "event-index-v1.json"
STATE_SNAPSHOT_FILE = STATE_DIR / "materialized-work-state-v1.json"
LEGACY_STATE_SNAPSHOT_FILE = STATE_DIR / "agent-core-snapshot-v1.json"

POLL_SECONDS = 5
HTTP_TIMEOUT = 20


def log(event: str, **fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    print(line, flush=True)
    try:
        MOTOR_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_config() -> tuple[str, str]:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    base = URL_FILE.read_text(encoding="utf-8").strip().rstrip("/")
    if not token or not base.startswith("https://"):
        raise RuntimeError("motor configuration missing or invalid")
    return base, token


def request_json(method: str, url: str, token: str, body=None):
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        raw = resp.read(1_048_576)
        return json.loads(raw.decode("utf-8")) if raw else {}


def run_process(argv: list[str], timeout: int = 120, cwd: str = "/workspace", env=None) -> dict:
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env if env is not None else {**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    return {
        "exitCode": proc.returncode,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-4000:],
    }


def handle_system_ping() -> dict:
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "python": shutil.which("python3"),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _load_evidence_index() -> dict:
    if not EVIDENCE_INDEX_FILE.exists():
        return {"schema": 1, "events": {}, "count": 0, "headHash": None}
    try:
        value = json.loads(EVIDENCE_INDEX_FILE.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("events"), dict):
            raise ValueError("invalid_index")
        return value
    except Exception:
        return {"schema": 1, "events": {}, "count": 0, "headHash": None}


def _write_evidence_index(index: dict) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = EVIDENCE_DIR / f".{EVIDENCE_INDEX_FILE.name}.{os.getpid()}.tmp"
    raw = (json.dumps(index, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    with tmp.open("wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, EVIDENCE_INDEX_FILE)


def _validate_evidence_event(event) -> dict:
    if not isinstance(event, dict):
        raise ValueError("invalid_evidence_event")
    required = [
        "schema_version",
        "event_id",
        "correlation_id",
        "event_type",
        "occurred_at",
        "recorded_at",
        "source",
        "payload",
        "provenance",
    ]
    for key in required:
        if key not in event:
            raise ValueError(f"missing_evidence_{key}")
    if event.get("schema_version") != "1.0":
        raise ValueError("unsupported_evidence_schema")
    if not isinstance(event.get("payload"), dict) or not isinstance(event.get("provenance"), dict):
        raise ValueError("invalid_evidence_payload")
    if not event.get("provenance", {}).get("event_hash"):
        raise ValueError("missing_evidence_event_hash")
    return event


def handle_evidence_ledger_append(payload=None) -> dict:
    events = payload.get("events") if isinstance(payload, dict) else None
    if events is None and isinstance(payload, dict) and isinstance(payload.get("event"), dict):
        events = [payload["event"]]
    if not isinstance(events, list) or not events or len(events) > 50:
        return {"exitCode": 2, "error": "invalid_evidence_batch"}
    index = _load_evidence_index()
    accepted = 0
    duplicates = 0
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_LEDGER_FILE.open("a", encoding="utf-8") as ledger:
        for raw in events:
            event = _validate_evidence_event(raw)
            event_id = str(event["event_id"])
            event_hash = str(event["provenance"]["event_hash"])
            existing = index["events"].get(event_id)
            if existing:
                if existing != event_hash:
                    return {"exitCode": 3, "error": "evidence_event_id_hash_conflict", "eventId": event_id}
                duplicates += 1
                continue
            ledger.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            index["events"][event_id] = event_hash
            index["count"] = int(index.get("count") or 0) + 1
            index["headHash"] = event_hash
            accepted += 1
    _write_evidence_index(index)
    return {
        "exitCode": 0,
        "accepted": accepted,
        "duplicates": duplicates,
        "count": index.get("count", 0),
        "headHash": index.get("headHash"),
        "path": str(EVIDENCE_LEDGER_FILE),
    }


def handle_evidence_ledger_status(_payload=None) -> dict:
    index = _load_evidence_index()
    return {
        "exists": EVIDENCE_LEDGER_FILE.exists(),
        "count": index.get("count", 0),
        "headHash": index.get("headHash"),
        "bytes": EVIDENCE_LEDGER_FILE.stat().st_size if EVIDENCE_LEDGER_FILE.exists() else 0,
        "path": str(EVIDENCE_LEDGER_FILE),
        "materializedStatePath": str(STATE_SNAPSHOT_FILE),
        "legacySnapshotExists": LEGACY_STATE_SNAPSHOT_FILE.exists(),
    }


def handle_evidence_ledger_read(payload=None) -> dict:
    after_seq = int((payload or {}).get("afterSeq") or 0)
    limit = max(1, min(int((payload or {}).get("limit") or 50), 100))
    if not EVIDENCE_LEDGER_FILE.exists():
        return {"events": [], "nextSeq": after_seq, "hasMore": False}
    events = []
    seq = 0
    with EVIDENCE_LEDGER_FILE.open("r", encoding="utf-8") as ledger:
        for line in ledger:
            if not line.strip():
                continue
            seq += 1
            if seq <= after_seq:
                continue
            if len(events) >= limit:
                break
            event = json.loads(line)
            _validate_evidence_event(event)
            events.append(event)
    index = _load_evidence_index()
    next_seq = after_seq + len(events)
    return {
        "events": events,
        "nextSeq": next_seq,
        "hasMore": next_seq < int(index.get("count") or 0),
        "count": index.get("count", 0),
        "headHash": index.get("headHash"),
    }


def handle_continuity_verify() -> dict:
    status = handle_evidence_ledger_status()
    index = _load_evidence_index()
    indexed_count = int(index.get("count") or 0)
    actual_count = 0
    parse_errors = 0
    if EVIDENCE_LEDGER_FILE.exists():
        with EVIDENCE_LEDGER_FILE.open("r", encoding="utf-8") as ledger:
            for line in ledger:
                if not line.strip():
                    continue
                try:
                    _validate_evidence_event(json.loads(line))
                    actual_count += 1
                except Exception:
                    parse_errors += 1
    return {
        "exitCode": 0 if parse_errors == 0 and actual_count == indexed_count else 1,
        "architecture": "evidence-ledger-v1",
        "ledger": status,
        "indexedCount": indexed_count,
        "actualCount": actual_count,
        "parseErrors": parse_errors,
        "legacyVerifierExists": (ROOT / "verify.py").exists(),
    }


def handle_continuity_status() -> dict:
    kernel = ROOT / "kernel"
    evidence_status = handle_evidence_ledger_status()
    return {
        "architecture": "evidence-ledger-v1",
        "workspaceExists": ROOT.exists(),
        "evidence": evidence_status,
        "materializedStateExists": STATE_SNAPSHOT_FILE.exists(),
        "legacyKernelExists": kernel.exists(),
        "legacyVerifyExists": (ROOT / "verify.py").exists(),
        "browserProfileExists": Path("/workspace/browser/profile").exists(),
    }


def handle_browser_profile_status() -> dict:
    profile = Path("/workspace/browser/profile")
    chromium = (
        shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
    )
    size_kb = None
    if profile.exists():
        try:
            du = subprocess.run(
                ["du", "-sk", str(profile)],
                text=True,
                capture_output=True,
                timeout=15,
            )
            if du.returncode == 0:
                size_kb = int(du.stdout.split()[0])
        except Exception:
            pass
    return {
        "profile": str(profile),
        "exists": profile.exists(),
        "sizeKb": size_kb,
        "chromium": chromium,
        "singletonLock": (profile / "SingletonLock").exists(),
        "localState": (profile / "Local State").exists(),
    }


def handle_state_snapshot_read(_payload=None) -> dict:
    source = STATE_SNAPSHOT_FILE if STATE_SNAPSHOT_FILE.exists() else LEGACY_STATE_SNAPSHOT_FILE
    if not source.exists():
        return {"exists": False, "snapshot": None}
    raw = source.read_bytes()
    if len(raw) > 1_048_576:
        return {"exitCode": 1, "error": "snapshot_too_large"}
    snapshot = json.loads(raw.decode("utf-8"))
    return {
        "exists": True,
        "snapshot": snapshot,
        "bytes": len(raw),
        "path": str(source),
        "legacy": source == LEGACY_STATE_SNAPSHOT_FILE,
    }


def handle_state_snapshot_write(payload=None) -> dict:
    snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
    if not isinstance(snapshot, dict):
        return {"exitCode": 2, "error": "invalid_snapshot_payload"}
    raw = (json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    if len(raw) > 1_048_576:
        return {"exitCode": 3, "error": "snapshot_too_large", "bytes": len(raw)}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_DIR / f".{STATE_SNAPSHOT_FILE.name}.{os.getpid()}.tmp"
    with tmp.open("wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATE_SNAPSHOT_FILE)
    return {"written": True, "bytes": len(raw), "path": str(STATE_SNAPSHOT_FILE)}


JOBS_DIR = ROOT / "jobs"
MAX_JOB_STEPS = 16
MAX_JOB_TEXT_BYTES = 262_144
MAX_JOB_DOWNLOAD_BYTES = 2_097_152
MAX_STEP_OUTPUT = 6_000


def _clip(value, limit: int = MAX_STEP_OUTPUT) -> str:
    return str(value or "")[-limit:]


def _safe_job_id(value) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", value):
        raise ValueError("invalid_job_id")
    return value


def _safe_relative_path(root: Path, value) -> Path:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("/", "\\")) or "\x00" in raw:
        raise ValueError("invalid_relative_path")
    rel = Path(raw)
    if any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("invalid_relative_path")
    root_resolved = root.resolve()
    candidate = (root / rel).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path_outside_job_workspace") from exc
    return candidate


def _safe_public_https_url(value, *, github_only: bool = False) -> str:
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid_https_url")
    host = parsed.hostname.lower()
    if github_only and host != "github.com":
        raise ValueError("github_clone_requires_github_com")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("hostname_resolution_failed") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("non_public_destination")
    return urllib.parse.urlunsplit(parsed)


def _job_env(job_root: Path) -> dict:
    home = job_root / ".home"
    home.mkdir(parents=True, exist_ok=True)
    keep = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "HOME": str(home),
        "PYTHONUNBUFFERED": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    return keep


def _step_result(step_type: str, ok: bool, **fields) -> dict:
    clean = {"type": step_type, "ok": ok}
    for key, value in fields.items():
        if isinstance(value, str):
            clean[key] = _clip(value)
        else:
            clean[key] = value
    return clean


def _run_git(job_root: Path, repo: Path, args: list[str], timeout: int = 120) -> dict:
    if not (repo / ".git").exists():
        raise ValueError("not_a_git_worktree")
    result = run_process(
        ["git", "-C", str(repo), *args],
        timeout=timeout,
        cwd=str(job_root),
        env=_job_env(job_root),
    )
    return {
        "exitCode": result["exitCode"],
        "stdout": _clip(result["stdout"]),
        "stderr": _clip(result["stderr"]),
    }


def _execute_work_step(job_root: Path, step: dict) -> dict:
    if not isinstance(step, dict):
        raise ValueError("invalid_work_step")
    step_type = str(step.get("type") or "").strip().lower()

    if step_type == "mkdir":
        path = _safe_relative_path(job_root, step.get("path"))
        path.mkdir(parents=True, exist_ok=True)
        return _step_result(step_type, True, path=str(path.relative_to(job_root)))

    if step_type == "write_text":
        content = step.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_JOB_TEXT_BYTES:
            raise ValueError("invalid_or_oversized_text")
        path = _safe_relative_path(job_root, step.get("path"))
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and step.get("overwrite") is not True:
            raise ValueError("target_exists_without_overwrite")
        path.write_text(content, encoding="utf-8")
        return _step_result(
            step_type,
            True,
            path=str(path.relative_to(job_root)),
            bytes=len(content.encode("utf-8")),
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    if step_type == "read_text":
        path = _safe_relative_path(job_root, step.get("path"))
        raw = path.read_bytes()
        if len(raw) > MAX_JOB_TEXT_BYTES:
            raise ValueError("text_file_too_large")
        return _step_result(
            step_type,
            True,
            path=str(path.relative_to(job_root)),
            text=raw.decode("utf-8", errors="replace"),
            bytes=len(raw),
        )

    if step_type == "fetch_https":
        url = _safe_public_https_url(step.get("url"))
        path = _safe_relative_path(job_root, step.get("path"))
        req = urllib.request.Request(url, headers={"User-Agent": "SELF-ROOT-bounded-motor/0.18"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(MAX_JOB_DOWNLOAD_BYTES + 1)
        if len(data) > MAX_JOB_DOWNLOAD_BYTES:
            raise ValueError("download_too_large")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return _step_result(
            step_type,
            True,
            path=str(path.relative_to(job_root)),
            bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    if step_type == "git_clone_public":
        url = _safe_public_https_url(step.get("url"), github_only=True)
        parsed = urllib.parse.urlsplit(url)
        pieces = [p for p in parsed.path.split("/") if p]
        if len(pieces) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:\.git)?", pieces[1]):
            raise ValueError("invalid_github_repository_url")
        dest = _safe_relative_path(job_root, step.get("path") or pieces[1].removesuffix(".git"))
        if dest.exists():
            raise ValueError("clone_destination_exists")
        argv = ["git", "clone", "--depth", "1", "--filter=blob:none"]
        ref = str(step.get("ref") or "").strip()
        if ref:
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", ref) or ".." in ref:
                raise ValueError("invalid_git_ref")
            argv += ["--branch", ref]
        argv += [url, str(dest)]
        result = run_process(argv, timeout=180, cwd=str(job_root), env=_job_env(job_root))
        if result["exitCode"] != 0:
            return _step_result(step_type, False, exitCode=result["exitCode"], stderr=result["stderr"])
        return _step_result(step_type, True, path=str(dest.relative_to(job_root)), stdout=result["stdout"])

    if step_type == "git_apply_patch":
        repo = _safe_relative_path(job_root, step.get("repo"))
        patch = step.get("patch")
        if not isinstance(patch, str) or not patch or len(patch.encode("utf-8")) > MAX_JOB_TEXT_BYTES:
            raise ValueError("invalid_or_oversized_patch")
        patch_file = job_root / f".patch-{os.getpid()}-{time.time_ns()}.diff"
        patch_file.write_text(patch, encoding="utf-8")
        try:
            check = _run_git(job_root, repo, ["apply", "--check", str(patch_file)], timeout=60)
            if check["exitCode"] != 0:
                return _step_result(step_type, False, **check)
            applied = _run_git(job_root, repo, ["apply", str(patch_file)], timeout=60)
            return _step_result(step_type, applied["exitCode"] == 0, **applied)
        finally:
            patch_file.unlink(missing_ok=True)

    if step_type == "git_inspect":
        repo = _safe_relative_path(job_root, step.get("repo"))
        mode = str(step.get("mode") or "status").strip().lower()
        modes = {
            "status": ["status", "--short", "--branch"],
            "diff": ["diff", "--no-ext-diff", "--"],
            "diff_stat": ["diff", "--stat", "--"],
            "head": ["log", "-1", "--oneline", "--decorate=no"],
        }
        if mode not in modes:
            raise ValueError("unsupported_git_inspect_mode")
        result = _run_git(job_root, repo, modes[mode], timeout=60)
        return _step_result(step_type, result["exitCode"] == 0, mode=mode, **result)

    if step_type == "syntax_check":
        kind = str(step.get("kind") or "").strip().lower()
        paths = step.get("paths")
        if not isinstance(paths, list) or not paths or len(paths) > 20:
            raise ValueError("invalid_syntax_check_paths")
        checked = []
        for rel in paths:
            path = _safe_relative_path(job_root, rel)
            if kind == "json":
                json.loads(path.read_text(encoding="utf-8"))
                checked.append(str(path.relative_to(job_root)))
            elif kind == "python":
                result = run_process(
                    ["python3", "-m", "py_compile", str(path)],
                    timeout=30,
                    cwd=str(job_root),
                    env=_job_env(job_root),
                )
                if result["exitCode"] != 0:
                    return _step_result(step_type, False, path=str(path.relative_to(job_root)), stderr=result["stderr"])
                checked.append(str(path.relative_to(job_root)))
            elif kind == "node":
                node = shutil.which("node")
                if not node:
                    raise ValueError("node_not_available")
                result = run_process(
                    [node, "--check", str(path)],
                    timeout=30,
                    cwd=str(job_root),
                    env=_job_env(job_root),
                )
                if result["exitCode"] != 0:
                    return _step_result(step_type, False, path=str(path.relative_to(job_root)), stderr=result["stderr"])
                checked.append(str(path.relative_to(job_root)))
            else:
                raise ValueError("unsupported_syntax_check_kind")
        return _step_result(step_type, True, kind=kind, checked=checked)

    if step_type == "git_stage_commit":
        repo = _safe_relative_path(job_root, step.get("repo"))
        files = step.get("paths")
        message = str(step.get("message") or "").strip()
        if not isinstance(files, list) or not files or len(files) > 50:
            raise ValueError("invalid_commit_paths")
        if not message or len(message) > 300:
            raise ValueError("invalid_commit_message")
        safe_files = []
        for rel in files:
            path = _safe_relative_path(repo, rel)
            safe_files.append(str(path.relative_to(repo)))
        staged = _run_git(job_root, repo, ["add", "--", *safe_files], timeout=60)
        if staged["exitCode"] != 0:
            return _step_result(step_type, False, **staged)
        committed = _run_git(
            job_root,
            repo,
            [
                "-c", "user.name=SELF-ROOT",
                "-c", "user.email=oldcraft541@agentmail.to",
                "commit", "--no-verify", "-m", message,
            ],
            timeout=60,
        )
        return _step_result(step_type, committed["exitCode"] == 0, **committed)

    raise ValueError("unsupported_work_step")


def handle_work_execute(payload=None) -> dict:
    if not isinstance(payload, dict):
        return {"exitCode": 2, "error": "invalid_work_payload"}
    try:
        job_id = _safe_job_id(payload.get("jobId"))
        steps = payload.get("steps")
        if not isinstance(steps, list) or not steps or len(steps) > MAX_JOB_STEPS:
            raise ValueError("invalid_work_steps")
        job_root = JOBS_DIR / job_id
        job_root.mkdir(parents=True, exist_ok=True)
        os.chmod(job_root, 0o700)
        results = []
        artifacts = []
        for index, step in enumerate(steps):
            started = time.time()
            try:
                result = _execute_work_step(job_root, step)
            except Exception as exc:
                result = _step_result(
                    str(step.get("type") if isinstance(step, dict) else "unknown"),
                    False,
                    error=type(exc).__name__,
                    detail=str(exc),
                )
            result["index"] = index
            result["durationMs"] = int((time.time() - started) * 1000)
            results.append(result)
            if result.get("path"):
                artifacts.append(result["path"])
            if not result.get("ok") and not (isinstance(step, dict) and step.get("continueOnError") is True):
                return {
                    "exitCode": 1,
                    "jobId": job_id,
                    "summary": f"work step {index} failed",
                    "workspace": str(job_root),
                    "steps": results,
                    "artifacts": artifacts[-20:],
                }
        return {
            "exitCode": 0,
            "jobId": job_id,
            "summary": f"completed {len(results)} bounded work steps",
            "workspace": str(job_root),
            "steps": results,
            "artifacts": artifacts[-20:],
        }
    except Exception as exc:
        return {"exitCode": 2, "error": type(exc).__name__, "detail": str(exc)[:1000]}


HANDLERS = {
    "system.ping": handle_system_ping,
    "continuity.verify": handle_continuity_verify,
    "continuity.status": handle_continuity_status,
    "browser.profile.status": handle_browser_profile_status,
    "state.snapshot.read": handle_state_snapshot_read,
    "state.snapshot.write": handle_state_snapshot_write,
    "evidence.ledger.append": handle_evidence_ledger_append,
    "evidence.ledger.status": handle_evidence_ledger_status,
    "evidence.ledger.read": handle_evidence_ledger_read,
    "work.execute": handle_work_execute,
}


def execute(command: dict) -> tuple[bool, dict]:
    action = command.get("action")
    handler = HANDLERS.get(action)
    if handler is None:
        return False, {"error": "action_not_implemented", "action": action}
    try:
        result = handler(command.get("payload")) if action.startswith("state.snapshot.") or action.startswith("evidence.ledger.") or action == "work.execute" else handler()
        ok = not isinstance(result, dict) or result.get("exitCode", 0) == 0
        return ok, result
    except subprocess.TimeoutExpired as exc:
        return False, {"error": "timeout", "detail": str(exc)}
    except Exception as exc:
        return False, {"error": type(exc).__name__, "detail": str(exc)[:1000]}


def main() -> int:
    MOTOR_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    log("motor.starting", allowedActions=sorted(HANDLERS))
    backoff = POLL_SECONDS

    while True:
        try:
            base, token = read_config()
            payload = request_json("GET", f"{base}/v1/motor/poll", token)
            command = payload.get("command")
            if not command:
                backoff = POLL_SECONDS
                time.sleep(POLL_SECONDS)
                continue

            command_id = str(command.get("id") or "")
            action = str(command.get("action") or "")
            log("motor.command.received", commandId=command_id, action=action)
            ok, result = execute(command)
            request_json(
                "POST",
                f"{base}/v1/motor/ack",
                token,
                {"id": command_id, "ok": ok, "result": result},
            )
            log("motor.command.acked", commandId=command_id, action=action, ok=ok)
            backoff = POLL_SECONDS
        except urllib.error.HTTPError as exc:
            log("motor.http_error", status=exc.code)
            backoff = min(max(backoff * 2, 10), 120)
            time.sleep(backoff)
        except Exception as exc:
            log("motor.error", error=type(exc).__name__, detail=str(exc)[:500])
            backoff = min(max(backoff * 2, 10), 120)
            time.sleep(backoff)


if __name__ == "__main__":
    raise SystemExit(main())
