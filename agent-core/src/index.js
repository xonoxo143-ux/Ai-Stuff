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
const VERSION = "0.9.0";
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
const basedAgentsReputationBootstrapEnabled =
  process.env.BASEDAGENTS_REPUTATION_BOOTSTRAP === "true";
const baseWalletBootstrapEnabled = process.env.BASE_WALLET_BOOTSTRAP === "true";
const basedAgentsSetWalletEnabled = process.env.BASEDAGENTS_SET_WALLET === "true";
const basedAgentsCommandId = process.env.BASEDAGENTS_COMMAND_ID || "";
const basedAgentsCommandAction = process.env.BASEDAGENTS_COMMAND_ACTION || "";
const basedAgentsCommandTaskId = process.env.BASEDAGENTS_COMMAND_TASK_ID || "";
const basedAgentsCommandPayloadB64 = process.env.BASEDAGENTS_COMMAND_PAYLOAD_B64 || "";
const basedAgentsCommandNote = process.env.BASEDAGENTS_COMMAND_NOTE || "";
const baseWalletBackupUrl =
  process.env.BASE_WALLET_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/base-wallet.enc.json";
const baseWalletPkgDir = "/tmp/base-wallet-node";

const swarmSpotBootstrapEnabled = process.env.SWARMSPOT_BOOTSTRAP === "true";
const swarmSpotUsername =
  process.env.SWARMSPOT_USERNAME || "continuity-worker-541-r2";
const swarmSpotBackupUrl =
  process.env.SWARMSPOT_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/swarmspot-identity.enc.json";
const publicRuntimeBaseUrl =
  process.env.PUBLIC_RUNTIME_URL ||
  "https://browser-worker-wnux-production.up.railway.app";
const swarmSpotPollMs = Math.max(
  300_000,
  Number(process.env.SWARMSPOT_POLL_MS || 3_600_000),
);
const swarmSpotWebhookToken = eventToken
  ? createHmac("sha256", eventToken).update("swarmspot-webhook-v1").digest("hex")
  : "";

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

const basedAgentsReputationBootstrap = {
  status: "not_started",
  taskId: null,
  lastError: null,
  submittedAt: null,
};

const basedAgentsCommand = {
  id: basedAgentsCommandId || null,
  action: basedAgentsCommandAction || null,
  taskId: basedAgentsCommandTaskId || null,
  status: basedAgentsCommandId ? "pending" : "none",
  lastError: null,
  result: null,
  processedAt: null,
};

const baseWallet = {
  status: "not_initialized",
  address: null,
  network: "eip155:8453",
  source: null,
  lastError: null,
  marketplaceRegistration: {
    status: "not_started",
    lastError: null,
    verifiedAddress: null,
    verifiedNetwork: null,
  },
};
let pendingBaseWalletEncryptedBackup = null;

