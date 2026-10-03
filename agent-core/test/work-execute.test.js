import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const token = "test-runtime-token";
const motorToken = "test-motor-token";

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function startRuntime(port, stateDir, extraEnv = {}) {
  const deadUrl = "http://127.0.0.1:1/missing";
  const child = spawn(process.execPath, ["src/index.js"], {
    cwd: path.resolve(import.meta.dirname, ".."),
    env: {
      ...process.env,
      PORT: String(port),
      RUNTIME_EVENT_TOKEN: token,
      MOTOR_AGENT_TOKEN: motorToken,
      AGENT_STATE_DIR: stateDir,
      OUTBOUND_WORK_ENABLED: "true",
      FINANCIAL_ACTIONS_ENABLED: "false",
      TASKBOUNTY_FEED_URL: deadUrl,
      BASEDAGENTS_FEED_URL: deadUrl,
      BASEDAGENTS_IDENTITY_BACKUP_URL: deadUrl,
      BASE_WALLET_BACKUP_URL: deadUrl,
      AGENTSOUK_IDENTITY_BACKUP_URL: deadUrl,
      SWARMSPOT_IDENTITY_BACKUP_URL: deadUrl,
      AGENTCHAIN_IDENTITY_BACKUP_URL: deadUrl,
      CLAWLANCER_IDENTITY_BACKUP_URL: deadUrl,
      AGENTLINE_IDENTITY_BACKUP_URL: deadUrl,
      BASEDAGENTS_BOOTSTRAP: "false",
      BASE_WALLET_BOOTSTRAP: "false",
      AGENTSOUK_BOOTSTRAP: "false",
      SWARMSPOT_BOOTSTRAP: "false",
      AGENTCHAIN_BOOTSTRAP: "false",
      CLAWLANCER_BOOTSTRAP: "false",
      AGENTLINE_BOOTSTRAP: "false",
      AGENTMAIL_WEBHOOK_PROVISION: "false",
      ...extraEnv,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let logs = "";
  child.stdout.on("data", (chunk) => { logs += chunk; });
  child.stderr.on("data", (chunk) => { logs += chunk; });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 80; i += 1) {
    if (child.exitCode !== null) throw new Error(`runtime_exited:${child.exitCode}\n${logs}`);
    try {
      const response = await fetch(base + "/health");
      if (response.ok) return { child, base };
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  child.kill("SIGKILL");
  throw new Error("runtime_start_timeout\n" + logs);
}

async function stopRuntime(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await Promise.race([
    new Promise((resolve) => child.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 3000)),
  ]);
  if (child.exitCode === null) child.kill("SIGKILL");
}

async function api(base, pathname, { method = "GET", body } = {}) {
  const response = await fetch(base + pathname, {
    method,
    headers: {
      authorization: "Bearer " + token,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  assert.ok(response.ok, response.status + ": " + JSON.stringify(payload));
  return payload;
}

async function nextMotorCommand(base, action) {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const response = await fetch(base + "/v1/motor/poll", {
      headers: { authorization: "Bearer " + motorToken },
    });
    assert.equal(response.status, 200);
    const { command } = await response.json();
    if (!command) continue;
    if (command.action === action) return command;
    const ack = await fetch(base + "/v1/motor/ack", {
      method: "POST",
      headers: {
        authorization: "Bearer " + motorToken,
        "content-type": "application/json",
      },
      body: JSON.stringify({ id: command.id, ok: true, result: { exists: false } }),
    });
    assert.equal(ack.status, 200);
  }
  throw new Error("motor_command_not_found:" + action);
}

test("work dispatch leases, executes through motor, and reconciles result", async () => {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "agent-work-execute-test-"));
  const port = await freePort();
  let runtime;
  try {
    runtime = await startRuntime(port, stateDir);
    await api(runtime.base, "/v1/work/items", {
      method: "POST",
      body: {
        provider: "testmarket",
        externalId: "motor-job",
        title: "Bounded coding task",
        description: "Write and validate a local JSON artifact",
        state: "QUALIFIED",
        payoutUsd: 10,
        expectedNetUsd: 10,
        paymentConfidence: 1,
        scopeConfidence: 1,
        estimatedMinutes: 15,
      },
    });

    const dispatched = await api(runtime.base, "/v1/work/dispatch", {
      method: "POST",
      body: {
        jobId: "motor-job-1",
        workKey: "testmarket:motor-job",
        title: "Create validated artifact",
        instructions: "Create the requested local artifact only.",
        successState: "SUBMITTED",
        steps: [
          { type: "mkdir", path: "artifact" },
          { type: "write_text", path: "artifact/result.json", content: "{\"ok\":true}" },
          { type: "syntax_check", kind: "json", paths: ["artifact/result.json"] },
        ],
      },
    });
    assert.equal(dispatched.item.state, "WORKING");
    assert.ok(dispatched.lease.leaseId);

    const command = await nextMotorCommand(runtime.base, "work.execute");
    assert.equal(command.payload.jobId, "motor-job-1");
    assert.equal(command.payload.workKey, "testmarket:motor-job");
    assert.equal(command.payload.leaseId, dispatched.lease.leaseId);

    const ack = await fetch(runtime.base + "/v1/motor/ack", {
      method: "POST",
      headers: {
        authorization: "Bearer " + motorToken,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        id: command.id,
        ok: true,
        result: {
          exitCode: 0,
          jobId: "motor-job-1",
          summary: "bounded artifact completed",
          artifacts: ["artifact/result.json"],
        },
      }),
    });
    assert.equal(ack.status, 200);

    const work = await api(runtime.base, "/v1/work");
    const item = work.items.find((x) => x.key === "testmarket:motor-job");
    assert.equal(item.state, "SUBMITTED");
    assert.equal(item.execution.checkpoint.phase, "submitted");

    const reports = await api(runtime.base, "/v1/reports");
    assert.equal(reports.results, 1);
    assert.match(reports.pending[0].summary, /bounded artifact completed/);
  } finally {
    if (runtime?.child) await stopRuntime(runtime.child);
    await rm(stateDir, { recursive: true, force: true });
  }
});

test("motor prioritizes non-ephemeral commands over mirror backlog and reports liveness", async () => {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "agent-motor-priority-test-"));
  const port = await freePort();
  let runtime;
  try {
    runtime = await startRuntime(port, stateDir, {
      EVIDENCE_MOTOR_MIRROR_ENABLED: "true",
      MOTOR_ONLINE_WINDOW_MS: "30000",
    });
    for (let i = 0; i < 5; i += 1) {
      await api(runtime.base, "/v1/motor/enqueue", {
        method: "POST",
        body: {
          action: "evidence.ledger.append",
          externalId: "mirror-" + i,
          payload: { events: [{ event_id: "mirror-" + i }] },
        },
      });
    }
    await api(runtime.base, "/v1/motor/enqueue", {
      method: "POST",
      body: { action: "system.ping", externalId: "priority-ping" },
    });

    const before = await (await fetch(runtime.base + "/health")).json();
    assert.equal(before.motor.online, false);
    assert.ok(before.motor.pendingByAction["evidence.ledger.append"] >= 5);
    assert.equal(before.motor.pendingByAction["system.ping"], 1);
    assert.equal(before.motor.evidenceMirrorDegraded, true);

    const poll = await fetch(runtime.base + "/v1/motor/poll", {
      headers: { authorization: "Bearer " + motorToken },
    });
    assert.equal(poll.status, 200);
    const { command } = await poll.json();
    assert.equal(command.action, "system.ping");

    const afterPoll = await (await fetch(runtime.base + "/health")).json();
    assert.equal(afterPoll.motor.online, true);
    assert.ok(afterPoll.motor.lastPollAt);
    const ack = await fetch(runtime.base + "/v1/motor/ack", {
      method: "POST",
      headers: {
        authorization: "Bearer " + motorToken,
        "content-type": "application/json",
      },
      body: JSON.stringify({ id: command.id, ok: true, result: { pong: true } }),
    });
    assert.equal(ack.status, 200);
    const afterAck = await (await fetch(runtime.base + "/health")).json();
    assert.ok(afterAck.motor.lastAckAt);
  } finally {
    if (runtime?.child) await stopRuntime(runtime.child);
    await rm(stateDir, { recursive: true, force: true });
  }
});

