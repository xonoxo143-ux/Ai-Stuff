#!/bin/sh
set -eu

RUNTIME_URL="${SELF_ROOT_RUNTIME_URL:-https://browser-worker-wnux-production.up.railway.app}"
BOOTSTRAP_TOKEN="${SELF_ROOT_MOTOR_BOOTSTRAP_TOKEN:-}"

if [ -z "$BOOTSTRAP_TOKEN" ]; then
  echo "SELF_ROOT_MOTOR_BOOTSTRAP_TOKEN is required" >&2
  exit 2
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 3; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 3; }

mkdir -p /workspace/continuity/motor /workspace/continuity/secrets
chmod 700 /workspace/continuity/secrets

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

curl -fsS -X POST   -H "Authorization: Bearer $BOOTSTRAP_TOKEN"   "$RUNTIME_URL/v1/motor/bootstrap" > "$TMP_JSON"

MOTOR_TOKEN="$(python3 - "$TMP_JSON" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    obj=json.load(f)
token=str(obj.get("motorToken") or "").strip()
if not token:
    raise SystemExit("bootstrap response did not contain motorToken")
print(token)
PY
)"

printf '%s\n' "$MOTOR_TOKEN" > /workspace/continuity/secrets/motor_token
chmod 600 /workspace/continuity/secrets/motor_token
printf '%s\n' "$RUNTIME_URL" > /workspace/continuity/motor/runtime_url
chmod 600 /workspace/continuity/motor/runtime_url

curl -fsSL   "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/motor/self_root_motor.py"   -o /workspace/continuity/motor/self_root_motor.py
chmod 700 /workspace/continuity/motor/self_root_motor.py

mkdir -p /workspace/continuity/motor
touch /workspace/continuity/motor/motor.log

install_openrc() {
  cat > /etc/init.d/self-root-motor <<'RC'
#!/sbin/openrc-run
name="SELF-ROOT motor"
description="Bounded outbound command nerve for SELF-ROOT"
command="/usr/bin/python3"
command_args="/workspace/continuity/motor/self_root_motor.py"
command_background="yes"
pidfile="/run/self-root-motor.pid"
output_log="/workspace/continuity/motor/service.stdout.log"
error_log="/workspace/continuity/motor/service.stderr.log"

depend() {
  need net
  after firewall
}
RC
  chmod 755 /etc/init.d/self-root-motor
  rc-update add self-root-motor default >/dev/null 2>&1 || true
  rc-service self-root-motor restart >/dev/null 2>&1 || rc-service self-root-motor start
}

install_systemd() {
  cat > /etc/systemd/system/self-root-motor.service <<'UNIT'
[Unit]
Description=SELF-ROOT bounded motor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /workspace/continuity/motor/self_root_motor.py
Restart=always
RestartSec=5
User=root
WorkingDirectory=/workspace
StandardOutput=append:/workspace/continuity/motor/service.stdout.log
StandardError=append:/workspace/continuity/motor/service.stderr.log

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable self-root-motor.service >/dev/null 2>&1
  systemctl restart self-root-motor.service
}

install_fallback() {
  if [ -f /workspace/continuity/motor/motor.pid ]; then
    oldpid="$(cat /workspace/continuity/motor/motor.pid 2>/dev/null || true)"
    [ -n "$oldpid" ] && kill "$oldpid" 2>/dev/null || true
  fi
  nohup python3 /workspace/continuity/motor/self_root_motor.py     >>/workspace/continuity/motor/service.stdout.log     2>>/workspace/continuity/motor/service.stderr.log &
  echo "$!" > /workspace/continuity/motor/motor.pid

  if command -v crontab >/dev/null 2>&1; then
    tmpcron="$(mktemp)"
    crontab -l 2>/dev/null | grep -v 'self_root_motor.py' > "$tmpcron" || true
    printf '%s\n' '@reboot nohup python3 /workspace/continuity/motor/self_root_motor.py >>/workspace/continuity/motor/service.stdout.log 2>>/workspace/continuity/motor/service.stderr.log &' >> "$tmpcron"
    crontab "$tmpcron"
    rm -f "$tmpcron"
  fi
}

if command -v rc-service >/dev/null 2>&1 && [ -x /sbin/openrc-run ]; then
  install_openrc
elif command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  install_systemd
else
  install_fallback
fi

sleep 2
python3 - <<'PY'
from pathlib import Path
print("SELF-ROOT motor installed")
print("token:", "present" if Path("/workspace/continuity/secrets/motor_token").exists() else "missing")
print("runtime:", Path("/workspace/continuity/motor/runtime_url").read_text().strip())
print("daemon:", Path("/workspace/continuity/motor/self_root_motor.py"))
PY