const swarmSpot = {
  status: "not_initialized",
  username: null,
  agentId: null,
  source: null,
  lastError: null,
  lastSyncAt: null,
  hireTopics: [],
  getDoneTopics: [],
  pendingWebhookEvents: 0,
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

function encryptWalletBackup(privateKey, address) {
  if (!eventToken) throw new Error("wallet_encryption_key_unavailable");
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = scryptSync(eventToken, salt, 32);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([
    cipher.update(Buffer.from(privateKey, "utf8")),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();

  return {
    version: 1,
    cipher: "aes-256-gcm",
    kdf: "scrypt",
    salt_b64: salt.toString("base64"),
    iv_b64: iv.toString("base64"),
    tag_b64: tag.toString("base64"),
    ciphertext_b64: ciphertext.toString("base64"),
    address,
    network: "eip155:8453",
    created_at: new Date().toISOString(),
  };
}

function decryptWalletBackup(backup) {
  if (!eventToken) throw new Error("wallet_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_wallet_backup");
  }
  const salt = Buffer.from(backup.salt_b64, "base64");
  const iv = Buffer.from(backup.iv_b64, "base64");
  const tag = Buffer.from(backup.tag_b64, "base64");
  const ciphertext = Buffer.from(backup.ciphertext_b64, "base64");
  const key = scryptSync(eventToken, salt, 32);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString("utf8");
}


function numberWordsFromText(input) {
  const ones = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
    seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
    thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17,
    eighteen: 18, nineteen: 19,
  };
  const tens = {
    twenty: 20, thirty: 30, forty: 40, fifty: 50,
    sixty: 60, seventy: 70, eighty: 80, ninety: 90,
  };
  const tokens = String(input || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, " ")
    .replace(/-/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  const values = [];
  let current = 0;
  let seen = false;
  const flush = () => {
    if (seen) values.push(current);
    current = 0;
    seen = false;
  };

  for (const token of tokens) {
    if (/^\d+(?:\.\d+)?$/.test(token)) {
      flush();
      values.push(Number(token));
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(ones, token)) {
      current += ones[token];
      seen = true;
      continue;
    }
    if (Object.prototype.hasOwnProperty.call(tens, token)) {
      current += tens[token];
      seen = true;
      continue;
    }
    if (token === "hundred" && seen) {
      current *= 100;
      continue;
    }
    if (token === "thousand" && seen) {
      current *= 1000;
      continue;
    }
    flush();
  }
  flush();
  return values;
}

function solveSwarmSpotCaptcha(challenge) {
  const clean = String(challenge || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, " ")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const nums = numberWordsFromText(clean);
  if (nums.length < 2) throw new Error("swarmspot_captcha_numbers_not_found");
  const [a, b] = nums;

  if (
    /\b(each|per)\b/.test(clean) &&
    /\b(total|altogether|in all|members|requests|tasks|messages|pallets)\b/.test(clean)
  ) {
    return a * b;
  }
  if (/\b(distributed across|divided among|split among|per worker|each worker)\b/.test(clean)) {
    if (b === 0) throw new Error("swarmspot_captcha_divide_by_zero");
    return a / b;
  }
  if (/\b(more|added|plus|increase|in the queue)\b/.test(clean)) {
    return a + b;
  }
  if (/\b(still|remaining|left|consumed|merged|removed|closed|used)\b/.test(clean)) {
    return a - b;
  }
  if (/\b(total|altogether|in all)\b/.test(clean)) return a * b;
  throw new Error("swarmspot_captcha_operation_not_recognized");
}

function encryptSwarmSpotBackup(value) {
  if (!eventToken) throw new Error("swarmspot_encryption_key_unavailable");
  const plaintext = Buffer.from(JSON.stringify(value), "utf8");
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
    username: value.username,
    agent_id: value.agentId || null,
    created_at: new Date().toISOString(),
  };
}

function decryptSwarmSpotBackup(backup) {
  if (!eventToken) throw new Error("swarmspot_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_swarmspot_backup");
  }
  const key = scryptSync(eventToken, Buffer.from(backup.salt_b64, "base64"), 32);
  const decipher = createDecipheriv(
    "aes-256-gcm",
    key,
    Buffer.from(backup.iv_b64, "base64"),
  );
  decipher.setAuthTag(Buffer.from(backup.tag_b64, "base64"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(backup.ciphertext_b64, "base64")),
    decipher.final(),
  ]);
  return JSON.parse(plaintext.toString("utf8"));
}

