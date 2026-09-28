import http from "node:http";
import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";

const PORT = Number(process.env.PORT || 3000);
const VERSION = "0.2.0";
const runtimeId = process.env.RUNTIME_ID || "continuity-agent-core";
const agentEmail = process.env.AGENT_EMAIL || "oldcraft541@agentmail.to";
const eventToken = process.env.RUNTIME_EVENT_TOKEN || process.env.BROWSER_WORKER_TOKEN || "";
const financialActionsEnabled = process.env.FINANCIAL_ACTIONS_ENABLED === "true";
const outboundWorkEnabled = process.env.OUTBOUND_WORK_ENABLED === "true";
const operatingFloatTargetUsd = Number(process.env.OPERATING_FLOAT_TARGET_USD || 100);

const taskBountyFeedUrl =
  process.env.TASKBOUNTY_FEED_URL ||
  "https://www.task-bounty.com/api/v1/tasks?state=open&limit=100";
const taskBountyPollMs = Math.max(
  30_000,
  Number(process.env.TASKBOUNTY_POLL_MS || 60_000),
);
const taskBountyWebhookSecret = process.env.TASKBOUNTY_WEBHOOK_SECRET || "";
const taskFeedSelfTest = process.env.TASK_FEED_SELF_TEST === "true";

const bootId = randomUUID();
const startedAt = new Date().toISOString();
let tickCount = 0;
let lastTickAt = startedAt;
const recentEvents = [];
const taskQueue = new Map();

const feedState = {
  provider: "taskbounty",
  mode: "public_feed_plus_optional_signed_webhook",
  lastAttemptAt: null,
  lastSuccessAt: null,
  lastError: null,
  syncCount: 0,
  discoveredCount: 0,
  candidateCount: 0,
  reviewCount: 0,
  rejectedCount: 0,
  webhookConfigured: Boolean(taskBountyWebhookSecret),
  pollMs: taskBountyPollMs,
};

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(data),
    "cache-control": "no-store",
  });
  res.end(data);
}

function authorized(req) {
  if (!eventToken) return false;
  const auth = req.headers.authorization || "";
  return auth === `Bearer ${eventToken}`;
}

async function readBody(req, maxBytes = 131072) {
  let total = 0;
  const chunks = [];
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) throw new Error("payload_too_large");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

async function readJson(req, maxBytes = 131072) {
  const raw = await readBody(req, maxBytes);
  if (!raw.length) return {};
  return JSON.parse(raw.toString("utf8"));
}

function rememberEvent(evt) {
  recentEvents.push(evt);
  while (recentEvents.length > 100) recentEvents.shift();
}

function safeHttpsUrl(value, allowedHostSuffix = null) {
  if (typeof value !== "string") return null;
  try {
    const u = new URL(value);
    if (u.protocol !== "https:") return null;
    if (allowedHostSuffix && !(u.hostname === allowedHostSuffix || u.hostname.endsWith("." + allowedHostSuffix))) {
      return null;
    }
    return u.toString();
  } catch {
    return null;
  }
}

function normalizeTask(raw, source = "taskbounty_public_feed") {
  if (!raw || typeof raw !== "object") return null;

  const taskId = String(raw.task_id || raw.id || "").trim();
  if (!taskId || taskId.length > 200) return null;

  const title = String(raw.title || "").trim().slice(0, 500);
  const bountyCentsRaw =
    raw.bounty_cents ??
    raw.amount_cents ??
    raw.reward_cents ??
    (Number.isFinite(Number(raw.bounty)) ? Math.round(Number(raw.bounty) * 100) : null);
  const bountyCents = Number.isFinite(Number(bountyCentsRaw))
    ? Math.max(0, Math.round(Number(bountyCentsRaw)))
    : null;

  const githubRepoUrl = safeHttpsUrl(
    raw.github_repo_url || raw.repo_url || raw.repository_url,
    "github.com",
  );
  const githubIssueUrl = safeHttpsUrl(
    raw.github_issue_url || raw.issue_url,
    "github.com",
  );

  return {
    provider: "taskbounty",
    source,
    taskId,
    title,
    bountyCents,
    solverNetCents: bountyCents == null ? null : Math.floor(bountyCents * 0.8),
    githubRepoUrl,
    githubIssueUrl,
    createdAt: typeof raw.created_at === "string" ? raw.created_at.slice(0, 80) : null,
    complexity: String(raw.complexity_tag || raw.complexity || "").trim().slice(0, 80) || null,
    language: String(raw.language || "").trim().slice(0, 80) || null,
  };
}

