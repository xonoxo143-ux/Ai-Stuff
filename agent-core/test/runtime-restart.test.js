import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const token = "test-runtime-token";

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

async function startRuntime({ port, stateDir }) {
  const deadUrl = "http://127.0.0.1:1/missing";
  const child = spawn(process.execPath, ["src/index.js"], {
    cwd: path.resolve(import.meta.dirname, ".."),
    env: {
      ...process.env,
      PORT: String(port),
      RUNTIME_EVENT_TOKEN: token,
      MOTOR_AGENT_TOKEN: "test-motor-token",
      AGENTMAIL_WEBHOOK_TOKEN: "test-agentmail-webhook-token",
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
      const response = await fetch(`${base}/health`);
      if (response.ok) return { child, base, logs: () => logs };
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  child.kill("SIGKILL");
  throw new Error(`runtime_start_timeout\n${logs}`);
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
  const response = await fetch(`${base}${pathname}`, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  assert.ok(response.ok, `${response.status}: ${JSON.stringify(payload)}`);
  return payload;
}

test("work lifecycle, payment proof, reports, and state survive restart", async () => {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "agent-runtime-test-"));
  const port = await freePort();
  let runtime;
  try {
    runtime = await startRuntime({ port, stateDir });
    const webhookResponse = await fetch(`${runtime.base}/integrations/agentmail/webhook`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-self-root-webhook-token": "test-agentmail-webhook-token",
      },
      body: JSON.stringify({
        type: "event",
        event_type: "message.received",
        event_id: "mail-event-1",
        message: {
          inbox_id: "inbox-test",
          message_id: "message-test",
          from: "oldcraft541@agentmail.to",
          to: ["oldcraft541@agentmail.to"],
          subject: "SELF-ROOT COMMAND: system.ping",
        },
      }),
    });
    assert.equal(webhookResponse.status, 202);
    let observedPing = false;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const motorPoll = await fetch(`${runtime.base}/v1/motor/poll`, {
        headers: { authorization: "Bearer test-motor-token" },
      });
      assert.equal(motorPoll.status, 200);
      const { command } = await motorPoll.json();
      if (!command) break;
      if (command.action === "system.ping") {
        observedPing = true;
        break;
      }
      const ack = await fetch(`${runtime.base}/v1/motor/ack`, {
        method: "POST",
        headers: {
          authorization: "Bearer test-motor-token",
          "content-type": "application/json",
        },
        body: JSON.stringify({ id: command.id, ok: true, result: { exists: false } }),
      });
      assert.equal(ack.status, 200);
    }
    assert.equal(observedPing, true);

    const itemBody = {
      provider: "testmarket",
      externalId: "job-1",
      title: "Bounded paid test job",
      state: "QUALIFIED",
      payoutUsd: 10,
      expectedNetUsd: 10,
      paymentConfidence: 1,
      scopeConfidence: 1,
      estimatedMinutes: 15,
    };
    await api(runtime.base, "/v1/work/items", { method: "POST", body: itemBody });
    const leased = await api(runtime.base, "/v1/work/lease", {
      method: "POST",
      body: { key: "testmarket:job-1", workerId: "test-worker", idempotencyKey: "lease-1" },
    });
    await api(runtime.base, "/v1/work/checkpoints", {
      method: "POST",
      body: {
        key: "testmarket:job-1",
        leaseId: leased.lease.leaseId,
        phase: "implementation",
        detail: "tests passing",
        idempotencyKey: "checkpoint-1",
      },
    });
    await api(runtime.base, "/v1/work/transitions", {
      method: "POST",
      body: {
        key: "testmarket:job-1",
        leaseId: leased.lease.leaseId,
        state: "WORKING",
        idempotencyKey: "working-1",
      },
    });
    await api(runtime.base, "/v1/work/transitions", {
      method: "POST",
      body: { key: "testmarket:job-1", leaseId: leased.lease.leaseId, state: "SUBMITTED" },
    });
    await api(runtime.base, "/v1/work/transitions", {
      method: "POST",
      body: { key: "testmarket:job-1", leaseId: leased.lease.leaseId, state: "ACCEPTED" },
    });
    await api(runtime.base, "/v1/work/transitions", {
      method: "POST",
      body: {
        key: "testmarket:job-1",
        state: "PAID",
        realizedUsd: 10,
        paymentProof: {
          source: "testmarket-api",
          reference: "payment-1",
          status: "settled",
          amountUsd: 10,
        },
      },
    });
    await stopRuntime(runtime.child);

    runtime = await startRuntime({ port, stateDir });
    const work = await api(runtime.base, "/v1/work");
    const restored = work.items.find((item) => item.key === "testmarket:job-1");
    assert.equal(restored.state, "PAID");
    assert.equal(restored.paymentProof.reference, "payment-1");
    assert.equal(work.providerStats.testmarket.paid, 1);
    const reports = await api(runtime.base, "/v1/reports");
    assert.equal(reports.results, 1);
  } finally {
    if (runtime?.child) await stopRuntime(runtime.child);
    await rm(stateDir, { recursive: true, force: true });
  }
});