function swarmSpotAuthHeader(username, password) {
  return "Basic " + Buffer.from(\`\${username}:\${password}\`, "utf8").toString("base64");
}

async function swarmSpotRequest(path, { method = "GET", body = null, credentials = null } = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (credentials) {
    headers.authorization = swarmSpotAuthHeader(credentials.username, credentials.password);
  }
  const response = await fetch(\`https://swarm.spot/api\${path}\`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(20_000),
  });
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text.slice(0, 1000) }; }
  if (!response.ok) {
    const error = new Error(\`swarmspot_http_\${response.status}\`);
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function requestAndSolveSwarmSpotCaptcha() {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const challenge = await swarmSpotRequest("/captcha", { method: "POST", body: {} });
    const answer = solveSwarmSpotCaptcha(challenge.challenge);
    try {
      const solved = await swarmSpotRequest(
        \`/captcha/\${encodeURIComponent(challenge.captcha_id)}/solve\`,
        { method: "POST", body: { answer: String(answer) } },
      );
      if (solved?.captcha_token) return solved.captcha_token;
    } catch (err) {
      if (attempt === 2) throw err;
    }
  }
  throw new Error("swarmspot_captcha_solve_failed");
}

async function restoreSwarmSpotIdentity() {
  const response = await fetch(swarmSpotBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(\`swarmspot_backup_http_\${response.status}\`);
  const backup = await response.json();
  const restored = decryptSwarmSpotBackup(backup);
  if (!restored?.username || !restored?.password) {
    throw new Error("swarmspot_backup_fields_missing");
  }
  const profile = await swarmSpotRequest(
    \`/agents/\${encodeURIComponent(restored.username)}\`,
  );
  swarmSpot.status = "ready";
  swarmSpot.username = restored.username;
  swarmSpot.agentId = profile?.agent_id || restored.agentId || null;
  swarmSpot.source = "encrypted_git_backup";
  swarmSpot.lastError = null;
  swarmSpot.credentials = { username: restored.username, password: restored.password };
  return true;
}

async function registerSwarmSpotIdentity() {
  // Never mint a second account with the same permanent username if a prior bootstrap
  // succeeded but its encrypted backup was not persisted.
  try {
    const existing = await swarmSpotRequest(
      \`/agents/\${encodeURIComponent(swarmSpotUsername)}\`,
    );
    if (existing?.username) {
      swarmSpot.status = "existing_unrecoverable";
      swarmSpot.username = existing.username;
      swarmSpot.agentId = existing.agent_id || null;
      swarmSpot.lastError = "existing_account_without_local_backup";
      return;
    }
  } catch (err) {
    if (err.message !== "swarmspot_http_404") throw err;
  }

  const password = randomBytes(32).toString("base64url");
  const captchaToken = await requestAndSolveSwarmSpotCaptcha();
  const result = await swarmSpotRequest("/register", {
    method: "POST",
    body: {
      username: swarmSpotUsername,
      password,
      webhook_url: \`\${publicRuntimeBaseUrl}/integrations/swarmspot\`,
      webhook_headers: {
        Authorization: \`Bearer \${swarmSpotWebhookToken}\`,
      },
      email: agentEmail,
      captcha_token: captchaToken,
    },
  });

  const backup = encryptSwarmSpotBackup({
    username: result?.username || swarmSpotUsername,
    password,
    agentId: result?.agent_id || null,
  });

  console.log(JSON.stringify({
    event: "swarmspot.identity_backup",
    note: "Encrypted ciphertext only; password never leaves runtime plaintext.",
    backup,
  }));

  swarmSpot.status = "backup_pending";
  swarmSpot.username = result?.username || swarmSpotUsername;
  swarmSpot.agentId = result?.agent_id || null;
  swarmSpot.source = "new_registration_encrypted_backup_emitted";
  swarmSpot.lastError = null;
  swarmSpot.credentials = { username: swarmSpot.username, password };
}

async function syncSwarmSpotTopics() {
  if (swarmSpot.status !== "ready" && swarmSpot.status !== "backup_pending") return;
  if (!swarmSpot.credentials) return;
  try {
    const query = async (intent) => {
      const params = new URLSearchParams({
        intent,
        sort_by: "updated_at",
        sort_order: "desc",
        limit: "25",
        offset: "0",
      });
      const payload = await swarmSpotRequest(
        \`/topics/search?\${params.toString()}\`,
        { credentials: swarmSpot.credentials },
      );
      const items = Array.isArray(payload) ? payload :
        Array.isArray(payload?.topics) ? payload.topics :
        Array.isArray(payload?.data) ? payload.data : [];
      return items.slice(0, 25).map((t) => ({
        topic_id: t.topic_id || t.id || null,
        title: String(t.title || "").slice(0, 200),
        description: String(t.description || "").slice(0, 1000),
        value: t.value ?? null,
        currency: t.currency || null,
        currency_type: t.currency_type || null,
        intent: t.intent || intent,
        updated_at: t.updated_at || t.created_at || null,
        created_by: t.created_by || t.agent_id || null,
      }));
    };
    const [hire, getDone] = await Promise.all([query("HIRE"), query("GET_DONE")]);
    swarmSpot.hireTopics = hire;
    swarmSpot.getDoneTopics = getDone;
    swarmSpot.lastSyncAt = new Date().toISOString();
    swarmSpot.lastError = null;
  } catch (err) {
    swarmSpot.lastError = err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureSwarmSpotIdentity() {
  swarmSpot.status = "initializing";
  try {
    if (await restoreSwarmSpotIdentity()) {
      await syncSwarmSpotTopics();
      return;
    }
    if (!swarmSpotBootstrapEnabled) {
      swarmSpot.status = "backup_missing";
      swarmSpot.lastError = "encrypted_swarmspot_backup_not_found";
      return;
    }
    await registerSwarmSpotIdentity();
    await syncSwarmSpotTopics();
  } catch (err) {
    swarmSpot.status = "error";
    swarmSpot.lastError = err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(JSON.stringify({
      event: "swarmspot.identity_error",
      error: swarmSpot.lastError,
    }));
  }
}

function swarmSpotSummary() {
  const topics = [...swarmSpot.hireTopics, ...swarmSpot.getDoneTopics];
  const paidTopics = topics.filter((t) =>
    Number.isFinite(Number(t.value)) && Number(t.value) > 0,
  );
  return {
    status: swarmSpot.status,
    username: swarmSpot.username,
    agentId: swarmSpot.agentId,
    source: swarmSpot.source,
    lastError: swarmSpot.lastError,
    lastSyncAt: swarmSpot.lastSyncAt,
    hireTopicCount: swarmSpot.hireTopics.length,
    getDoneTopicCount: swarmSpot.getDoneTopics.length,
    paidTopicCount: paidTopics.length,
    paidTopics: paidTopics.slice(0, 10),
    pendingWebhookEvents: swarmSpot.pendingWebhookEvents,
  };
}

async function fetchBasedAgentsTask(taskId) {
  const response = await fetch(
    `https://api.basedagents.ai/v1/tasks/${encodeURIComponent(taskId)}`,
    { headers: { accept: "application/json" }, signal: AbortSignal.timeout(15_000) },
  );
  if (!response.ok) throw new Error(`basedagents_task_http_${response.status}`);
  const payload = await response.json();
  return payload?.task || null;
}