test("ephemeral mirror bookkeeping stays out of durable snapshots without extra checkpoints", async () => {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "agent-motor-durable-test-"));
  const port = await freePort();
  let runtime;
  try {
    runtime = await startRuntime(port, stateDir, {
      EVIDENCE_MOTOR_MIRROR_ENABLED: "true",
    });
    await new Promise((resolve) => setTimeout(resolve, 600));
    const before = await (await fetch(runtime.base + "/health")).json();

    await api(runtime.base, "/v1/motor/enqueue", {
      method: "POST",
      body: { action: "system.ping", externalId: "durable-ping" },
    });
    await api(runtime.base, "/v1/motor/enqueue", {
      method: "POST",
      body: {
        action: "evidence.ledger.append",
        externalId: "durable-mirror",
        payload: { events: [{ event_id: "durable-mirror" }] },
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 2800));
    const after = await (await fetch(runtime.base + "/health")).json();
    assert.equal(after.continuity.evidence.saveCount - before.continuity.evidence.saveCount, 1);
    const materialized = JSON.parse(
      await readFile(path.join(stateDir, "materialized-state-v1.json"), "utf8"),
    );
    const actions = (materialized.state.motorQueue || []).map((item) => item.action);
    assert.ok(actions.includes("system.ping"));
    assert.equal(actions.includes("evidence.ledger.append"), false);
    assert.equal(actions.includes("state.snapshot.write"), false);
  } finally {
    if (runtime?.child) await stopRuntime(runtime.child);
    await rm(stateDir, { recursive: true, force: true });
  }
});

