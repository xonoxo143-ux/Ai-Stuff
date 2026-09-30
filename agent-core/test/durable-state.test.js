import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { createDurableState } from "../src/durable-state.js";

function store(directory, options = {}) {
  return createDurableState({
    directory,
    debounceMs: 5,
    softwareVersion: "test-0.19.0",
    configHash: "config-test-hash",
    ...options,
  });
}

test("evidence ledger is canonical and materialized state restores normally", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "agent-evidence-test-"));
  try {
    const first = store(directory);
    const initial = await first.init();
    assert.equal(initial.recovered, false);

    await first.save({ workLedger: [["provider:1", { state: "WORKING" }]] }, "test");
    const record = await first.appendEvent({
      id: "event-1",
      type: "work.test",
      source: "unit-test",
      externalId: "provider:1",
      payload: { result: "ok" },
    });
    assert.equal(record.schema_version, "1.0");
    assert.equal(record.event_type, "work.test");
    assert.equal(record.correlation_id, "provider:1");
    assert.equal(record.provenance.software_version, "test-0.19.0");
    assert.equal(record.provenance.config_hash, "config-test-hash");
    await first.flush();

    const restarted = store(directory);
    const loaded = await restarted.init();
    assert.equal(loaded.recovered, true);
    assert.equal(loaded.recoveredFrom, "materialized_cache");
    assert.equal(loaded.snapshot.workLedger[0][1].state, "WORKING");

    const ledger = await readFile(path.join(directory, "evidence-ledger-v1.jsonl"), "utf8");
    assert.match(ledger, /continuity\.state_checkpoint/);
    assert.match(ledger, /work\.test/);
    const verification = await restarted.verify();
    assert.equal(verification.ok, true);
    assert.ok(verification.eventCount >= 2);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("materialized cache rebuilds from the append-only evidence ledger", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "agent-evidence-rebuild-"));
  try {
    const first = store(directory);
    await first.init();
    await first.save({
      workLedger: [["provider:2", { state: "SUBMITTED" }]],
      marker: "ledger-rebuild",
    }, "checkpoint");
    await first.flush();

    await unlink(path.join(directory, "materialized-state-v1.json"));

    const restarted = store(directory);
    const loaded = await restarted.init();
    assert.equal(loaded.recovered, true);
    assert.equal(loaded.recoveredFrom, "evidence_ledger");
    assert.equal(loaded.snapshot.marker, "ledger-rebuild");
    assert.equal(loaded.snapshot.workLedger[0][1].state, "SUBMITTED");

    const rebuilt = JSON.parse(
      await readFile(path.join(directory, "materialized-state-v1.json"), "utf8"),
    );
    assert.equal(rebuilt.schema, 2);
    assert.equal(rebuilt.state.marker, "ledger-rebuild");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("legacy snapshot migrates without overwriting legacy evidence", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "agent-evidence-migration-"));
  try {
    const legacySnapshot = {
      schema: 1,
      capturedAt: "2026-09-29T20:15:00.000Z",
      reason: "legacy_test",
      state: {
        workLedger: [["legacy:1", { state: "WORKING" }]],
        marker: "legacy-state",
      },
    };
    const legacyEvent =
      JSON.stringify({
        schema: 1,
        recordedAt: "2026-09-29T20:16:00.000Z",
        id: "legacy-event-1",
        type: "work.legacy",
      }) + "\n";
    await writeFile(
      path.join(directory, "agent-state-v1.json"),
      JSON.stringify(legacySnapshot) + "\n",
    );
    await writeFile(path.join(directory, "events-v1.jsonl"), legacyEvent);

    const migrated = store(directory);
    const loaded = await migrated.init();
    assert.equal(loaded.recovered, true);
    assert.equal(loaded.recoveredFrom, "legacy_snapshot_migration");
    assert.equal(loaded.snapshot.marker, "legacy-state");

    const events = await migrated.readEvents({ limit: 10 });
    assert.equal(events.at(-1).event_type, "continuity.legacy_snapshot_imported");
    assert.equal(events.at(-1).payload.legacy_event_log.lines, 1);
    assert.equal(events.at(-1).payload.migration_policy, "preserve_legacy_files_read_only");

    assert.match(
      await readFile(path.join(directory, "agent-state-v1.json"), "utf8"),
      /legacy-state/,
    );
    assert.match(
      await readFile(path.join(directory, "events-v1.jsonl"), "utf8"),
      /work\.legacy/,
    );
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