function evaluateTask(task) {
  const reasons = [];
  let score = 50;
  let status = "candidate";

  if (task.bountyCents == null) {
    status = "manual_review";
    reasons.push("missing_bounty_amount");
  } else if (task.bountyCents < 1000) {
    status = "rejected";
    reasons.push("gross_bounty_below_10_usd");
  } else {
    if (task.solverNetCents >= 4000) score += 15;
    else if (task.solverNetCents >= 2000) score += 10;
    else score += 5;
  }

  if (!task.githubIssueUrl || !task.githubRepoUrl) {
    status = status === "rejected" ? status : "manual_review";
    reasons.push("missing_github_issue_or_repo");
  } else {
    score += 10;
  }

  const lang = (task.language || "").toLowerCase();
  if (["javascript", "typescript", "python", "go", "rust", "java", "c#", "c++"].includes(lang)) {
    score += 10;
  }

  const complexity = (task.complexity || "").toLowerCase();
  if (/(easy|small|low|xs|s)/.test(complexity)) score += 10;
  if (/(hard|large|high|xl)/.test(complexity)) score -= 15;

  const riskText = `${task.title} ${task.complexity || ""}`.toLowerCase();
  const highRiskPatterns = [
    "malware",
    "phishing",
    "credential theft",
    "steal credentials",
    "ransomware",
    "bypass authentication",
    "exploit production",
    "weapon",
    "spyware",
  ];
  if (highRiskPatterns.some((p) => riskText.includes(p))) {
    status = "manual_review";
    reasons.push("potentially_sensitive_or_harmful_scope");
    score = Math.min(score, 40);
  }

  if (status === "candidate" && score < 55) {
    status = "manual_review";
    reasons.push("low_automatic_confidence");
  }

  if (status === "candidate") reasons.push("passes_initial_economic_and_scope_filter");

  return {
    status,
    score: Math.max(0, Math.min(100, score)),
    reasons,
    nextAction:
      status === "candidate"
        ? "await_ai_feasibility_review"
        : status === "manual_review"
          ? "hold_for_review"
          : "ignore",
  };
}

function recomputeFeedCounts() {
  let candidates = 0;
  let review = 0;
  let rejected = 0;
  for (const item of taskQueue.values()) {
    if (item.evaluation.status === "candidate") candidates += 1;
    else if (item.evaluation.status === "manual_review") review += 1;
    else if (item.evaluation.status === "rejected") rejected += 1;
  }
  feedState.candidateCount = candidates;
  feedState.reviewCount = review;
  feedState.rejectedCount = rejected;
  feedState.discoveredCount = taskQueue.size;
}

function ingestTask(raw, source) {
  const task = normalizeTask(raw, source);
  if (!task) return null;

  const previous = taskQueue.get(task.taskId);
  const evaluation = evaluateTask(task);
  const record = {
    ...task,
    evaluation,
    firstSeenAt: previous?.firstSeenAt || new Date().toISOString(),
    lastSeenAt: new Date().toISOString(),
  };
  taskQueue.set(task.taskId, record);
  recomputeFeedCounts();

  if (!previous || JSON.stringify(previous.evaluation) !== JSON.stringify(evaluation)) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: previous ? "job.updated" : "job.available",
      source,
      externalId: task.taskId,
      status: evaluation.status,
      score: evaluation.score,
    });
  }
  return record;
}

function extractTasks(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  if (Array.isArray(payload.tasks)) return payload.tasks;
  if (Array.isArray(payload.data)) return payload.data;
  if (payload.payload && typeof payload.payload === "object") return [payload.payload];
  if (payload.task && typeof payload.task === "object") return [payload.task];
  if (payload.task_id || payload.id) return [payload];
  return [];
}

