import http from "node:http";
import {
  createCipheriv,
  createDecipheriv,
  createHmac,
  randomBytes,
  randomUUID,
  scryptSync,
  timingSafeEqual,
} from "node:crypto";
import { execFile } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";

const PORT = Number(process.env.PORT || 3000);
const VERSION = "0.4.1";
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

const basedAgentsFeedUrl =
  process.env.BASEDAGENTS_FEED_URL ||
  "https://api.basedagents.ai/v1/tasks?status=open";
const basedAgentsPollMs = Math.max(
  300_000,
  Number(process.env.BASEDAGENTS_POLL_MS || 3_600_000),
);
const basedAgentsBootstrapEnabled = process.env.BASEDAGENTS_BOOTSTRAP === "true";
const basedAgentsBackupUrl =
  process.env.BASEDAGENTS_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/basedagents-identity.enc.json";
const basedAgentsHome = "/tmp/agent-home";
const basedAgentsKeypairPath = `${basedAgentsHome}/.basedagents/keys/continuity-agent-keypair.json`;

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

const basedAgentsState = {
  provider: "basedagents",
  mode: "public_open_task_feed",
  lastAttemptAt: null,
  lastSuccessAt: null,
  lastError: null,
  syncCount: 0,
  discoveredCount: 0,
  paidCandidateCount: 0,
  reputationCandidateCount: 0,
  reviewCount: 0,
  rejectedCount: 0,
  pollMs: basedAgentsPollMs,
};

const basedAgentsIdentity = {
  status: "not_initialized",
  registered: false,
  agentId: null,
  profileUrl: null,
  source: null,
  lastError: null,
  cliVersion: null,
};

function execFileAsync(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(
      command,
      args,
      { maxBuffer: 2 * 1024 * 1024, timeout: 120_000, ...options },
      (error, stdout, stderr) => {
        if (error) {
          error.stdout = stdout;
          error.stderr = stderr;
          reject(error);
          return;
        }
        resolve({ stdout, stderr });
      },
    );
  });
}

function parseCliJson(stdout) {
  const text = String(stdout || "").trim();
  if (!text) throw new Error("basedagents_empty_json_output");
  try {
    return JSON.parse(text);
  } catch {}
  const first = text.indexOf("{");
  const last = text.lastIndexOf("}");
  if (first >= 0 && last > first) {
    return JSON.parse(text.slice(first, last + 1));
  }
  throw new Error("basedagents_json_not_found");
}

async function runBasedAgentsCli(args) {
  const result = await execFileAsync(
    "npx",
    ["--yes", "basedagents@latest", ...args],
    {
      env: { ...process.env, HOME: basedAgentsHome },
    },
  );
  return {
    json: args.includes("--json") ? parseCliJson(result.stdout) : null,
    stdout: result.stdout,
    stderr: result.stderr,
  };
}

function encryptIdentityBackup(plaintext, agentMeta) {
  if (!eventToken) throw new Error("identity_encryption_key_unavailable");
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = scryptSync(eventToken, salt, 32);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();

  return {
    version: 1,
    cipher: "aes-256-gcm",
    kdf: "scrypt",
    salt_b64: salt.toString("base64"),
    iv_b64: iv.toString("base64"),
    tag_b64: tag.toString("base64"),
    ciphertext_b64: ciphertext.toString("base64"),
    agent_id: agentMeta.agent_id || null,
    name: agentMeta.name || null,
    profile_url: agentMeta.profile_url || null,
    created_at: new Date().toISOString(),
  };
}

function decryptIdentityBackup(backup) {
  if (!eventToken) throw new Error("identity_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_identity_backup");
  }

  const salt = Buffer.from(backup.salt_b64, "base64");
  const iv = Buffer.from(backup.iv_b64, "base64");
  const tag = Buffer.from(backup.tag_b64, "base64");
  const ciphertext = Buffer.from(backup.ciphertext_b64, "base64");
  const key = scryptSync(eventToken, salt, 32);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