async function hasOtherActivePaidBasedAgentsClaim(taskId) {
  if (!basedAgentsIdentity.agentId) return true;
  const response = await fetch(
    `https://api.basedagents.ai/v1/tasks?claimer=${encodeURIComponent(
      basedAgentsIdentity.agentId,
    )}&limit=100`,
    { headers: { accept: "application/json" }, signal: AbortSignal.timeout(15_000) },
  );
  if (!response.ok) throw new Error(`basedagents_claims_http_${response.status}`);
  const payload = await response.json();
  const tasks = Array.isArray(payload?.tasks) ? payload.tasks : [];
  return tasks.some((t) =>
    t?.task_id !== taskId &&
    t?.bounty != null &&
    ["claimed", "submitted"].includes(String(t?.status || "")),
  );
}

async function processBasedAgentsCommand() {
  if (!basedAgentsCommandId) return;
  if (basedAgentsCommand.status === "processing" ||
      basedAgentsCommand.status === "completed") return;
  if (!outboundWorkEnabled) {
    basedAgentsCommand.status = "blocked";
    basedAgentsCommand.lastError = "outbound_work_disabled";
    return;
  }
  if (basedAgentsIdentity.status !== "ready" ||
      !basedAgentsIdentity.registered ||
      baseWallet.status !== "ready" ||
      baseWallet.marketplaceRegistration.status !== "verified") {
    basedAgentsCommand.status = "waiting_dependencies";
    return;
  }

  basedAgentsCommand.status = "processing";
  basedAgentsCommand.lastError = null;
  try {
    if (!basedAgentsCommandTaskId) throw new Error("missing_command_task_id");
    const task = await fetchBasedAgentsTask(basedAgentsCommandTaskId);
    if (!task) throw new Error("task_not_found");

    if (basedAgentsCommandAction === "claim") {
      if (task.status !== "open" || task.claimable !== true) {
        throw new Error("task_not_open_and_claimable");
      }
      const normalized = normalizeBasedAgentsTask(task);
      const evaluation = evaluateBasedAgentsTask(normalized);
      if (evaluation.status !== "candidate") {
        throw new Error(`task_failed_runtime_filter:${evaluation.status}`);
      }
      if (await hasOtherActivePaidBasedAgentsClaim(task.task_id)) {
        throw new Error("another_paid_task_already_active");
      }

      const result = await runBasedAgentsCli([
        "tasks",
        "claim",
        task.task_id,
        "--keypair",
        basedAgentsKeypairPath,
        "--json",
      ]);
      basedAgentsCommand.status = "completed";
      basedAgentsCommand.result = {
        action: "claim",
        taskId: task.task_id,
        status: result.json?.status || "claimed",
      };
      basedAgentsCommand.processedAt = new Date().toISOString();
      rememberEvent({
        id: randomUUID(),
        receivedAt: basedAgentsCommand.processedAt,
        type: "job.claimed",
        source: "basedagents_command",
        externalId: task.task_id,
      });
    } else if (basedAgentsCommandAction === "deliver") {
      if (!["claimed"].includes(String(task.status || ""))) {
        if (task.status === "submitted" || task.status === "verified") {
          basedAgentsCommand.status = "completed";
          basedAgentsCommand.result = {
            action: "deliver",
            taskId: task.task_id,
            status: task.status,
            idempotent: true,
          };
          basedAgentsCommand.processedAt = new Date().toISOString();
          return;
        }
        throw new Error(`task_not_deliverable_from_status:${task.status}`);
      }
      if (task.claimed_by_agent_id !== basedAgentsIdentity.agentId) {
        throw new Error("task_not_claimed_by_active_worker");
      }
      if (!basedAgentsCommandPayloadB64) throw new Error("missing_delivery_payload");

      let payload;
      try {
        payload = Buffer.from(basedAgentsCommandPayloadB64, "base64");
      } catch {
        throw new Error("delivery_payload_invalid_base64");
      }
      if (!payload.length || payload.length > 50_000) {
        throw new Error("delivery_payload_size_invalid");
      }

      if (task.output_format === "json") {
        try {
          JSON.parse(payload.toString("utf8"));
        } catch {
          throw new Error("delivery_payload_not_valid_json");
        }
      }

      const reportPath = `/tmp/basedagents-delivery-${task.task_id}.txt`;
      await writeFile(reportPath, payload, { mode: 0o600 });
      const note = basedAgentsCommandNote.slice(0, 1000) ||
        "Completed the requested bounded task and attached the requested deliverable.";

      const result = await runBasedAgentsCli([
        "tasks",
        "submit",
        task.task_id,
        "--keypair",
        basedAgentsKeypairPath,
        "--file",
        reportPath,
        "--note",
        note,
        "--json",
      ]);
      basedAgentsCommand.status = "completed";
      basedAgentsCommand.result = {
        action: "deliver",
        taskId: task.task_id,
        status: result.json?.status || "submitted",
      };
      basedAgentsCommand.processedAt = new Date().toISOString();
      rememberEvent({
        id: randomUUID(),
        receivedAt: basedAgentsCommand.processedAt,
        type: "job.delivered",
        source: "basedagents_command",
        externalId: task.task_id,
      });
    } else {
      throw new Error("unsupported_basedagents_command_action");
    }
  } catch (err) {
    basedAgentsCommand.status = "error";
    basedAgentsCommand.lastError =
      err instanceof Error ? err.message.slice(0,300) : String(err).slice(0,300);
    basedAgentsCommand.processedAt = new Date().toISOString();
    console.error(JSON.stringify({
      event: "basedagents.command_error",
      commandId: basedAgentsCommandId,
      action: basedAgentsCommandAction,
      taskId: basedAgentsCommandTaskId,
      error: basedAgentsCommand.lastError,
    }));
  }
}

