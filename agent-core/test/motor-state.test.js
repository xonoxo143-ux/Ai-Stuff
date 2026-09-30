import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

test("bounded motor atomically writes and reads the durable work snapshot", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "motor-state-test-"));
  const script = String.raw`
import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location("motor", sys.argv[1])
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)
state_dir = pathlib.Path(sys.argv[2])
motor.STATE_DIR = state_dir
motor.STATE_SNAPSHOT_FILE = state_dir / "agent-core-snapshot-v1.json"
written = motor.handle_state_snapshot_write({"snapshot": {"workLedger": [["p:1", {"state": "PAID"}]]}})
loaded = motor.handle_state_snapshot_read()
print(json.dumps({"written": written, "loaded": loaded}))
`;
  try {
    const motorPath = path.resolve(import.meta.dirname, "../motor/self_root_motor.py");
    const { stdout } = await execFileAsync("python3", ["-c", script, motorPath, directory]);
    const result = JSON.parse(stdout);
    assert.equal(result.written.written, true);
    assert.equal(result.loaded.exists, true);
    assert.equal(result.loaded.snapshot.workLedger[0][1].state, "PAID");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});



test("bounded motor executes typed work steps and rejects path traversal", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "motor-work-test-"));
  const script = `
import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location("motor", sys.argv[1])
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)
root = pathlib.Path(sys.argv[2])
motor.JOBS_DIR = root / "jobs"
ok, result = motor.execute({"action":"work.execute","payload":{"jobId":"unit-job","steps":[{"type":"mkdir","path":"artifact"},{"type":"write_text","path":"artifact/data.json","content":"{\\\"ok\\\":true}"},{"type":"syntax_check","kind":"json","paths":["artifact/data.json"]},{"type":"read_text","path":"artifact/data.json"}]}})
blocked_ok, blocked = motor.execute({"action":"work.execute","payload":{"jobId":"blocked-job","steps":[{"type":"write_text","path":"../escape.txt","content":"no"}]}})
print(json.dumps({"ok":ok,"result":result,"blockedOk":blocked_ok,"blocked":blocked,"escaped":(root / "escape.txt").exists()}))
`
  try {
    const motorPath = path.resolve(import.meta.dirname, "../motor/self_root_motor.py");
    const { stdout } = await execFileAsync("python3", ["-c", script, motorPath, directory]);
    const result = JSON.parse(stdout);
    assert.equal(result.ok, true);
    assert.equal(result.result.exitCode, 0);
    assert.equal(result.result.steps.length, 4);
    assert.equal(result.result.steps[2].ok, true);
    assert.equal(result.result.steps[3].text, '{"ok":true}');
    assert.equal(result.blockedOk, false);
    assert.equal(result.blocked.exitCode, 1);
    assert.equal(result.escaped, false);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});


test("machine evidence ledger append is durable and idempotent", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "motor-evidence-test-"));
  const script = `
import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location("motor", sys.argv[1])
motor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(motor)
root = pathlib.Path(sys.argv[2])
motor.ROOT = root
motor.STATE_DIR = root / "state"
motor.EVIDENCE_DIR = root / "evidence"
motor.EVIDENCE_LEDGER_FILE = motor.EVIDENCE_DIR / "evidence-ledger-v1.jsonl"
motor.EVIDENCE_INDEX_FILE = motor.EVIDENCE_DIR / "event-index-v1.json"
motor.STATE_SNAPSHOT_FILE = motor.STATE_DIR / "materialized-work-state-v1.json"
motor.LEGACY_STATE_SNAPSHOT_FILE = motor.STATE_DIR / "agent-core-snapshot-v1.json"
event = {
  "schema_version": "1.0",
  "event_id": "event-1",
  "correlation_id": "job-1",
  "parent_event_id": None,
  "event_type": "work.test",
  "occurred_at": "2026-09-30T16:00:00.000Z",
  "recorded_at": "2026-09-30T16:00:00.000Z",
  "source": "unit-test",
  "strategy_id": None,
  "strategy_version": None,
  "payload": {"ok": True},
  "provenance": {
    "software_version": "0.19.0",
    "config_hash": "cfg",
    "dataset_version": None,
    "ledger_seq": 1,
    "previous_event_hash": None,
    "event_hash": "hash-1"
  }
}
first_ok, first = motor.execute({"action": "evidence.ledger.append", "payload": {"events": [event]}})
second_ok, second = motor.execute({"action": "evidence.ledger.append", "payload": {"events": [event]}})
status_ok, status = motor.execute({"action": "evidence.ledger.status", "payload": {}})
read_ok, read = motor.execute({"action": "evidence.ledger.read", "payload": {"afterSeq": 0, "limit": 10}})
print(json.dumps({
  "firstOk": first_ok,
  "first": first,
  "secondOk": second_ok,
  "second": second,
  "statusOk": status_ok,
  "status": status,
  "readOk": read_ok,
  "read": read
}))
`;
  try {
    const motorPath = path.resolve(import.meta.dirname, "../motor/self_root_motor.py");
    const { stdout } = await execFileAsync("python3", ["-c", script, motorPath, directory]);
    const result = JSON.parse(stdout);
    assert.equal(result.firstOk, true);
    assert.equal(result.first.accepted, 1);
    assert.equal(result.secondOk, true);
    assert.equal(result.second.duplicates, 1);
    assert.equal(result.statusOk, true);
    assert.equal(result.status.count, 1);
    assert.equal(result.readOk, true);
    assert.equal(result.read.events.length, 1);
    assert.equal(result.read.events[0].event_id, "event-1");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