async function restoreBasedAgentsIdentity() {
  const response = await fetch(basedAgentsBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`identity_backup_http_${response.status}`);

  const backup = await response.json();
  const plaintext = decryptIdentityBackup(backup);
  await mkdir(`${basedAgentsHome}/.basedagents/keys`, { recursive: true });
  await writeFile(basedAgentsKeypairPath, plaintext, { mode: 0o600 });
  await chmod(basedAgentsKeypairPath, 0o600);

  const idResult = await runBasedAgentsCli([
    "id",
    "--keypair",
    basedAgentsKeypairPath,
    "--json",
  ]);
  if (!idResult.json?.registered) throw new Error("restored_identity_not_registered");

  basedAgentsIdentity.status = "ready";
  basedAgentsIdentity.registered = true;
  basedAgentsIdentity.agentId = idResult.json.agent_id || backup.agent_id || null;
  basedAgentsIdentity.profileUrl = idResult.json.profile_url || backup.profile_url || null;
  basedAgentsIdentity.source = "encrypted_git_backup";
  basedAgentsIdentity.lastError = null;
  return true;
}

async function registerBasedAgentsIdentity() {
  await mkdir(`${basedAgentsHome}/.basedagents/keys`, { recursive: true });

  let name = process.env.BASEDAGENTS_AGENT_NAME || "Continuity-Worker-541-R2";
  let result;
  try {
    result = await runBasedAgentsCli([
      "register",
      "--name",
      name,
      "--description",
      "Transparent autonomous software and research worker for bounded paid tasks.",
      "--capabilities",
      "research,code,data,automation",
      "--json",
    ]);
  } catch (err) {
    const combined = `${err?.stdout || ""}\n${err?.stderr || ""}`;
    if (!combined.includes("409") && !combined.toLowerCase().includes("taken")) throw err;
    name = `Continuity-Worker-541-${bootId.slice(0, 6)}`;
    result = await runBasedAgentsCli([
      "register",
      "--name",
      name,
      "--description",
      "Transparent autonomous software and research worker for bounded paid tasks.",
      "--capabilities",
      "research,code,data,automation",
      "--json",
    ]);
  }

  const registeredPath = result.json?.keypair_path;
  if (!registeredPath || !result.json?.agent_id) {
    throw new Error("registration_missing_identity_fields");
  }

  const keypairBytes = await readFile(registeredPath);
  await writeFile(basedAgentsKeypairPath, keypairBytes, { mode: 0o600 });
  await chmod(basedAgentsKeypairPath, 0o600);

  const backup = encryptIdentityBackup(keypairBytes, result.json);
  console.log(
    JSON.stringify({
      event: "basedagents.identity_backup",
      note: "Encrypted ciphertext only; private key never leaves runtime plaintext.",
      backup,
    }),
  );

  basedAgentsIdentity.status = "backup_pending";
  basedAgentsIdentity.registered = true;
  basedAgentsIdentity.agentId = result.json.agent_id;
  basedAgentsIdentity.profileUrl = result.json.profile_url || null;
  basedAgentsIdentity.source = "new_registration_encrypted_backup_emitted";
  basedAgentsIdentity.lastError = null;
}

async function ensureBasedAgentsIdentity() {
  basedAgentsIdentity.status = "initializing";
  try {
    const versionResult = await execFileAsync(
      "npx",
      ["--yes", "basedagents@latest", "--version"],
      { env: { ...process.env, HOME: basedAgentsHome } },
    );
    basedAgentsIdentity.cliVersion = String(versionResult.stdout || "").trim().slice(0, 80) || null;

    if (await restoreBasedAgentsIdentity()) return;

    if (!basedAgentsBootstrapEnabled) {
      basedAgentsIdentity.status = "backup_missing";
      basedAgentsIdentity.lastError = "encrypted_identity_backup_not_found";
      return;
    }

    await registerBasedAgentsIdentity();
  } catch (err) {
    basedAgentsIdentity.status = "error";
    basedAgentsIdentity.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(
      JSON.stringify({
        event: "basedagents.identity_error",
        error: basedAgentsIdentity.lastError,
      }),
    );
  }
}

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