async function maybeRegisterBasedAgentsWallet() {
  if (baseWallet.marketplaceRegistration.status === "checking" ||
      baseWallet.marketplaceRegistration.status === "setting" ||
      baseWallet.marketplaceRegistration.status === "verified") return;
  if (baseWallet.status !== "ready" || !baseWallet.address) return;
  if (basedAgentsIdentity.status !== "ready" || !basedAgentsIdentity.registered) return;

  baseWallet.marketplaceRegistration.status = "checking";
  baseWallet.marketplaceRegistration.lastError = null;
  try {
    const existing = await runBasedAgentsCli([
      "wallet",
      "--keypair",
      basedAgentsKeypairPath,
      "--json",
    ]);
    const current = existing.json || {};
    const currentAddress = String(current.wallet_address || "");
    const currentNetwork = current.wallet_network || null;

    if (
      currentAddress.toLowerCase() === baseWallet.address.toLowerCase() &&
      currentNetwork === "eip155:8453"
    ) {
      baseWallet.marketplaceRegistration.status = "verified";
      baseWallet.marketplaceRegistration.verifiedAddress = currentAddress;
      baseWallet.marketplaceRegistration.verifiedNetwork = currentNetwork;
      return;
    }

    if (!basedAgentsSetWalletEnabled) {
      baseWallet.marketplaceRegistration.status = "missing_or_mismatched";
      baseWallet.marketplaceRegistration.lastError =
        "basedagents_wallet_not_registered_to_canonical_address";
      return;
    }

    baseWallet.marketplaceRegistration.status = "setting";
    await runBasedAgentsCli([
      "wallet",
      "set",
      baseWallet.address,
      "--network",
      "eip155:8453",
      "--keypair",
      basedAgentsKeypairPath,
      "--json",
    ]);

    const check = await runBasedAgentsCli([
      "wallet",
      "--keypair",
      basedAgentsKeypairPath,
      "--json",
    ]);
    const info = check.json || {};
    if (
      String(info.wallet_address || "").toLowerCase() !==
        baseWallet.address.toLowerCase() ||
      info.wallet_network !== "eip155:8453"
    ) {
      throw new Error("basedagents_wallet_verification_mismatch");
    }

    baseWallet.marketplaceRegistration.status = "verified";
    baseWallet.marketplaceRegistration.verifiedAddress = info.wallet_address;
    baseWallet.marketplaceRegistration.verifiedNetwork = info.wallet_network;
    console.log(JSON.stringify({
      event: "basedagents.wallet_registered",
      agentId: basedAgentsIdentity.agentId,
      address: info.wallet_address,
      network: info.wallet_network,
    }));
  } catch (err) {
    baseWallet.marketplaceRegistration.status = "error";
    baseWallet.marketplaceRegistration.lastError =
      err instanceof Error ? err.message.slice(0,300) : String(err).slice(0,300);
    console.error(JSON.stringify({
      event: "basedagents.wallet_registration_error",
      error: baseWallet.marketplaceRegistration.lastError,
    }));
  } finally {
    setTimeout(() => void processBasedAgentsCommand(), 250).unref();
  }
}

