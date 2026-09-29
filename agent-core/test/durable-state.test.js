import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { createDurableState } from "../src/durable-state.js";

test("durable state atomically saves, restores, and journals events", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "agent-state-test-"));
  try {
    const store = createDurableState({ directory, debounceMs: 5 });
    const initial = await store.init();
    assert.equal(initial.recovered, false);

    await store.save({ workLedger: [["provider:1", { state: "WORKING" }]] }, "test");
    await store.appendEvent({ id: "event-1", type: "work.test" });
    await store.flush();

    const restarted = createDurableState({ directory });
    const loaded = await restarted.init();
    assert.equal(loaded.recovered, true);
    assert.equal(loaded.snapshot.workLedger[0][1].state, "WORKING");
    assert.match(await readFile(path.join(directory, "events-v1.jsonl"), "utf8"), /work\.test/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