async function syncTaskBounty() {
  feedState.lastAttemptAt = new Date().toISOString();
  try {
    const response = await fetch(taskBountyFeedUrl, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) throw new Error(`taskbounty_http_${response.status}`);
    const payload = await response.json();
    const tasks = extractTasks(payload);
    for (const task of tasks) ingestTask(task, "taskbounty_public_feed");

    feedState.lastSuccessAt = new Date().toISOString();
    feedState.lastError = null;
    feedState.syncCount += 1;
    recomputeFeedCounts();
  } catch (err) {
    feedState.lastError = err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

function verifyTaskBountySignature(rawBody, provided) {
  if (!taskBountyWebhookSecret || typeof provided !== "string") return false;
  const expectedHex = createHmac("sha256", taskBountyWebhookSecret).update(rawBody).digest("hex");
  const normalized = provided.replace(/^sha256=/i, "").trim().toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(normalized)) return false;
  const a = Buffer.from(expectedHex, "hex");
  const b = Buffer.from(normalized, "hex");
  return a.length === b.length && timingSafeEqual(a, b);
}

function taskFeedSummary() {
  return {
    provider: feedState.provider,
    mode: feedState.mode,
    lastAttemptAt: feedState.lastAttemptAt,
    lastSuccessAt: feedState.lastSuccessAt,
    lastError: feedState.lastError,
    syncCount: feedState.syncCount,
    discoveredCount: feedState.discoveredCount,
    candidateCount: feedState.candidateCount,
    reviewCount: feedState.reviewCount,
    rejectedCount: feedState.rejectedCount,
    webhookConfigured: feedState.webhookConfigured,
    pollMs: feedState.pollMs,
  };
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  if (req.method === "GET" && url.pathname === "/health") {
    return json(res, 200, {
      ok: true,
      runtime: runtimeId,
      version: VERSION,
      bootId,
      startedAt,
      lastTickAt,
      taskFeed: taskFeedSummary(),
    });
  }

  if (req.method === "GET" && url.pathname === "/ready") {
    const ready = Boolean(eventToken) && Boolean(feedState.lastSuccessAt || !feedState.lastError);
    return json(res, ready ? 200 : 503, {
      ready,
      runtime: runtimeId,
      agentEmail,
      financialActionsEnabled,
      outboundWorkEnabled,
      operatingFloatTargetUsd,
      eventIngressConfigured: Boolean(eventToken),
      taskFeed: taskFeedSummary(),
    });
  }

  if (req.method === "GET" && url.pathname === "/v1/status") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    return json(res, 200, {
      runtime: runtimeId,
      version: VERSION,
      bootId,
      startedAt,
      tickCount,
      lastTickAt,
      agentEmail,
      policy: {
        financialActionsEnabled,
        outboundWorkEnabled,
        maxAutonomousSpendUsd: 0,
        operatingFloatTargetUsd,
        surplusPolicy: "settled_net_revenue_above_operating_float_to_project_funding_pool",
        speculativeTradingEnabled: false,
      },
      integrations: {
        taskBounty: taskFeedSummary(),
        agentMail: "not_configured_in_runtime",
        circle: "not_configured_in_runtime",
        stripe: "external_adapter_only",
        continuityJournal: "adapter_pending",
      },
      queue: Array.from(taskQueue.values()).slice(-100),
      recentEvents,
    });
  }

  if (req.method === "POST" && url.pathname === "/integrations/taskbounty") {
    if (!taskBountyWebhookSecret) {
      return json(res, 503, { error: "taskbounty_webhook_not_configured" });
    }
    try {
      const rawBody = await readBody(req);
      if (!verifyTaskBountySignature(rawBody, req.headers["x-taskbounty-signature"])) {
        return json(res, 401, { error: "invalid_signature" });
      }
      const payload = JSON.parse(rawBody.toString("utf8"));
      const tasks = extractTasks(payload);
      const accepted = tasks.map((task) => ingestTask(task, "taskbounty_signed_webhook")).filter(Boolean);
      return json(res, 202, {
        accepted: accepted.length,
        taskIds: accepted.map((x) => x.taskId),
      });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
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
        "job.updated",
      ]);
      if (!allowedTypes.has(body.type)) {
        return json(res, 400, { error: "unsupported_event_type" });
      }
      const event = {
        id: randomUUID(),
        receivedAt: new Date().toISOString(),
        type: body.type,
        source: typeof body.source === "string" ? body.source.slice(0, 120) : "unknown",
        externalId: typeof body.externalId === "string" ? body.externalId.slice(0, 240) : null,
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

const taskFeedTimer = setInterval(() => {
  void syncTaskBounty();
}, taskBountyPollMs);
taskFeedTimer.unref();

if (taskFeedSelfTest) {
  ingestTask(
    {
      task_id: "self-test-task",
      title: "Synthetic TypeScript regression fix",
      bounty_cents: 2500,
      github_repo_url: "https://github.com/example/example",
      github_issue_url: "https://github.com/example/example/issues/1",
      complexity_tag: "small",
      language: "typescript",
      created_at: new Date().toISOString(),
    },
    "self_test",
  );
}

server.listen(PORT, "0.0.0.0", () => {
  console.log(
    JSON.stringify({
      event: "runtime.started",
      runtime: runtimeId,
      version: VERSION,
      bootId,
      port: PORT,
      financialActionsEnabled,
      outboundWorkEnabled,
      operatingFloatTargetUsd,
      taskFeed: taskFeedSummary(),
    }),
  );
  void syncTaskBounty();
});

function shutdown(signal) {
  clearInterval(heartbeat);
  clearInterval(taskFeedTimer);
  console.log(JSON.stringify({ event: "runtime.stopping", signal, bootId }));
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