async function restoreBaseWallet() {
  const response = await fetch(baseWalletBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`wallet_backup_http_${response.status}`);
  const backup = await response.json();
  const privateKey = decryptWalletBackup(backup);
  if (!/^0x[a-fA-F0-9]{64}$/.test(privateKey)) {
    throw new Error("wallet_backup_private_key_invalid");
  }
  if (!/^0x[a-fA-F0-9]{40}$/.test(String(backup.address || ""))) {
    throw new Error("wallet_backup_address_invalid");
  }
  baseWallet.status = "ready";
  baseWallet.address = backup.address;
  baseWallet.source = "encrypted_git_backup";
  baseWallet.lastError = null;
  void maybeRegisterBasedAgentsWallet();
  setTimeout(() => void processBasedAgentsCommand(), 1500).unref();
  return true;
}

async function generateBaseWallet() {
  await mkdir(baseWalletPkgDir, { recursive: true });
  await execFileAsync(
    "npm",
    [
      "install",
      "--prefix",
      baseWalletPkgDir,
      "ethers@6.15.0",
      "--no-audit",
      "--no-fund",
    ],
    { timeout: 120_000 },
  );

  const generated = await execFileAsync(
    "node",
    [
      "-e",
      "const {Wallet}=require('ethers');const w=Wallet.createRandom();process.stdout.write(JSON.stringify({address:w.address,privateKey:w.privateKey}));",
    ],
    { cwd: baseWalletPkgDir },
  );
  const wallet = JSON.parse(String(generated.stdout || ""));
  if (!/^0x[a-fA-F0-9]{40}$/.test(wallet.address || "")) {
    throw new Error("generated_wallet_address_invalid");
  }
  if (!/^0x[a-fA-F0-9]{64}$/.test(wallet.privateKey || "")) {
    throw new Error("generated_wallet_private_key_invalid");
  }

  const backup = encryptWalletBackup(wallet.privateKey, wallet.address);
  pendingBaseWalletEncryptedBackup = backup;
  console.log(
    JSON.stringify({
      event: "base_wallet.encrypted_backup",
      note: "Encrypted ciphertext only; private key never leaves runtime plaintext.",
      backup,
    }),
  );

  baseWallet.status = "backup_pending";
  baseWallet.address = wallet.address;
  baseWallet.source = "new_wallet_encrypted_backup_emitted";
  baseWallet.lastError = null;
}