function normalizeBasedAgentsTask(raw) {
  if (!raw || typeof raw !== "object") return null;
  const taskId = String(raw.task_id || raw.id || "").trim();
  if (!taskId || taskId.length > 200) return null;

  const bountyDisplay = raw.bounty?.amount_display;
  const bountyUsd = Number.isFinite(Number(bountyDisplay))
    ? Number(bountyDisplay)
    : null;

  return {
    provider: "basedagents",
    source: "basedagents_public_feed",
    taskId,
    title: String(raw.title || "").trim().slice(0, 500),
    description: String(raw.description || "").trim().slice(0, 5000),
    category: String(raw.category || "").trim().slice(0, 80) || null,
    outputFormat: String(raw.output_format || "").trim().slice(0, 40) || null,
    claimable: raw.claimable === true,
    bountyUsd,
    bountyToken: raw.bounty?.token || null,
    bountyNetwork: raw.bounty?.network || null,
    escrowStatus: raw.escrow?.status || null,
    createdAt: typeof raw.created_at === "string" ? raw.created_at.slice(0, 80) : null,
    taskUrl: `https://basedagents.ai/tasks/${encodeURIComponent(taskId)}`,
  };
}

function evaluateBasedAgentsTask(task) {
  const reasons = [];
  let score = 50;
  let status = "rejected";

  if (!task.claimable) {
    reasons.push("not_claimable");
  } else if (task.bountyUsd != null) {
    if (task.bountyToken !== "USDC" || task.bountyNetwork !== "eip155:8453") {
      status = "manual_review";
      reasons.push("unexpected_payment_rail");
    } else if (task.escrowStatus !== "funded") {
      status = "manual_review";
      reasons.push("escrow_not_confirmed_funded");
    } else if (task.bountyUsd < 1) {
      reasons.push("paid_bounty_below_1_usd");
    } else {
      status = "candidate";
      score += Math.min(25, Math.floor(task.bountyUsd));
      reasons.push("claimable_funded_usdc_bounty");
    }
  } else if (/^\[first task/i.test(task.title)) {
    status = "reputation_candidate";
    score = 65;
    reasons.push("zero_cost_new_agent_reputation_task");
  } else {
    reasons.push("free_task_not_selected_for_bootstrap");
  }

  const riskText = `${task.title} ${task.description}`.toLowerCase();
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
    score = Math.min(score, 40);
    reasons.push("potentially_sensitive_or_harmful_scope");
  }

  return {
    status,
    score: Math.max(0, Math.min(100, score)),
    reasons,
    nextAction:
      status === "candidate"
        ? "await_ai_feasibility_review"
        : status === "reputation_candidate"
          ? "eligible_once_for_bootstrap_reputation"
          : status === "manual_review"
            ? "hold_for_review"
            : "ignore",
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
  let tbCandidates = 0;
  let tbReview = 0;
  let tbRejected = 0;
  let tbDiscovered = 0;

  let baPaid = 0;
  let baReputation = 0;
  let baReview = 0;
  let baRejected = 0;
  let baDiscovered = 0;

  for (const item of taskQueue.values()) {
    if (item.provider === "taskbounty") {
      tbDiscovered += 1;
      if (item.evaluation.status === "candidate") tbCandidates += 1;
      else if (item.evaluation.status === "manual_review") tbReview += 1;
      else if (item.evaluation.status === "rejected") tbRejected += 1;
    } else if (item.provider === "basedagents") {
      baDiscovered += 1;
      if (item.evaluation.status === "candidate") baPaid += 1;
      else if (item.evaluation.status === "reputation_candidate") baReputation += 1;
      else if (item.evaluation.status === "manual_review") baReview += 1;
      else if (item.evaluation.status === "rejected") baRejected += 1;
    }
  }

  feedState.candidateCount = tbCandidates;
  feedState.reviewCount = tbReview;
  feedState.rejectedCount = tbRejected;
  feedState.discoveredCount = tbDiscovered;

  basedAgentsState.paidCandidateCount = baPaid;
  basedAgentsState.reputationCandidateCount = baReputation;
  basedAgentsState.reviewCount = baReview;
  basedAgentsState.rejectedCount = baRejected;
  basedAgentsState.discoveredCount = baDiscovered;
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

function ingestBasedAgentsTask(raw) {
  const task = normalizeBasedAgentsTask(raw);
  if (!task) return null;

  const key = `basedagents:${task.taskId}`;
  const previous = taskQueue.get(key);
  const evaluation = evaluateBasedAgentsTask(task);
  const record = {
    ...task,
    evaluation,
    firstSeenAt: previous?.firstSeenAt || new Date().toISOString(),
    lastSeenAt: new Date().toISOString(),
  };
  taskQueue.set(key, record);
  recomputeFeedCounts();

  if (!previous || JSON.stringify(previous.evaluation) !== JSON.stringify(evaluation)) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: previous ? "job.updated" : "job.available",
      source: "basedagents_public_feed",
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

async function syncBasedAgents() {
  basedAgentsState.lastAttemptAt = new Date().toISOString();
  try {
    const response = await fetch(basedAgentsFeedUrl, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) throw new Error(`basedagents_http_${response.status}`);
    const payload = await response.json();
    const tasks = Array.isArray(payload?.tasks) ? payload.tasks : [];
    for (const task of tasks) ingestBasedAgentsTask(task);

    basedAgentsState.lastSuccessAt = new Date().toISOString();
    basedAgentsState.lastError = null;
    basedAgentsState.syncCount += 1;
    recomputeFeedCounts();
  } catch (err) {
    basedAgentsState.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
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

function basedAgentsSummary() {
  return {
    identity: {
      status: basedAgentsIdentity.status,
      registered: basedAgentsIdentity.registered,
      agentId: basedAgentsIdentity.agentId,
      profileUrl: basedAgentsIdentity.profileUrl,
      source: basedAgentsIdentity.source,
      lastError: basedAgentsIdentity.lastError,
      cliVersion: basedAgentsIdentity.cliVersion,
    },
    provider: basedAgentsState.provider,
    mode: basedAgentsState.mode,
    lastAttemptAt: basedAgentsState.lastAttemptAt,
    lastSuccessAt: basedAgentsState.lastSuccessAt,
    lastError: basedAgentsState.lastError,
    syncCount: basedAgentsState.syncCount,
    discoveredCount: basedAgentsState.discoveredCount,
    paidCandidateCount: basedAgentsState.paidCandidateCount,
    reputationCandidateCount: basedAgentsState.reputationCandidateCount,
    reviewCount: basedAgentsState.reviewCount,
    rejectedCount: basedAgentsState.rejectedCount,
    pollMs: basedAgentsState.pollMs,
  };
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
      taskFeeds: {
        taskBounty: taskFeedSummary(),
        basedAgents: basedAgentsSummary(),
        basedAgents: basedAgentsSummary(),
      },
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
      taskFeeds: {
        taskBounty: taskFeedSummary(),
        basedAgents: basedAgentsSummary(),
      },
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

const basedAgentsTimer = setInterval(() => {
  void syncBasedAgents();
}, basedAgentsPollMs);
basedAgentsTimer.unref();

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
  void syncBasedAgents();
  void ensureBasedAgentsIdentity();
});

function shutdown(signal) {
  clearInterval(heartbeat);
  clearInterval(taskFeedTimer);
  clearInterval(basedAgentsTimer);
  console.log(JSON.stringify({ event: "runtime.stopping", signal, bootId }));
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
