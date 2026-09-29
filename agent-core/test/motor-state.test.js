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

