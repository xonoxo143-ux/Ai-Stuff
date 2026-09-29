#!/usr/bin/env python3
"""SELF-ROOT bounded motor daemon.

Polls Agent Core for allowlisted commands and executes only local handlers
defined in this file. There is intentionally no arbitrary-shell command type.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/workspace/continuity")
MOTOR_DIR = ROOT / "motor"
SECRETS_DIR = ROOT / "secrets"
TOKEN_FILE = SECRETS_DIR / "motor_token"
URL_FILE = MOTOR_DIR / "runtime_url"
LOG_FILE = MOTOR_DIR / "motor.log"
STATE_DIR = ROOT / "state"
STATE_SNAPSHOT_FILE = STATE_DIR / "agent-core-snapshot-v1.json"

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


def run_process(argv: list[str], timeout: int = 120) -> dict:
    proc = subprocess.run(
        argv,
        cwd="/workspace",
        text=True,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
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


def handle_continuity_verify() -> dict:
    verifier = ROOT / "verify.py"
    if not verifier.exists():
        return {"exitCode": 127, "error": f"missing {verifier}"}
    return run_process(["python3", str(verifier)], timeout=180)


def handle_continuity_status() -> dict:
    kernel = ROOT / "kernel"
    files = []
    if kernel.exists():
        for p in sorted(kernel.iterdir())[:100]:
            try:
                files.append({
                    "name": p.name,
                    "type": "dir" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else None,
                })
            except OSError:
                pass
    return {
        "workspaceExists": ROOT.exists(),
        "kernelExists": kernel.exists(),
        "kernelEntries": files,
        "verifyExists": (ROOT / "verify.py").exists(),
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
    if not STATE_SNAPSHOT_FILE.exists():
        return {"exists": False, "snapshot": None}
    raw = STATE_SNAPSHOT_FILE.read_bytes()
    if len(raw) > 1_048_576:
        return {"exitCode": 1, "error": "snapshot_too_large"}
    snapshot = json.loads(raw.decode("utf-8"))
    return {
        "exists": True,
        "snapshot": snapshot,
        "bytes": len(raw),
        "path": str(STATE_SNAPSHOT_FILE),
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


HANDLERS = {
    "system.ping": handle_system_ping,
    "continuity.verify": handle_continuity_verify,
    "continuity.status": handle_continuity_status,
    "browser.profile.status": handle_browser_profile_status,
    "state.snapshot.read": handle_state_snapshot_read,
    "state.snapshot.write": handle_state_snapshot_write,
}


def execute(command: dict) -> tuple[bool, dict]:
    action = command.get("action")
    handler = HANDLERS.get(action)
    if handler is None:
        return False, {"error": "action_not_implemented", "action": action}
    try:
        result = handler(command.get("payload")) if action.startswith("state.snapshot.") else handler()
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