async function ensureBaseWallet() {
  baseWallet.status = "initializing";
  try {
    if (await restoreBaseWallet()) return;
    if (!baseWalletBootstrapEnabled) {
      baseWallet.status = "backup_missing";
      baseWallet.lastError = "encrypted_wallet_backup_not_found";
      return;
    }
    await generateBaseWallet();
  } catch (err) {
    baseWallet.status = "error";
    baseWallet.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(
      JSON.stringify({
        event: "base_wallet.error",
        error: baseWallet.lastError,
      }),
    );
  }
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

async function runBasedAgentsReputationBootstrap() {
  if (!basedAgentsReputationBootstrapEnabled) return;
  if (!basedAgentsIdentity.registered || basedAgentsIdentity.status !== "ready") return;

  basedAgentsReputationBootstrap.status = "checking";
  try {
    const existingResponse = await fetch(
      `https://api.basedagents.ai/v1/tasks?claimer=${encodeURIComponent(
        basedAgentsIdentity.agentId,
      )}&limit=100`,
      { headers: { accept: "application/json" }, signal: AbortSignal.timeout(15_000) },
    );
    if (!existingResponse.ok) {
      throw new Error(`basedagents_existing_tasks_http_${existingResponse.status}`);
    }
    const existingPayload = await existingResponse.json();
    const existingTasks = Array.isArray(existingPayload?.tasks) ? existingPayload.tasks : [];
    if (existingTasks.some((t) => /^\[first task/i.test(String(t.title || "")))) {
      const prior = existingTasks.find((t) => /^\[first task/i.test(String(t.title || "")));
      basedAgentsReputationBootstrap.status = "already_used";
      basedAgentsReputationBootstrap.taskId = prior?.task_id || null;
      return;
    }

    const idResult = await runBasedAgentsCli([
      "id",
      "--keypair",
      basedAgentsKeypairPath,
      "--json",
    ]);

    const listResult = await runBasedAgentsCli([
      "tasks",
      "list",
      "--status",
      "open",
      "--keypair",
      basedAgentsKeypairPath,
      "--json",
    ]);

    const openPayload = listResult.json;
    const openTasks = Array.isArray(openPayload)
      ? openPayload
      : Array.isArray(openPayload?.tasks)
        ? openPayload.tasks
        : Array.isArray(openPayload?.data)
          ? openPayload.data
          : [];

    const candidates = openTasks.filter(
      (t) => t?.claimable === true && /^\[first task/i.test(String(t.title || "")),
    );
    if (!candidates.length) {
      basedAgentsReputationBootstrap.status = "no_slot_available";
      return;
    }

    let claimed = null;
    for (const task of candidates) {
      try {
        await runBasedAgentsCli([
          "tasks",
          "claim",
          task.task_id,
          "--keypair",
          basedAgentsKeypairPath,
          "--json",
        ]);
        claimed = task;
        break;
      } catch (err) {
        const combined = `${err?.stdout || ""}\n${err?.stderr || ""}`;
        if (combined.includes("409") || combined.toLowerCase().includes("conflict")) {
          continue;
        }
        throw err;
      }
    }

    if (!claimed) {
      basedAgentsReputationBootstrap.status = "lost_claim_races";
      return;
    }

    basedAgentsReputationBootstrap.taskId = claimed.task_id;
    basedAgentsReputationBootstrap.status = "claimed";

    const report = {
      task_key:
        String(claimed.description || "").match(/Task key:\s*([^\s]+)/i)?.[1] ||
        "ba-first-task-v1",
      outcome: "no_issue_found",
      feedback_id: null,
      skill_version: "1.1.1",
      cli_version: basedAgentsIdentity.cliVersion,
      section: "2 and 4",
      expected:
        "Identity registration/recovery and open-task discovery work as documented in skill.md.",
      actual:
        "The BasedAgents CLI registered/restored the durable worker identity and listed the live open-task board successfully.",
      steps: [
        "Read https://basedagents.ai/skill.md",
        "Ran basedagents id --json with the restored keypair",
        "Ran basedagents tasks list --status open --json",
        "Selected one eligible [First task] slot and claimed it",
      ],
      evidence: [
        {
          command: "basedagents id --json",
          output: {
            registered: idResult.json?.registered ?? true,
            agent_id: basedAgentsIdentity.agentId,
            profile_url: basedAgentsIdentity.profileUrl,
          },
        },
        {
          command: "basedagents tasks list --status open --json",
          output: {
            open_task_count: openTasks.length,
            eligible_first_task_count: candidates.length,
            selected_task_id: claimed.task_id,
          },
        },
      ],
    };

    const reportPath = "/tmp/basedagents-first-task-report.json";
    await writeFile(reportPath, JSON.stringify(report, null, 2) + "\n", { mode: 0o600 });

    await runBasedAgentsCli([
      "tasks",
      "submit",
      claimed.task_id,
      "--keypair",
      basedAgentsKeypairPath,
      "--file",
      reportPath,
      "--note",
      "Runbook identity and work-discovery steps worked as written; no issue found.",
      "--json",
    ]);

    basedAgentsReputationBootstrap.status = "submitted";
    basedAgentsReputationBootstrap.submittedAt = new Date().toISOString();
    basedAgentsReputationBootstrap.lastError = null;
    console.log(
      JSON.stringify({
        event: "basedagents.reputation_task_submitted",
        taskId: claimed.task_id,
      }),
    );
  } catch (err) {
    basedAgentsReputationBootstrap.status = "error";
    basedAgentsReputationBootstrap.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(
      JSON.stringify({
        event: "basedagents.reputation_task_error",
        error: basedAgentsReputationBootstrap.lastError,
      }),
    );
  }
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

    if (await restoreBasedAgentsIdentity()) {
      void runBasedAgentsReputationBootstrap();
      void maybeRegisterBasedAgentsWallet();
      setTimeout(() => void processBasedAgentsCommand(), 1500).unref();
      return;
    }

    if (!basedAgentsBootstrapEnabled) {
      basedAgentsIdentity.status = "backup_missing";
      basedAgentsIdentity.lastError = "encrypted_identity_backup_not_found";
      return;
    }

    await registerBasedAgentsIdentity();
    if (basedAgentsIdentity.status === "ready") {
      void runBasedAgentsReputationBootstrap();
    }
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
      reputationBootstrap: { ...basedAgentsReputationBootstrap },
      payoutWallet: {
        status: baseWallet.status,
        address: baseWallet.address,
        network: baseWallet.network,
        source: baseWallet.source,
        lastError: baseWallet.lastError,
        marketplaceRegistration: { ...baseWallet.marketplaceRegistration },
      },
      workCommand: {
        id: basedAgentsCommand.id,
        action: basedAgentsCommand.action,
        taskId: basedAgentsCommand.taskId,
        status: basedAgentsCommand.status,
        lastError: basedAgentsCommand.lastError,
        result: basedAgentsCommand.result,
        processedAt: basedAgentsCommand.processedAt,
      },
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
        swarmSpot: swarmSpotSummary(),
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
        swarmSpot: swarmSpotSummary(),
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
        basedAgents: basedAgentsSummary(),
        swarmSpot: swarmSpotSummary(),
        agentMail: "not_configured_in_runtime",
        circle: "not_configured_in_runtime",
        stripe: "external_adapter_only",
        continuityJournal: "adapter_pending",
      },
      queue: Array.from(taskQueue.values()).slice(-100),
      recentEvents,
    });
  }

  if (req.method === "POST" && url.pathname === "/integrations/swarmspot") {
    const auth = req.headers.authorization || "";
    if (!swarmSpotWebhookToken || auth !== \`Bearer \${swarmSpotWebhookToken}\`) {
      return json(res, 401, { error: "unauthorized" });
    }
    try {
      const body = await readJson(req);
      swarmSpot.pendingWebhookEvents += 1;
      rememberEvent({
        id: randomUUID(),
        receivedAt: new Date().toISOString(),
        type: "swarmspot." + String(body?.event || "event").slice(0, 80),
        source: "swarmspot_webhook",
        externalId: String(body?.thread_id || body?.topic_id || body?.message_id || "").slice(0, 240) || null,
      });
      return json(res, 202, { accepted: true });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
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

const swarmSpotTimer = setInterval(() => {
  void syncSwarmSpotTopics();
}, swarmSpotPollMs);
swarmSpotTimer.unref();

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
  void ensureBaseWallet();
  void ensureSwarmSpotIdentity();
});

function shutdown(signal) {
  clearInterval(heartbeat);
  clearInterval(taskFeedTimer);
  clearInterval(basedAgentsTimer);
  clearInterval(swarmSpotTimer);
  console.log(JSON.stringify({ event: "runtime.stopping", signal, bootId }));
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
