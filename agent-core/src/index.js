import http from "node:http";
import { randomUUID } from "node:crypto";

const PORT = Number(process.env.PORT || 3000);
const runtimeId = process.env.RUNTIME_ID || "continuity-agent-core";
const agentEmail = process.env.AGENT_EMAIL || "oldcraft541@agentmail.to";
const eventToken = process.env.RUNTIME_EVENT_TOKEN || process.env.BROWSER_WORKER_TOKEN || "";
const financialActionsEnabled = process.env.FINANCIAL_ACTIONS_ENABLED === "true";
const outboundWorkEnabled = process.env.OUTBOUND_WORK_ENABLED === "true";

const bootId = randomUUID();
const startedAt = new Date().toISOString();
let tickCount = 0;
let lastTickAt = startedAt;
const recentEvents = [];

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(data),
    "cache-control": "no-store"
  });
  res.end(data);
}

function authorized(req) {
  if (!eventToken) return false;
  const auth = req.headers.authorization || "";
  return auth === `Bearer ${eventToken}`;
}

async function readJson(req, maxBytes = 65536) {
  let total = 0;
  const chunks = [];
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) throw new Error("payload_too_large");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function rememberEvent(evt) {
  recentEvents.push(evt);
  while (recentEvents.length > 50) recentEvents.shift();
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  if (req.method === "GET" && url.pathname === "/health") {
    return json(res, 200, {
      ok: true,
      runtime: runtimeId,
      version: "0.1.0",
      bootId,
      startedAt,
      lastTickAt
    });
  }

  if (req.method === "GET" && url.pathname === "/ready") {
    return json(res, eventToken ? 200 : 503, {
      ready: Boolean(eventToken),
      runtime: runtimeId,
      agentEmail,
      financialActionsEnabled,
      outboundWorkEnabled,
      eventIngressConfigured: Boolean(eventToken)
    });
  }

  if (req.method === "GET" && url.pathname === "/v1/status") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    return json(res, 200, {
      runtime: runtimeId,
      version: "0.1.0",
      bootId,
      startedAt,
      tickCount,
      lastTickAt,
      agentEmail,
      policy: {
        financialActionsEnabled,
        outboundWorkEnabled,
        maxAutonomousSpendUsd: 0,
        speculativeTradingEnabled: false
      },
      integrations: {
        agentMail: "not_configured_in_runtime",
        circle: "not_configured_in_runtime",
        stripe: "external_adapter_only",
        continuityJournal: "adapter_pending"
      },
      recentEvents
    });
  }

  if (req.method === "POST" && url.pathname === "/v1/events") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req);
      const allowedTypes = new Set([
        "manual.test",
        "schedule.tick",
        "email.received",
        "job.available",
        "job.updated"
      ]);
      if (!allowedTypes.has(body.type)) {
        return json(res, 400, { error: "unsupported_event_type" });
      }
      const event = {
        id: randomUUID(),
        receivedAt: new Date().toISOString(),
        type: body.type,
        source: typeof body.source === "string" ? body.source.slice(0, 120) : "unknown",
        externalId: typeof body.externalId === "string" ? body.externalId.slice(0, 240) : null
      };
      rememberEvent(event);
      return json(res, 202, { accepted: true, event });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
  }

  return json(res, 404, { error: "not_found" });
});

const heartbeat = setInterval(() => {
  tickCount += 1;
  lastTickAt = new Date().toISOString();
}, 60_000);
heartbeat.unref();

server.listen(PORT, "0.0.0.0", () => {
  console.log(JSON.stringify({
    event: "runtime.started",
    runtime: runtimeId,
    version: "0.1.0",
    bootId,
    port: PORT,
    financialActionsEnabled,
    outboundWorkEnabled
  }));
});

function shutdown(signal) {
  console.log(JSON.stringify({ event: "runtime.stopping", signal, bootId }));
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
