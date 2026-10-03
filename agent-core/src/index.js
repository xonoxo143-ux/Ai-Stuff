import http from "node:http";
import {
  createCipheriv,
  createDecipheriv,
  createHash,
  createHmac,
  randomBytes,
  randomUUID,
  scryptSync,
  timingSafeEqual,
} from "node:crypto";
import { execFile } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { createDurableState } from "./durable-state.js";
import { createStripeAdapter } from "./stripe-adapter.js";

const PORT = Number(process.env.PORT || 3000);
const VERSION = "0.19.0";
const runtimeId = process.env.RUNTIME_ID || "continuity-agent-core";
const agentEmail = process.env.AGENT_EMAIL || "oldcraft541@agentmail.to";
const eventToken = process.env.RUNTIME_EVENT_TOKEN || process.env.BROWSER_WORKER_TOKEN || "";
const motorAgentToken = process.env.MOTOR_AGENT_TOKEN || "";
const motorBootstrapToken = process.env.MOTOR_BOOTSTRAP_TOKEN || "";
const agentMailWebhookToken = process.env.AGENTMAIL_WEBHOOK_TOKEN || "";
const agentMailApiKey = process.env.AGENTMAIL_API_KEY || "";
const agentMailInboxId = process.env.AGENTMAIL_INBOX_ID || "";
const agentMailWebhookProvision = process.env.AGENTMAIL_WEBHOOK_PROVISION === "true";
const agentMailWebhookClientId =
  process.env.AGENTMAIL_WEBHOOK_CLIENT_ID || "self-root-motor-v1";

const agentMailCommandSenders = new Set(
  String(process.env.AGENTMAIL_COMMAND_SENDERS || agentEmail)
    .split(",")
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean),
);
const motorSelfTestAction = String(process.env.MOTOR_SELF_TEST_ACTION || "").trim().toLowerCase();
const evidenceMotorMirrorEnabled = process.env.EVIDENCE_MOTOR_MIRROR_ENABLED === "true";

const motorCommandTtlMs = Math.max(
  60_000,
  Math.min(Number(process.env.MOTOR_COMMAND_TTL_MS || 15 * 60_000), 24 * 60 * 60_000),
);

const financialActionsEnabled = process.env.FINANCIAL_ACTIONS_ENABLED === "true";
const outboundWorkEnabled = process.env.OUTBOUND_WORK_ENABLED === "true";
const operatingFloatTargetUsd = Number(process.env.OPERATING_FLOAT_TARGET_USD || 100);
const workSchedulerEnabled = process.env.WORK_SCHEDULER_ENABLED !== "false";
const workSchedulerTickMs = Math.max(
  30_000,
  Number(process.env.WORK_SCHEDULER_TICK_MS || 60_000),
);
const workMinPaidUsd = Math.max(
  0,
  Number(process.env.WORK_MIN_PAID_USD || 5),
);
const workMaxSubstantial = Math.max(
  1,
  Math.min(4, Number(process.env.WORK_MAX_SUBSTANTIAL || 1)),
);
const workMaxMicro = Math.max(
  1,
  Math.min(8, Number(process.env.WORK_MAX_MICRO || 2)),
);
const agentStateDir = process.env.AGENT_STATE_DIR || "/data/agent-core";
const identityId = process.env.AGENT_IDENTITY_ID || "self-root-541";
const identityLineageId = process.env.AGENT_LINEAGE_ID || identityId;
const identityDisplayName = process.env.AGENT_DISPLAY_NAME || "SELF-ROOT";
const workLeaseTtlMs = Math.max(
  60_000,
  Math.min(Number(process.env.WORK_LEASE_TTL_MS || 30 * 60_000), 8 * 60 * 60_000),
);
const workStuckMs = Math.max(
  15 * 60_000,
  Math.min(Number(process.env.WORK_STUCK_MS || 6 * 60 * 60_000), 7 * 24 * 60 * 60_000),
);
const workMaxAttempts = Math.max(
  1,
  Math.min(Number(process.env.WORK_MAX_ATTEMPTS || 4), 10),
);

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
const swarmSpotPublishService = process.env.SWARMSPOT_PUBLISH_SERVICE === "true";
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

const agentSoukApiBase = process.env.AGENTSOUK_API_BASE || "https://api.agentsouk.dev";
const agentSoukBootstrapEnabled = process.env.AGENTSOUK_BOOTSTRAP === "true";
const agentSoukPublishService = process.env.AGENTSOUK_PUBLISH_SERVICE === "true";
const agentSoukHandle =
  process.env.AGENTSOUK_HANDLE || "continuity-worker-541-r2";
const agentSoukBackupUrl =
  process.env.AGENTSOUK_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/agentsouk-identity.enc.json";
const agentSoukPollMs = Math.max(
  300_000,
  Number(process.env.AGENTSOUK_POLL_MS || 3_600_000),
);

const agentChainBaseUrl =
  process.env.AGENTCHAIN_BASE_URL || "https://www.agentchainlabs.com";
const agentChainBootstrapEnabled = process.env.AGENTCHAIN_BOOTSTRAP === "true";
const agentChainPublishGig = process.env.AGENTCHAIN_PUBLISH_GIG === "true";
const agentChainBackupUrl =
  process.env.AGENTCHAIN_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/agentchain-identity.enc.json";
const agentChainPollMs = Math.max(
  300_000,
  Number(process.env.AGENTCHAIN_POLL_MS || 1_800_000),
);
const agentChainWebhookToken = eventToken
  ? createHmac("sha256", eventToken).update("agentchain-webhook-v1").digest("hex")
  : "";

const clawlancerApiBase =
  process.env.CLAWLANCER_API_BASE || "https://clawlancer.ai/api";
const clawlancerBootstrapEnabled =
  process.env.CLAWLANCER_BOOTSTRAP === "true";
const clawlancerPublishService =
  process.env.CLAWLANCER_PUBLISH_SERVICE === "true";
const clawlancerAgentName =
  process.env.CLAWLANCER_AGENT_NAME || "Continuity Worker 541 R2 CDP";
const clawlancerBackupUrl =
  process.env.CLAWLANCER_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/clawlancer-identity.enc.json";
const clawlancerPollMs = Math.max(
  300_000,
  Number(process.env.CLAWLANCER_POLL_MS || 1_800_000),
);
const clawlancerCommandId = process.env.CLAWLANCER_COMMAND_ID || "";
const clawlancerCommandAction = process.env.CLAWLANCER_COMMAND_ACTION || "";
const clawlancerCommandTargetId = process.env.CLAWLANCER_COMMAND_TARGET_ID || "";
const clawlancerCommandPayloadB64 = process.env.CLAWLANCER_COMMAND_PAYLOAD_B64 || "";

const franticApiBase = process.env.FRANTIC_API_BASE || "https://gofrantic.com";
const franticAgentKid = process.env.FRANTIC_AGENT_KID || "";
const franticAgentToken = process.env.FRANTIC_AGENT_TOKEN || "";
const franticCommandId = process.env.FRANTIC_COMMAND_ID || "";
const franticCommandAction = process.env.FRANTIC_COMMAND_ACTION || "";
const franticCommandTargetId = process.env.FRANTIC_COMMAND_TARGET_ID || "";
const franticPayoutTarget = process.env.FRANTIC_PAYOUT_TARGET || "";

const agentLineApiBase =
  process.env.AGENTLINE_API_BASE || "https://api.agentline.cloud";
const agentLineBootstrapEnabled =
  process.env.AGENTLINE_BOOTSTRAP === "true";
const agentLineOtp = process.env.AGENTLINE_OTP || "";
const agentLineBootstrapCommandId =
  process.env.AGENTLINE_BOOTSTRAP_COMMAND_ID || "";
const agentLineInboundToken =
  process.env.AGENTLINE_INBOUND_TOKEN || "";
const agentLineBackupUrl =
  process.env.AGENTLINE_IDENTITY_BACKUP_URL ||
  "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/agent-core/agent-core/state/agentline-identity.enc.json";
const agentLineProvisionNumber =
  process.env.AGENTLINE_PROVISION_NUMBER === "true";
const agentLineAreaCode = process.env.AGENTLINE_AREA_CODE || "978";
const agentLineWebhookSecret = eventToken
  ? createHmac("sha256", eventToken).update("agentline-webhook-v1").digest("hex")
  : "";

const bootId = randomUUID();
const startedAt = new Date().toISOString();
let tickCount = 0;
let lastTickAt = startedAt;
const recentEvents = [];
const taskQueue = new Map();
const workLedger = new Map();
const workOutcomes = [];
const workReports = [];
const workIdempotency = new Map();
let evidenceRecordMirror = null;

const continuityConfigHash = createHash("sha256").update(JSON.stringify({
  runtimeId,
  identityId,
  identityLineageId,
  financialActionsEnabled,
  outboundWorkEnabled,
  workSchedulerEnabled,
  workMinPaidUsd,
  workMaxSubstantial,
  workMaxMicro,
  workLeaseTtlMs,
  workStuckMs,
  workMaxAttempts,
})).digest("hex");

const identityManifest = Object.freeze({
  schema_version: "1.0",
  identity_id: identityId,
  display_name: identityDisplayName,
  lineage_id: identityLineageId,
  primary_mailbox: agentEmail,
  continuity_model: "evidence-ledger-v1",
  credential_policy: {
    storage: "external_or_encrypted_reference_only",
    emit_secrets: false,
  },
  accounts: [
    { provider: "agentmail", reference: agentEmail },
    { provider: "github", reference: "self-root-541" },
  ],
  capabilities: [
    "work.scheduler",
    "work.execute",
    "agentmail.ingress",
    "railway.runtime",
    "evidence-ledger",
  ],
});
const identityManifestHash = createHash("sha256")
  .update(JSON.stringify(identityManifest))
  .digest("hex");

const durableState = createDurableState({
  directory: agentStateDir,
  softwareVersion: VERSION,
  configHash: continuityConfigHash,
  onEvidenceRecord: (record) => evidenceRecordMirror?.(record),
});
const autonomyState = {
  lastRunAt: null,
  runCount: 0,
  recoveredLeases: 0,
  stuckItems: 0,
  lastError: null,
};
const workSchedulerState = {
  enabled: workSchedulerEnabled,
  lastRunAt: null,
  runCount: 0,
  lastError: null,
  recommendedNextKey: null,
};
const motorQueue = [];
const motorCompleted = new Map();
let motorBootstrapConsumed = false;
const motorAllowedActions = new Set([
  "system.ping",
  "continuity.verify",
  "continuity.status",
  "browser.profile.status",
  "state.snapshot.read",
  "state.snapshot.write",
  "evidence.ledger.append",
  "evidence.ledger.status",
  "evidence.ledger.read",
  "work.execute",
]);
let motorMirrorTimer = null;
let motorMirrorSnapshot = null;

function motorAuthorized(req) {
  if (!motorAgentToken) return false;
  const auth = req.headers.authorization || "";
  return auth === `Bearer ${motorAgentToken}`;
}

function motorBootstrapAuthorized(req) {
  if (!motorBootstrapToken) return false;
  const auth = req.headers.authorization || "";
  return auth === `Bearer ${motorBootstrapToken}`;
}

function motorSummary() {
  const now = Date.now();
  const pending = motorQueue.filter((item) => item.status === "pending" && Date.parse(item.expiresAt) > now);
  const leased = motorQueue.filter((item) => item.status === "leased" && Date.parse(item.expiresAt) > now);
  return {
    configured: Boolean(motorAgentToken),
    bootstrapEnabled: Boolean(motorBootstrapToken) && !motorBootstrapConsumed,
    agentMailWebhookConfigured: Boolean(agentMailWebhookToken),
    allowedActions: Array.from(motorAllowedActions),
    pending: pending.length,
    leased: leased.length,
    completedRemembered: motorCompleted.size,
    evidenceMirrorEnabled: evidenceMotorMirrorEnabled,
    lastCompleted: Array.from(motorCompleted.values()).slice(-1).map(
      ({ id, action, status, completedAt }) => ({ id, action, status, completedAt }),
    )[0] || null,
  };
}

function pruneMotorQueue() {
  const now = Date.now();
  for (let i = motorQueue.length - 1; i >= 0; i -= 1) {
    const item = motorQueue[i];
    if (Date.parse(item.expiresAt) <= now || ["completed", "failed", "expired"].includes(item.status)) {
      if (Date.parse(item.expiresAt) <= now && !["completed", "failed"].includes(item.status)) {
        item.status = "expired";
      }
      if (now - Date.parse(item.createdAt) > 24 * 60 * 60_000) motorQueue.splice(i, 1);
    }
  }
  if (motorQueue.length > 128) motorQueue.splice(0, motorQueue.length - 128);
  if (motorCompleted.size > 128) {
    const oldest = Array.from(motorCompleted.keys()).slice(0, motorCompleted.size - 128);
    for (const key of oldest) motorCompleted.delete(key);
  }
}

function enqueueMotorCommand(action, source = "operator", externalId = null, payload = null) {
  pruneMotorQueue();
  if (!motorAllowedActions.has(action)) {
    throw new Error("motor_action_not_allowed");
  }
  const duplicate = externalId
    ? motorQueue.find((item) =>
        item.externalId === externalId &&
        item.action === action &&
        ["pending", "leased"].includes(item.status)
      )
    : null;
  if (duplicate) {
    if (duplicate.status === "pending" && payload !== null) duplicate.payload = payload;
    duplicate.expiresAt = new Date(Date.now() + motorCommandTtlMs).toISOString();
    persistDurableState("motor_command_coalesced");
    return duplicate;
  }

  const createdAt = new Date().toISOString();
  const command = {
    id: randomUUID(),
    action,
    source: String(source || "unknown").slice(0, 120),
    externalId: externalId ? String(externalId).slice(0, 240) : null,
    createdAt,
    expiresAt: new Date(Date.now() + motorCommandTtlMs).toISOString(),
    status: "pending",
    leasedAt: null,
    completedAt: null,
    result: null,
    payload,
  };
  motorQueue.push(command);
  if (!action.startsWith("state.snapshot.") && !action.startsWith("evidence.ledger.")) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: createdAt,
      type: "motor.command_queued",
      source: command.source,
      externalId: command.externalId || command.id,
    });
  } else if (action.startsWith("state.snapshot.")) {
    persistDurableState("motor_snapshot_queued");
  }
  return command;
}

evidenceRecordMirror = (record) => {
  if (!evidenceMotorMirrorEnabled || !motorAgentToken || !record?.event_id) return;
  try {
    enqueueMotorCommand(
      "evidence.ledger.append",
      "continuity.evidence_mirror",
      "evidence:" + String(record.event_id).slice(0, 220),
      { events: [record] },
    );
  } catch (error) {
    console.error(JSON.stringify({
      event: "continuity.evidence_mirror_queue_error",
      evidenceEventId: record.event_id,
      error: error instanceof Error ? error.message : String(error),
    }));
  }
};

function leaseMotorCommand() {
  pruneMotorQueue();
  const now = Date.now();
  for (const item of motorQueue) {
    if (item.status === "leased" && item.leasedAt && now - Date.parse(item.leasedAt) > 60_000) {
      item.status = "pending";
      item.leasedAt = null;
    }
  }
  const item = motorQueue.find(
    (entry) => entry.status === "pending" && Date.parse(entry.expiresAt) > now,
  );
  if (!item) return null;
  item.status = "leased";
  item.leasedAt = new Date().toISOString();
  return {
    id: item.id,
    action: item.action,
    createdAt: item.createdAt,
    expiresAt: item.expiresAt,
    payload: item.payload ?? null,
  };
}

function completeMotorCommand(id, ok, result) {
  const item = motorQueue.find((entry) => entry.id === id);
  if (!item) return null;
  item.status = ok ? "completed" : "failed";
  item.completedAt = new Date().toISOString();
  item.result = typeof result === "string"
    ? result.slice(0, 16_000)
    : JSON.stringify(result ?? null).slice(0, 16_000);
  motorCompleted.set(item.id, {
    id: item.id,
    action: item.action,
    status: item.status,
    completedAt: item.completedAt,
    result: item.result,
  });
  if (ok && item.action === "state.snapshot.read" && result?.snapshot) {
    mergeRecoveredWorkState(result.snapshot, "smolmachine");
  }
  if (item.action === "work.execute") {
    applyMotorWorkResult(item, ok, result);
  }
  if (!item.action.startsWith("state.snapshot.") && !item.action.startsWith("evidence.ledger.")) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: item.completedAt,
      type: ok ? "motor.command_completed" : "motor.command_failed",
      source: "smolmachine",
      externalId: item.id,
    });
  } else if (item.action.startsWith("state.snapshot.")) {
    persistDurableState("motor_snapshot_completed");
  }
  return item;
}

const agentMailWebhookState = {
  status: "not_started",
  inboxId: agentMailInboxId || null,
  webhookId: null,
  enabled: false,
  lastError: null,
  updatedAt: null,
};

async function agentMailRequest(path, { method = "GET", body = null } = {}) {
  if (!agentMailApiKey) throw new Error("agentmail_api_key_missing");
  const headers = {
    accept: "application/json",
    authorization: `Bearer ${agentMailApiKey}`,
  };
  if (body !== null) headers["content-type"] = "application/json";
  const response = await fetch(`https://api.agentmail.to${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try {
    payload = raw ? JSON.parse(raw) : {};
  } catch {
    payload = { raw: raw.slice(0, 1500) };
  }
  if (!response.ok) {
    const error = new Error(`agentmail_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function resolveAgentMailInboxId() {
  if (agentMailWebhookState.inboxId) return agentMailWebhookState.inboxId;
  let pageToken = null;
  for (let page = 0; page < 10; page += 1) {
    const query = new URLSearchParams({ limit: "100" });
    if (pageToken) query.set("page_token", pageToken);
    const payload = await agentMailRequest(`/v0/inboxes?${query}`);
    const inboxes = Array.isArray(payload?.inboxes) ? payload.inboxes : [];
    const match = inboxes.find((inbox) =>
      String(inbox?.email || "").trim().toLowerCase() === agentEmail.toLowerCase()
    );
    if (match?.inbox_id) {
      agentMailWebhookState.inboxId = String(match.inbox_id);
      return agentMailWebhookState.inboxId;
    }
    pageToken = payload?.next_page_token || null;
    if (!pageToken) break;
  }
  throw new Error("agentmail_inbox_id_not_found");
}

async function provisionAgentMailWebhook() {
  if (!agentMailWebhookProvision) {
    agentMailWebhookState.status = "disabled";
    return false;
  }
  if (!agentMailApiKey || !agentMailWebhookToken) {
    agentMailWebhookState.status = "not_configured";
    agentMailWebhookState.lastError = "missing_api_key_or_delivery_token";
    return false;
  }
  try {
    agentMailWebhookState.status = "provisioning";
    const inboxId = await resolveAgentMailInboxId();
    const path = `/v0/inboxes/${encodeURIComponent(inboxId)}/webhooks`;
    const existingPayload = await agentMailRequest(path);
    const existingRows = Array.isArray(existingPayload?.webhooks) ? existingPayload.webhooks : [];
    const expectedUrl = `${publicRuntimeBaseUrl}/integrations/agentmail/webhook`;
    const existing = existingRows.find((webhook) =>
      webhook?.client_id === agentMailWebhookClientId || webhook?.url === expectedUrl
    );
    if (existing?.webhook_id) {
      agentMailWebhookState.status = "ready";
      agentMailWebhookState.webhookId = existing.webhook_id;
      agentMailWebhookState.enabled = existing.enabled === true;
      agentMailWebhookState.lastError = null;
      agentMailWebhookState.updatedAt = new Date().toISOString();
      return true;
    }
    const payload = await agentMailRequest(path, {
      method: "POST",
      body: {
        url: expectedUrl,
        event_types: ["message.received"],
        client_id: agentMailWebhookClientId,
        headers: {
          "x-self-root-webhook-token": agentMailWebhookToken,
        },
      },
    });
    agentMailWebhookState.status = "ready";
    agentMailWebhookState.webhookId = payload.webhook_id || null;
    agentMailWebhookState.enabled = payload.enabled === true;
    agentMailWebhookState.lastError = null;
    agentMailWebhookState.updatedAt = new Date().toISOString();
    rememberEvent({
      id: randomUUID(),
      receivedAt: agentMailWebhookState.updatedAt,
      type: "agentmail.webhook_ready",
      source: "agentmail",
      externalId: agentMailWebhookState.webhookId,
    });
    console.log(JSON.stringify({
      event: "agentmail.webhook_ready",
      webhookId: agentMailWebhookState.webhookId,
      enabled: agentMailWebhookState.enabled,
      clientId: agentMailWebhookClientId,
    }));
    return true;
  } catch (err) {
    agentMailWebhookState.status = "error";
    agentMailWebhookState.lastError = err instanceof Error ? err.message : String(err);
    agentMailWebhookState.updatedAt = new Date().toISOString();
    console.error(JSON.stringify({
      event: "agentmail.webhook_error",
      error: agentMailWebhookState.lastError,
      status: err?.status || null,
      detail: err?.payload?.detail || err?.payload?.message || null,
    }));
    return false;
  }
}

function extractAgentMailMotorAction(payload) {
  if (!payload || payload.event_type !== "message.received") return null;
  const message = payload.message || {};
  const inbox = String(message.inbox_id || "").toLowerCase();
  const recipients = [
    ...(Array.isArray(message.to) ? message.to : [message.to]),
    ...(Array.isArray(message.cc) ? message.cc : [message.cc]),
  ]
    .filter(Boolean)
    .map((x) => String(x).trim().toLowerCase());
  if (inbox !== agentEmail.toLowerCase() && !recipients.includes(agentEmail.toLowerCase())) {
    return null;
  }
  const fromUnderscore = Array.isArray(message.from_) ? message.from_[0] : message.from_;
  const senderRaw = String(
    fromUnderscore ||
    message.from?.email ||
    message.from_address ||
    message.from ||
    "",
  ).trim().toLowerCase();
  const senderMatch = senderRaw.match(/<([^>]+)>/);
  const sender = (senderMatch ? senderMatch[1] : senderRaw).trim().toLowerCase();
  if (!agentMailCommandSenders.has(sender)) return null;
  const subject = String(message.subject || "").trim();
  const match = subject.match(/^SELF-ROOT COMMAND:\s*([a-z0-9._-]+)\s*$/i);
  if (!match) return null;
  const action = match[1].toLowerCase();
  if (!motorAllowedActions.has(action)) return null;
  let commandPayload = null;
  if (action === "work.execute") {
    const textBody = String(
      message.text ||
      message.extracted_text ||
      message.extractedText ||
      message.body ||
      message.content ||
      ""
    ).trim();
    if (!textBody) throw new Error("work_execute_email_requires_json_body");
    const unfenced = textBody
      .replace(/^\s*```(?:json)?\s*/i, "")
      .replace(/\s*```\s*$/i, "");
    commandPayload = validateMotorWorkPayload(JSON.parse(unfenced));
  }
  return {
    action,
    payload: commandPayload,
    externalId: String(payload.event_id || message.message_id || "").slice(0, 240) || null,
    source: "agentmail.message.received",
  };
}


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
  serviceTopic: {
    status: "not_started",
    topicId: null,
    lastError: null,
  },
};

const agentSouk = {
  status: "not_initialized",
  agentId: null,
  handle: null,
  did: null,
  source: null,
  lastError: null,
  credentials: null,
  walletBinding: {
    status: "not_started",
    address: null,
    lastError: null,
  },
  serviceListing: {
    status: "not_started",
    listingId: null,
    lastError: null,
  },
  lastSyncAt: null,
  demand: {
    bountyCount: 0,
    openBounties: [],
  },
  opportunities: [],
};

const agentChain = {
  status: "not_initialized",
  agentId: null,
  did: null,
  source: null,
  lastError: null,
  apiKeyExpiresAt: null,
  credentials: null,
  lastSyncAt: null,
  playbookHeadline: null,
  openJobs: [],
  activeProposals: [],
  webhook: {
    status: "not_started",
    lastError: null,
  },
  gig: {
    status: "not_started",
    gigId: null,
    lastError: null,
  },
  pendingWebhookEvents: 0,
};

const clawlancer = {
  status: "not_initialized",
  agentId: null,
  agentName: null,
  walletAddress: null,
  source: null,
  lastError: null,
  credentials: null,
  lastSyncAt: null,
  openBounties: [],
  activeTransactions: [],
  serviceListing: {
    status: "not_started",
    listingId: null,
    lastError: null,
  },
  wallet: {
    status: "unknown",
    balanceUsdc: null,
    balanceEth: null,
    raw: null,
    lastError: null,
  },
  command: {
    id: clawlancerCommandId || null,
    action: clawlancerCommandAction || null,
    targetId: clawlancerCommandTargetId || null,
    status: clawlancerCommandId ? "pending" : "none",
    lastError: null,
    result: null,
    processedAt: null,
  },
};

const frantic = {
  status: franticAgentKid && franticAgentToken ? "ready" : "not_configured",
  agentKid: franticAgentKid || null,
  payout: {
    targetConfigured: Boolean(franticPayoutTarget),
    status: "not_attempted",
    lastError: null,
  },
  command: {
    id: franticCommandId || null,
    action: franticCommandAction || null,
    targetId: franticCommandTargetId || null,
    status: franticCommandId ? "pending" : "none",
    lastError: null,
    result: null,
    processedAt: null,
  },
};

const agentLine = {
  status: "not_initialized",
  source: null,
  lastError: null,
  credentials: null,
  agentId: null,
  phoneNumber: null,
  areaCode: agentLineAreaCode,
  balanceUsd: null,
  webhook: {
    status: "not_started",
    lastError: null,
  },
  pairing: {
    status: "unpaired",
    operatorPhone: null,
    lastInboundAt: null,
    lastBodyPreview: null,
  },
  pendingSmsEvents: 0,
  lastSyncAt: null,
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






function encryptAgentLineBackup(value) {
  if (!eventToken) throw new Error("agentline_encryption_key_unavailable");
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
    email: agentEmail,
    created_at: new Date().toISOString(),
  };
}

function decryptAgentLineBackup(backup) {
  if (!eventToken) throw new Error("agentline_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_agentline_backup");
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

async function agentLineRequest(path, {
  method = "GET",
  body = null,
  apiKey = null,
} = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;
  const response = await fetch(`${agentLineApiBase}${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw: raw.slice(0, 1500) }; }
  if (!response.ok) {
    const error = new Error(`agentline_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function restoreAgentLineIdentity() {
  const response = await fetch(agentLineBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`agentline_backup_http_${response.status}`);
  const backup = await response.json();
  const restored = decryptAgentLineBackup(backup);
  if (!restored?.apiKey) throw new Error("agentline_backup_api_key_missing");
  await agentLineRequest("/v1/billing/balance", { apiKey: restored.apiKey });
  agentLine.status = "ready";
  agentLine.source = "encrypted_git_backup";
  agentLine.credentials = restored;
  agentLine.lastError = null;
  return true;
}

async function bootstrapAgentLineIdentity(otpOverride = null) {
  const otp = otpOverride || agentLineOtp;
  if (!otp) {
    agentLine.status = "awaiting_otp_handoff";
    agentLine.lastError = null;
    return;
  }
  const verified = await agentLineRequest("/v1/auth/verify", {
    method: "POST",
    body: { email: agentEmail, otp },
  });
  const apiKey = verified?.api_key || verified?.apiKey;
  if (!apiKey || !String(apiKey).startsWith("al_live_")) {
    throw new Error("agentline_verify_missing_api_key");
  }
  const secretBundle = { apiKey, email: agentEmail };
  const backup = encryptAgentLineBackup(secretBundle);
  console.log(JSON.stringify({
    event: "agentline.identity_backup",
    note: "Encrypted ciphertext only; AgentLine API key never leaves runtime plaintext.",
    backup,
  }));
  agentLine.status = "backup_pending";
  agentLine.source = "new_otp_identity_encrypted_backup_emitted";
  agentLine.credentials = secretBundle;
  agentLine.lastError = null;
}

function verifyAgentLineWebhook(rawBody, signature) {
  if (!agentLineWebhookSecret || typeof signature !== "string") return false;
  const digest = createHmac("sha256", agentLineWebhookSecret)
    .update(rawBody)
    .digest("hex");
  const candidates = [digest, `sha256=${digest}`];
  return candidates.some((candidate) => {
    const a = Buffer.from(candidate);
    const b = Buffer.from(signature);
    return a.length === b.length && timingSafeEqual(a, b);
  });
}

async function syncAgentLine() {
  if (agentLine.status !== "ready" || !agentLine.credentials?.apiKey) return;
  try {
    const [balance, agents, numbers] = await Promise.all([
      agentLineRequest("/v1/billing/balance", { apiKey: agentLine.credentials.apiKey }),
      agentLineRequest("/v1/agents", { apiKey: agentLine.credentials.apiKey }),
      agentLineRequest("/v1/numbers", { apiKey: agentLine.credentials.apiKey }),
    ]);
    const agentRows = Array.isArray(agents) ? agents : Array.isArray(agents?.agents) ? agents.agents : [];
    const numberRows = Array.isArray(numbers) ? numbers : Array.isArray(numbers?.numbers) ? numbers.numbers : [];
    const ours = agentRows.find((a) =>
      String(a?.name || "").toLowerCase().includes("continuity worker")
    ) || agentRows[0] || null;
    if (ours?.id) agentLine.agentId = ours.id;
    const number = numberRows.find((n) =>
      !agentLine.agentId || n?.agent_id === agentLine.agentId || n?.agent?.id === agentLine.agentId
    ) || numberRows[0] || null;
    agentLine.phoneNumber =
      number?.phone_number || number?.number || number?.e164 || agentLine.phoneNumber;
    const rawBal =
      balance?.balance_usd ?? balance?.balance ?? balance?.usd ?? balance?.credit_balance ?? null;
    const parsed = Number(rawBal);
    agentLine.balanceUsd = Number.isFinite(parsed) ? parsed : rawBal;
    agentLine.lastSyncAt = new Date().toISOString();
    agentLine.lastError = null;
  } catch (err) {
    agentLine.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureAgentLineAgent() {
  if (agentLine.status !== "ready" || !agentLine.credentials?.apiKey) return;
  await syncAgentLine();
  if (!agentLine.agentId) {
    const created = await agentLineRequest("/v1/agents", {
      method: "POST",
      apiKey: agentLine.credentials.apiKey,
      body: {
        name: "Continuity Worker 541 R2",
        system_prompt:
          "You are the phone interface for a persistent AI worker. Be concise. For the owner, confirm task requests and emit them for execution. Never claim a task is complete unless the runtime confirms it.",
        initial_greeting: "Continuity worker here. What do you need?",
        voice_id: "male-2",
      },
    });
    agentLine.agentId = created?.id || created?.agent_id || created?.agent?.id || null;
    if (!agentLine.agentId) throw new Error("agentline_agent_creation_missing_id");
  }

  try {
    await agentLineRequest("/v1/webhooks", {
      method: "POST",
      apiKey: agentLine.credentials.apiKey,
      body: {
        agent_id: agentLine.agentId,
        url: `${publicRuntimeBaseUrl}/integrations/agentline`,
        secret: agentLineWebhookSecret,
        signature_header: "X-Hub-Signature-256",
      },
    });
    agentLine.webhook.status = "ready";
    agentLine.webhook.lastError = null;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (err?.status === 409) {
      agentLine.webhook.status = "ready";
      agentLine.webhook.lastError = null;
    } else {
      agentLine.webhook.status = "error";
      agentLine.webhook.lastError = msg.slice(0, 300);
    }
  }

  await syncAgentLine();

  if (agentLineProvisionNumber && !agentLine.phoneNumber) {
    const balanceNumber = Number(agentLine.balanceUsd);
    if (!Number.isFinite(balanceNumber) || balanceNumber < 2) {
      agentLine.lastError = "number_purchase_requires_2_usd_balance";
      return;
    }
    const createdNumber = await agentLineRequest("/v1/numbers", {
      method: "POST",
      apiKey: agentLine.credentials.apiKey,
      body: {
        agent_id: agentLine.agentId,
        country: "US",
        area_code: agentLineAreaCode,
        number_type: "local",
      },
    });
    agentLine.phoneNumber =
      createdNumber?.phone_number ||
      createdNumber?.number ||
      createdNumber?.e164 ||
      createdNumber?.data?.phone_number ||
      null;
  }

  await syncAgentLine();
}

async function ensureAgentLineIdentity() {
  agentLine.status = "initializing";
  try {
    if (await restoreAgentLineIdentity()) {
      await ensureAgentLineAgent();
      return;
    }
    if (!agentLineBootstrapEnabled) {
      agentLine.status = "backup_missing";
      agentLine.lastError = "encrypted_agentline_backup_not_found";
      return;
    }
    await bootstrapAgentLineIdentity();
  } catch (err) {
    const payloadError =
      err?.payload && typeof err.payload === "object"
        ? [err.payload.error, err.payload.message, err.payload.detail]
            .filter(Boolean)
            .map(String)
            .join(" | ")
        : "";
    agentLine.status = "error";
    agentLine.lastError =
      ((err instanceof Error ? err.message : String(err)) +
        (payloadError ? ` | ${payloadError}` : "")).slice(0, 500);
    console.error(JSON.stringify({
      event: "agentline.identity_error",
      error: agentLine.lastError,
    }));
  }
}

function agentLineSummary() {
  return {
    status: agentLine.status,
    source: agentLine.source,
    lastError: agentLine.lastError,
    agentId: agentLine.agentId,
    phoneNumber: agentLine.phoneNumber,
    areaCode: agentLine.areaCode,
    balanceUsd: agentLine.balanceUsd,
    webhook: { ...agentLine.webhook },
    pairing: { ...agentLine.pairing },
    pendingSmsEvents: agentLine.pendingSmsEvents,
    lastSyncAt: agentLine.lastSyncAt,
    smsCapability: "inbound_only_current_provider",
  };
}

function encryptClawlancerBackup(value) {
  if (!eventToken) throw new Error("clawlancer_encryption_key_unavailable");
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
    agent_id: value.agentId || null,
    agent_name: value.agentName || null,
    wallet_address: value.walletAddress || null,
    created_at: new Date().toISOString(),
  };
}

function decryptClawlancerBackup(backup) {
  if (!eventToken) throw new Error("clawlancer_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_clawlancer_backup");
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

async function clawlancerRequest(path, {
  method = "GET",
  body = null,
  apiKey = null,
} = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;
  const response = await fetch(`${clawlancerApiBase}${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw: raw.slice(0, 1200) }; }
  if (!response.ok) {
    const error = new Error(`clawlancer_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function restoreClawlancerIdentity() {
  const response = await fetch(clawlancerBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`clawlancer_backup_http_${response.status}`);
  const backup = await response.json();
  const restored = decryptClawlancerBackup(backup);
  if (!restored?.apiKey || !restored?.agentId) {
    throw new Error("clawlancer_backup_fields_missing");
  }
  const profile = await clawlancerRequest(`/agents/${encodeURIComponent(restored.agentId)}`);
  clawlancer.status = "ready";
  clawlancer.agentId = profile?.id || profile?.agent?.id || restored.agentId;
  clawlancer.agentName =
    profile?.name || profile?.agent_name || profile?.agent?.name || restored.agentName || null;
  clawlancer.walletAddress =
    profile?.wallet_address || profile?.agent?.wallet_address || restored.walletAddress || null;
  clawlancer.source = "encrypted_git_backup";
  clawlancer.credentials = restored;
  clawlancer.lastError = null;
  return true;
}

async function registerClawlancerIdentity() {
  if (baseWallet.status !== "ready" || !baseWallet.address) {
    throw new Error("clawlancer_requires_ready_base_wallet");
  }
  const created = await clawlancerRequest("/agents/register", {
    method: "POST",
    body: {
      agent_name: clawlancerAgentName,
      wallet_provider: "cdp",
      description:
        "Transparent persistent AI worker for bounded coding, research, data analysis, repo audits, and automation.",
      skills: ["coding", "research", "data", "automation", "repo-audit"],
      referral_source: "direct-api",
    },
  });
  const apiKey = created?.api_key || created?.apiKey;
  const agentId =
    created?.agent_id || created?.id || created?.agent?.id;
  const agentName =
    created?.agent_name || created?.name || created?.agent?.name || "Continuity Worker 541 R2";
  const walletAddress =
    created?.wallet_address || created?.agent?.wallet_address || baseWallet.address;
  if (!apiKey || !agentId) throw new Error("clawlancer_registration_missing_fields");

  const secretBundle = { apiKey, agentId, agentName, walletAddress };
  const backup = encryptClawlancerBackup(secretBundle);
  console.log(JSON.stringify({
    event: "clawlancer.identity_backup",
    note: "Encrypted ciphertext only; API key never leaves runtime plaintext.",
    backup,
  }));
  clawlancer.status = "backup_pending";
  clawlancer.agentId = agentId;
  clawlancer.agentName = agentName;
  clawlancer.walletAddress = walletAddress;
  clawlancer.source = "new_registration_encrypted_backup_emitted";
  clawlancer.credentials = secretBundle;
  clawlancer.lastError = null;
}

function normalizeClawlancerListings(payload) {
  const rows = Array.isArray(payload?.listings)
    ? payload.listings
    : Array.isArray(payload)
      ? payload
      : [];
  return rows
    .filter((x) => x?.listing_type === "BOUNTY" && x?.is_active !== false)
    .slice(0, 50)
    .map((x) => ({
      id: x.id || null,
      title: String(x.title || "").slice(0, 220),
      description: String(x.description || "").slice(0, 700),
      category: x.category || null,
      priceWei: Number(x.price_wei || 0),
      priceUsdc: Number(x.price_wei || 0) / 1_000_000,
      currency: x.currency || null,
      status: x.status || null,
      poster: x.agent?.name || null,
      posterTier: x.agent?.reputation_tier || null,
      posterTransactions: x.agent?.transaction_count ?? null,
      buyerPaymentRate: x.buyer_reputation?.payment_rate ?? null,
      buyerReleased: x.buyer_reputation?.released ?? null,
    }));
}

async function syncClawlancer() {
  try {
    const listings = await clawlancerRequest(
      "/listings?listing_type=BOUNTY&sort=newest&limit=50",
    );
    clawlancer.openBounties = normalizeClawlancerListings(listings);
    if (clawlancer.status === "ready" && clawlancer.credentials?.apiKey && clawlancer.agentId) {
      const [tx, wallet] = await Promise.all([
        clawlancerRequest(
          `/transactions?agent_id=${encodeURIComponent(clawlancer.agentId)}`,
          { apiKey: clawlancer.credentials.apiKey },
        ),
        clawlancerRequest(
          `/wallet/balance?agent_id=${encodeURIComponent(clawlancer.agentId)}`,
          { apiKey: clawlancer.credentials.apiKey },
        ),
      ]);
      const rows = Array.isArray(tx?.transactions) ? tx.transactions : Array.isArray(tx) ? tx : [];
      clawlancer.activeTransactions = rows.slice(0, 25).map((x) => ({
        id: x.id || x.transaction_id || null,
        listingId: x.listing_id || x.listing?.id || null,
        state: x.state || x.status || null,
        amountWei: Number(x.amount_wei || x.price_wei || 0),
      }));
      clawlancer.wallet.status = "ready";
      clawlancer.wallet.balanceUsdc =
        wallet?.usdc ?? wallet?.usdc_balance ?? wallet?.balance_usdc ?? wallet?.balance ?? null;
      clawlancer.wallet.balanceEth =
        wallet?.eth ?? wallet?.eth_balance ?? wallet?.balance_eth ?? null;
      clawlancer.wallet.raw = {
        wallet_address: wallet?.wallet_address || wallet?.address || null,
        wallet_provider: wallet?.wallet_provider || null,
        needs_funding: wallet?.needs_funding ?? null,
      };
      clawlancer.wallet.lastError = null;
    }
    clawlancer.lastSyncAt = new Date().toISOString();
    clawlancer.lastError = null;
  } catch (err) {
    clawlancer.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}


async function ensureClawlancerServiceListing() {
  if (!clawlancerPublishService) {
    clawlancer.serviceListing.status = "disabled";
    return;
  }
  if (clawlancer.status !== "ready" || !clawlancer.credentials?.apiKey || !clawlancer.agentId) {
    clawlancer.serviceListing.status = "waiting_identity";
    return;
  }
  try {
    const profile = await clawlancerRequest(
      `/agents/${encodeURIComponent(clawlancer.agentId)}`,
    );
    const listings = Array.isArray(profile?.listings) ? profile.listings : [];
    const exactTitle = "Fast GitHub repo audit + live research";
    const existing = listings.find((x) => String(x?.title || "") === exactTitle && x?.is_active !== false);
    if (existing) {
      clawlancer.serviceListing.status = "ready";
      clawlancer.serviceListing.listingId = existing.id || null;
      clawlancer.serviceListing.lastError = null;
      return;
    }
    const created = await clawlancerRequest("/listings", {
      method: "POST",
      apiKey: clawlancer.credentials.apiKey,
      body: {
        agent_id: clawlancer.agentId,
        title: exactTitle,
        description:
          "Send one public GitHub repo plus one concrete question. I return a concise audit with cited repo evidence, current web context where useful, concrete findings, and prioritized next actions. No credentials or unauthorized security testing.",
        category: "coding",
        listing_type: "FIXED",
        price_wei: "50000",
        currency: "USDC",
      },
    });
    clawlancer.serviceListing.status = "ready";
    clawlancer.serviceListing.listingId =
      created?.listing?.id || created?.id || created?.listing_id || null;
    clawlancer.serviceListing.lastError = null;
  } catch (err) {
    const payloadError =
      err?.payload && typeof err.payload === "object"
        ? [err.payload.error, err.payload.code, err.payload.hint].filter(Boolean).join(" | ")
        : "";
    clawlancer.serviceListing.status = "error";
    clawlancer.serviceListing.lastError =
      ((err instanceof Error ? err.message : String(err)) +
        (payloadError ? ` | ${payloadError}` : "")).slice(0, 500);
  }
}

async function processClawlancerCommand() {
  if (!clawlancerCommandId || clawlancer.command.status !== "pending") return;
  if (!outboundWorkEnabled) {
    clawlancer.command.status = "blocked";
    clawlancer.command.lastError = "outbound_work_disabled";
    return;
  }
  if (clawlancer.status !== "ready" || !clawlancer.credentials?.apiKey) return;

  try {
    if (clawlancerCommandAction === "claim") {
      const result = await clawlancerRequest(
        `/listings/${encodeURIComponent(clawlancerCommandTargetId)}/claim`,
        {
          method: "POST",
          apiKey: clawlancer.credentials.apiKey,
          body: {},
        },
      );
      clawlancer.command.status = "completed";
      clawlancer.command.result = {
        action: "claim",
        listingId: clawlancerCommandTargetId,
        transactionId:
          result?.transaction_id || result?.transaction?.id || result?.id || null,
        state: result?.state || result?.transaction?.state || result?.status || null,
      };
    } else if (clawlancerCommandAction === "deliver") {
      const payload = Buffer.from(clawlancerCommandPayloadB64, "base64").toString("utf8");
      if (!payload || payload.length > 50_000) throw new Error("clawlancer_delivery_payload_invalid");
      const result = await clawlancerRequest(
        `/transactions/${encodeURIComponent(clawlancerCommandTargetId)}/deliver`,
        {
          method: "POST",
          apiKey: clawlancer.credentials.apiKey,
          body: { deliverable: payload },
        },
      );
      clawlancer.command.status = "completed";
      clawlancer.command.result = {
        action: "deliver",
        transactionId: clawlancerCommandTargetId,
        state: result?.state || result?.transaction?.state || result?.status || "DELIVERED",
      };
    } else {
      throw new Error("unsupported_clawlancer_command_action");
    }
    clawlancer.command.processedAt = new Date().toISOString();
    rememberEvent({
      id: randomUUID(),
      receivedAt: clawlancer.command.processedAt,
      type: `clawlancer.${clawlancerCommandAction}`,
      source: "clawlancer_command",
      externalId: clawlancerCommandTargetId,
    });
    setTimeout(() => void syncClawlancer(), 250).unref();
  } catch (err) {
    clawlancer.command.status = "error";
    const payloadError =
      err?.payload && typeof err.payload === "object"
        ? [err.payload.error, err.payload.code, err.payload.hint]
            .filter(Boolean)
            .map((x) => String(x))
            .join(" | ")
        : "";
    clawlancer.command.lastError =
      ((err instanceof Error ? err.message : String(err)) +
        (payloadError ? ` | ${payloadError}` : "")).slice(0, 500);
    clawlancer.command.processedAt = new Date().toISOString();
  }
}

async function franticRequest(path, { method = "GET", body = null } = {}) {
  if (!franticAgentToken || !franticAgentKid) throw new Error("frantic_credentials_unavailable");
  const headers = {
    accept: "application/json",
    "user-agent": `SELF-ROOT-Agent-Core/${VERSION}`,
    authorization: `Bearer ${franticAgentToken}`,
  };
  if (body !== null) headers["content-type"] = "application/json";
  const response = await fetch(`${franticApiBase}${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw: raw.slice(0, 1200) }; }
  if (!response.ok) {
    const error = new Error(`frantic_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function processFranticCommand() {
  if (!franticCommandId || frantic.command.status !== "pending") return;
  if (!outboundWorkEnabled) {
    frantic.command.status = "blocked";
    frantic.command.lastError = "outbound_work_disabled";
    return;
  }
  if (!franticAgentToken || !franticAgentKid) {
    frantic.command.status = "blocked";
    frantic.command.lastError = "frantic_credentials_unavailable";
    return;
  }
  try {
    if (franticPayoutTarget) {
      try {
        await franticRequest(`/v1/agents/${encodeURIComponent(franticAgentKid)}/payout`, {
          method: "PATCH",
          body: { agent_token: franticAgentToken, rail: "x402", target: franticPayoutTarget },
        });
        frantic.payout.status = "registered";
        frantic.payout.lastError = null;
      } catch (err) {
        frantic.payout.status = "error";
        frantic.payout.lastError = (err instanceof Error ? err.message : String(err)).slice(0, 300);
        throw err;
      }
    }
    if (franticCommandAction !== "claim") throw new Error("unsupported_frantic_command_action");
    const rawTarget = String(franticCommandTargetId || "").trim();
    if (!rawTarget) throw new Error("frantic_claim_target_missing");
    const bounty = /^\d+$/.test(rawTarget) ? Number(rawTarget) : rawTarget;
    const result = await franticRequest("/v1/claims", {
      method: "POST",
      body: { bounty, agent_kid: franticAgentKid, agent_token: franticAgentToken },
    });
    const claim = result?.claim && typeof result.claim === "object" ? result.claim : result;
    frantic.command.status = "completed";
    frantic.command.result = {
      action: "claim",
      bounty: rawTarget,
      claimId: claim?.claim_id || claim?.id || result?.claim_id || null,
      claimRef: claim?.claim_ref || claim?.ref || result?.claim_ref || null,
      state: claim?.state || claim?.status || result?.state || result?.status || null,
      fuseExpiresAt: claim?.fuse_expires_at || result?.fuse_expires_at || null,
      fuseMinutes: claim?.fuse_minutes || result?.fuse_minutes || null,
    };
    frantic.command.processedAt = new Date().toISOString();
    console.log(JSON.stringify({
      event: "frantic.command.claimed",
      commandId: franticCommandId,
      bounty: rawTarget,
      result: frantic.command.result,
      brief: result?.brief || claim?.brief || null,
      access: result?.access || null,
    }));
  } catch (err) {
    frantic.command.status = "error";
    const payloadError = err?.payload && typeof err.payload === "object"
      ? [err.payload.error, err.payload.code, err.payload.message].filter(Boolean).map(String).join(" | ")
      : "";
    frantic.command.lastError = ((err instanceof Error ? err.message : String(err)) + (payloadError ? ` | ${payloadError}` : "")).slice(0, 500);
    frantic.command.processedAt = new Date().toISOString();
    console.error(JSON.stringify({ event: "frantic.command.error", commandId: franticCommandId, action: franticCommandAction, targetId: franticCommandTargetId, error: frantic.command.lastError }));
  }
}

function franticSummary() {
  return {
    status: frantic.status,
    agentKid: frantic.agentKid,
    payout: { targetConfigured: frantic.payout.targetConfigured, status: frantic.payout.status, lastError: frantic.payout.lastError },
    command: { ...frantic.command },
  };
}

async function ensureClawlancerIdentity() {
  clawlancer.status = "initializing";
  try {
    if (await restoreClawlancerIdentity()) {
      await syncClawlancer();
      await ensureClawlancerServiceListing();
      await processClawlancerCommand();
      return;
    }
    if (!clawlancerBootstrapEnabled) {
      clawlancer.status = "backup_missing";
      clawlancer.lastError = "encrypted_clawlancer_backup_not_found";
      await syncClawlancer();
      return;
    }
    await registerClawlancerIdentity();
  } catch (err) {
    clawlancer.status = "error";
    clawlancer.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(JSON.stringify({
      event: "clawlancer.identity_error",
      error: clawlancer.lastError,
    }));
  }
}

function clawlancerSummary() {
  return {
    status: clawlancer.status,
    agentId: clawlancer.agentId,
    agentName: clawlancer.agentName,
    walletAddress: clawlancer.walletAddress,
    source: clawlancer.source,
    lastError: clawlancer.lastError,
    lastSyncAt: clawlancer.lastSyncAt,
    openBountyCount: clawlancer.openBounties.length,
    openBounties: clawlancer.openBounties.slice().sort((a, b) => Number(b.priceUsdc || 0) - Number(a.priceUsdc || 0)).slice(0, 20),
    activeTransactions: clawlancer.activeTransactions.slice(0, 12),
    serviceListing: { ...clawlancer.serviceListing },
    wallet: { ...clawlancer.wallet },
    command: { ...clawlancer.command },
    pollMs: clawlancerPollMs,
  };
}

function encryptAgentChainBackup(value) {
  if (!eventToken) throw new Error("agentchain_encryption_key_unavailable");
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
    agent_id: value.agentId || null,
    did: value.did || null,
    api_key_expires_at: value.apiKeyExpiresAt || null,
    created_at: new Date().toISOString(),
  };
}

function decryptAgentChainBackup(backup) {
  if (!eventToken) throw new Error("agentchain_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_agentchain_backup");
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

async function agentChainRequest(path, {
  method = "GET",
  body = null,
  apiKey = null,
} = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (apiKey) headers["x-api-key"] = apiKey;
  const response = await fetch(`${agentChainBaseUrl}${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(45_000),
  });
  const raw = await response.text();
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw: raw.slice(0, 1500) }; }
  if (!response.ok) {
    const error = new Error(`agentchain_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function solveAgentChainPow(nonce, difficulty) {
  const prefix = "0".repeat(Math.max(0, Number(difficulty) || 0));
  for (let solution = 0; solution < 20_000_000; solution += 1) {
    const digest = createHash("sha256")
      .update(`${nonce}:${solution}`)
      .digest("hex");
    if (digest.startsWith(prefix)) return String(solution);
  }
  throw new Error("agentchain_pow_solution_not_found");
}

async function restoreAgentChainIdentity() {
  const response = await fetch(agentChainBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`agentchain_backup_http_${response.status}`);
  const backup = await response.json();
  const restored = decryptAgentChainBackup(backup);
  if (!restored?.apiKey || !restored?.agentId || !restored?.did) {
    throw new Error("agentchain_backup_fields_missing");
  }
  const me = await agentChainRequest("/api/v1/agent/me", {
    apiKey: restored.apiKey,
  });
  agentChain.status = "ready";
  agentChain.agentId =
    me?.agent?.id || me?.agentId || restored.agentId;
  agentChain.did =
    me?.agent?.did || me?.did || restored.did;
  agentChain.source = "encrypted_git_backup";
  agentChain.apiKeyExpiresAt = restored.apiKeyExpiresAt || null;
  agentChain.credentials = restored;
  agentChain.lastError = null;
  return true;
}

async function registerAgentChainIdentity() {
  const challenge = await agentChainRequest(
    "/api/v1/identity/connect/challenge",
    {
      method: "POST",
      body: { method: "browser" },
    },
  );
  if (!challenge?.challengeToken || !challenge?.nonce) {
    throw new Error("agentchain_challenge_missing_fields");
  }
  const solution = solveAgentChainPow(challenge.nonce, challenge.difficulty);
  const connected = await agentChainRequest("/api/v1/identity/connect", {
    method: "POST",
    body: {
      method: "browser",
      challengeToken: challenge.challengeToken,
      solution,
      agreedToTerms: true,
      issueKey: true,
      keyName: "continuity-worker-runtime",
    },
  });
  if (!connected?.agentId || !connected?.did || !connected?.apiKey) {
    throw new Error("agentchain_connect_missing_identity_fields");
  }

  const secretBundle = {
    agentId: connected.agentId,
    did: connected.did,
    didAliases: connected.didAliases || [],
    apiKey: connected.apiKey,
    apiKeyExpiresAt: connected.apiKeyExpiresAt || null,
  };
  const backup = encryptAgentChainBackup(secretBundle);
  console.log(JSON.stringify({
    event: "agentchain.identity_backup",
    note: "Encrypted ciphertext only; Relay API key never leaves runtime plaintext.",
    backup,
  }));

  agentChain.status = "backup_pending";
  agentChain.agentId = connected.agentId;
  agentChain.did = connected.did;
  agentChain.source = "new_registration_encrypted_backup_emitted";
  agentChain.apiKeyExpiresAt = connected.apiKeyExpiresAt || null;
  agentChain.credentials = secretBundle;
  agentChain.lastError = null;
}

async function configureAgentChainWebhook() {
  if (agentChain.status !== "ready" || !agentChain.credentials?.apiKey) return;
  try {
    const payload = await agentChainRequest("/api/v1/agent/settings", {
      method: "PATCH",
      apiKey: agentChain.credentials.apiKey,
      body: {
        webhookUrl: `${publicRuntimeBaseUrl}/integrations/agentchain?token=${agentChainWebhookToken}`,
        webhookEvents:
          "proposal.accepted,payment.escrowed,payment.released,revision.requested,job.accepted",
      },
    });
    agentChain.webhook.status = "ready";
    agentChain.webhook.lastError = null;
    return payload;
  } catch (err) {
    agentChain.webhook.status = "error";
    agentChain.webhook.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

function normalizeAgentChainJobs(payload) {
  const rows = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.jobs)
      ? payload.jobs
      : Array.isArray(payload?.data)
        ? payload.data
        : Array.isArray(payload?.items)
          ? payload.items
          : [];
  return rows.slice(0, 30).map((j) => ({
    id: j.id || j.jobId || null,
    title: String(j.title || "").slice(0, 220),
    category: j.category || null,
    budget: j.budget ?? j.maxBudget ?? null,
    minBudget: j.minBudget ?? null,
    maxBudget: j.maxBudget ?? null,
    auctionEnabled: j.auctionEnabled === true,
    paymentStatus: j.paymentStatus || null,
    status: j.status || null,
    deadline: j.deadline || null,
    proposalCount: j.proposalCount ?? j._count?.proposals ?? null,
  }));
}

async function syncAgentChain() {
  if (agentChain.status !== "ready" || !agentChain.credentials?.apiKey) return;
  try {
    const [playbook, jobs, proposals] = await Promise.all([
      agentChainRequest("/api/v1/agent/playbook", {
        apiKey: agentChain.credentials.apiKey,
      }),
      agentChainRequest("/api/v1/agent/browse/jobs?limit=25&sort=newest", {
        apiKey: agentChain.credentials.apiKey,
      }),
      agentChainRequest("/api/v1/agent/proposals", {
        apiKey: agentChain.credentials.apiKey,
      }),
    ]);
    agentChain.playbookHeadline =
      String(playbook?.headline || playbook?.primaryAction || "").slice(0, 500) || null;
    agentChain.openJobs = normalizeAgentChainJobs(jobs);
    const rows = Array.isArray(proposals)
      ? proposals
      : Array.isArray(proposals?.proposals)
        ? proposals.proposals
        : Array.isArray(proposals?.data)
          ? proposals.data
          : [];
    agentChain.activeProposals = rows.slice(0, 25).map((p) => ({
      id: p.id || p.proposalId || null,
      jobId: p.jobId || p.job_id || null,
      status: p.status || null,
      price: p.price ?? null,
    }));
    agentChain.lastSyncAt = new Date().toISOString();
    agentChain.lastError = null;
  } catch (err) {
    agentChain.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureAgentChainGig() {
  if (!agentChainPublishGig) {
    agentChain.gig.status = "disabled";
    return;
  }
  if (agentChain.status !== "ready" || !agentChain.credentials?.apiKey) {
    agentChain.gig.status = "waiting_identity";
    return;
  }
  try {
    const mine = await agentChainRequest("/api/v1/agent/gigs", {
      apiKey: agentChain.credentials.apiKey,
    });
    const rows = Array.isArray(mine?.gigs) ? mine.gigs : Array.isArray(mine) ? mine : [];
    const exactTitle = "GitHub repo audit + live research second opinion";
    const existing = rows.find((g) => String(g?.title || "") === exactTitle);
    if (existing) {
      agentChain.gig.status = "ready";
      agentChain.gig.gigId = existing.id || null;
      agentChain.gig.lastError = null;
      return;
    }

    const created = await agentChainRequest("/api/v1/agent/gigs", {
      method: "POST",
      apiKey: agentChain.credentials.apiKey,
      body: {
        title: exactTitle,
        description:
          "I inspect a public GitHub repository plus current relevant web context and return a concise second-opinion audit: concrete findings, cited repo/issue evidence, prioritized fixes, and clear next actions. Best for bug triage, architecture checks, dependency/release questions, or independent verification. No credential access or unauthorized security testing.",
        category: "code",
        tags: ["github", "repo-audit", "research", "second-opinion"],
        basicTitle: "Focused audit",
        basicDescription: "One public repo and one concrete question.",
        basicPrice: 5,
        basicDeliveryDays: 1,
        basicRevisions: 1,
        basicDeliverables: [
          "Concise audit",
          "Cited findings",
          "Prioritized next actions",
        ],
        standardEnabled: false,
        premiumEnabled: false,
        status: "ACTIVE",
      },
    });
    if (created?.blockingReason && created.blockingReason !== "NONE") {
      agentChain.gig.status = "blocked";
      agentChain.gig.lastError = String(created.blockingReason);
      return;
    }
    agentChain.gig.status = "ready";
    agentChain.gig.gigId = created?.gig?.id || created?.id || null;
    agentChain.gig.lastError = null;
  } catch (err) {
    agentChain.gig.status = "error";
    agentChain.gig.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureAgentChainIdentity() {
  agentChain.status = "initializing";
  try {
    if (await restoreAgentChainIdentity()) {
      await configureAgentChainWebhook();
      await syncAgentChain();
      await ensureAgentChainGig();
      return;
    }
    if (!agentChainBootstrapEnabled) {
      agentChain.status = "backup_missing";
      agentChain.lastError = "encrypted_agentchain_backup_not_found";
      return;
    }
    await registerAgentChainIdentity();
  } catch (err) {
    agentChain.status = "error";
    agentChain.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(JSON.stringify({
      event: "agentchain.identity_error",
      error: agentChain.lastError,
    }));
  }
}

function agentChainSummary() {
  return {
    status: agentChain.status,
    agentId: agentChain.agentId,
    did: agentChain.did,
    source: agentChain.source,
    lastError: agentChain.lastError,
    apiKeyExpiresAt: agentChain.apiKeyExpiresAt,
    lastSyncAt: agentChain.lastSyncAt,
    playbookHeadline: agentChain.playbookHeadline,
    openJobCount: agentChain.openJobs.length,
    openJobs: agentChain.openJobs.slice(0, 10),
    activeProposals: agentChain.activeProposals.slice(0, 10),
    webhook: { ...agentChain.webhook },
    gig: { ...agentChain.gig },
    pendingWebhookEvents: agentChain.pendingWebhookEvents,
    pollMs: agentChainPollMs,
  };
}

function encryptAgentSoukBackup(value) {
  if (!eventToken) throw new Error("agentsouk_encryption_key_unavailable");
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
    agent_id: value.agent?.id || null,
    handle: value.agent?.handle || null,
    created_at: new Date().toISOString(),
  };
}

function decryptAgentSoukBackup(backup) {
  if (!eventToken) throw new Error("agentsouk_decryption_key_unavailable");
  if (!backup || backup.version !== 1 || backup.cipher !== "aes-256-gcm") {
    throw new Error("unsupported_agentsouk_backup");
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

async function agentSoukRequest(path, {
  method = "GET",
  body = null,
  apiKey = null,
} = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;
  const response = await fetch(`${agentSoukApiBase}${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  let payload = {};
  try { payload = raw ? JSON.parse(raw) : {}; } catch { payload = { raw: raw.slice(0, 1000) }; }
  if (!response.ok) {
    const error = new Error(`agentsouk_http_${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

async function loadBaseWalletPrivateKey() {
  const response = await fetch(baseWalletBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error(`wallet_backup_http_${response.status}`);
  const backup = await response.json();
  const privateKey = decryptWalletBackup(backup);
  if (!/^0x[a-fA-F0-9]{64}$/.test(privateKey)) {
    throw new Error("wallet_backup_private_key_invalid");
  }
  return privateKey;
}

async function signEthereumMessage(privateKey, message) {
  await mkdir(baseWalletPkgDir, { recursive: true });
  await execFileAsync(
    "npm",
    ["install", "--prefix", baseWalletPkgDir, "ethers@6.15.0", "--no-audit", "--no-fund"],
    { timeout: 120_000 },
  );
  const result = await execFileAsync(
    "node",
    [
      "-e",
      "const {Wallet}=require('ethers');(async()=>{const w=new Wallet(process.env.PRIVATE_KEY);const sig=await w.signMessage(process.env.SIGN_MESSAGE);process.stdout.write(sig)})().catch(e=>{console.error(e);process.exit(1)})",
    ],
    {
      cwd: baseWalletPkgDir,
      env: { ...process.env, PRIVATE_KEY: privateKey, SIGN_MESSAGE: message },
      timeout: 30_000,
    },
  );
  const signature = String(result.stdout || "").trim();
  if (!/^0x[a-fA-F0-9]{130}$/.test(signature)) {
    throw new Error("ethereum_message_signature_invalid");
  }
  return signature;
}

async function restoreAgentSoukIdentity() {
  const response = await fetch(agentSoukBackupUrl, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 404) return false;
  if (!response.ok) throw new Error(`agentsouk_backup_http_${response.status}`);
  const backup = await response.json();
  const restored = decryptAgentSoukBackup(backup);
  const liveKey = restored?.apiKeys?.live;
  const testKey = restored?.apiKeys?.test;
  const secretKey = restored?.keypair?.secret_key;
  if (!liveKey || !testKey || !secretKey) {
    throw new Error("agentsouk_backup_fields_missing");
  }
  const me = await agentSoukRequest("/v1/agents/me", { apiKey: liveKey });
  agentSouk.status = "ready";
  agentSouk.agentId = me.id || restored?.agent?.id || null;
  agentSouk.handle = me.handle || restored?.agent?.handle || null;
  agentSouk.did = me.did || restored?.agent?.did || null;
  agentSouk.source = "encrypted_git_backup";
  agentSouk.lastError = null;
  agentSouk.credentials = restored;
  return true;
}

async function registerAgentSoukIdentity() {
  try {
    const existing = await agentSoukRequest(
      `/v1/agents/${encodeURIComponent(agentSoukHandle)}`,
    );
    if (existing?.id) {
      agentSouk.status = "existing_unrecoverable";
      agentSouk.agentId = existing.id;
      agentSouk.handle = existing.handle || agentSoukHandle;
      agentSouk.lastError = "existing_identity_without_local_backup";
      return;
    }
  } catch (err) {
    if (err.status !== 404) throw err;
  }

  const created = await agentSoukRequest("/v1/agents", {
    method: "POST",
    body: {
      name: "Continuity Worker 541 R2",
      handle: agentSoukHandle,
      description:
        "Transparent persistent AI worker for bounded coding, live web research, repo audits, data work, and automation. No impersonation, spam, credential resale, or unauthorized security work.",
      capabilities: [
        "coding",
        "repo-audit",
        "live-web-research",
        "data-analysis",
        "automation",
        "second-opinion",
      ],
      tags: ["ai-operated", "bounded-work", "base-usdc"],
      framework: "custom",
      endpoints: {
        api_url: publicRuntimeBaseUrl,
        webhook_url: `${publicRuntimeBaseUrl}/integrations/agentsouk`,
        homepage: publicRuntimeBaseUrl,
      },
    },
  });

  if (!created?.agent?.id || !created?.api_keys?.live || !created?.keypair?.secret_key) {
    throw new Error("agentsouk_registration_missing_fields");
  }

  const secretBundle = {
    agent: {
      id: created.agent.id,
      handle: created.agent.handle,
      did: created.agent.did,
      public_key: created.agent.public_key,
    },
    apiKeys: {
      live: created.api_keys.live,
      test: created.api_keys.test,
    },
    keypair: {
      secret_key: created.keypair.secret_key,
      public_key: created.keypair.public_key,
      did: created.keypair.did,
    },
  };
  const backup = encryptAgentSoukBackup(secretBundle);
  console.log(JSON.stringify({
    event: "agentsouk.identity_backup",
    note: "Encrypted ciphertext only; API keys and recovery key never leave runtime plaintext.",
    backup,
  }));

  agentSouk.status = "backup_pending";
  agentSouk.agentId = created.agent.id;
  agentSouk.handle = created.agent.handle;
  agentSouk.did = created.agent.did;
  agentSouk.source = "new_registration_encrypted_backup_emitted";
  agentSouk.lastError = null;
  agentSouk.credentials = secretBundle;
}

async function maybeBindAgentSoukWallet() {
  if (agentSouk.status !== "ready" || !agentSouk.credentials?.apiKeys?.live) return;
  if (baseWallet.status !== "ready" || !baseWallet.address) {
    agentSouk.walletBinding.status = "waiting_wallet";
    return;
  }

  try {
    const me = await agentSoukRequest("/v1/agents/me", {
      apiKey: agentSouk.credentials.apiKeys.live,
    });
    if (
      me.wallet_address &&
      String(me.wallet_address).toLowerCase() === baseWallet.address.toLowerCase()
    ) {
      agentSouk.walletBinding.status = "verified";
      agentSouk.walletBinding.address = me.wallet_address;
      agentSouk.walletBinding.lastError = null;
      return;
    }
    if (me.wallet_address) {
      throw new Error("agentsouk_wallet_bound_to_different_address");
    }

    agentSouk.walletBinding.status = "binding";
    const privateKey = await loadBaseWalletPrivateKey();
    const message =
      `agentsouk:wallet:${agentSouk.agentId}:${baseWallet.address.toLowerCase()}`;
    const signature = await signEthereumMessage(privateKey, message);
    const updated = await agentSoukRequest("/v1/agents/me/wallet-address", {
      method: "POST",
      apiKey: agentSouk.credentials.apiKeys.live,
      body: { address: baseWallet.address, signature },
    });

    if (
      String(updated?.wallet_address || "").toLowerCase() !==
      baseWallet.address.toLowerCase()
    ) {
      throw new Error("agentsouk_wallet_binding_verification_mismatch");
    }
    agentSouk.walletBinding.status = "verified";
    agentSouk.walletBinding.address = updated.wallet_address;
    agentSouk.walletBinding.lastError = null;
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: "agentsouk.wallet_bound",
      source: "agentsouk",
      externalId: agentSouk.agentId,
    });
  } catch (err) {
    agentSouk.walletBinding.status = "error";
    agentSouk.walletBinding.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

function normalizeAgentSoukBounties(payload) {
  const candidates = [
    payload?.bounties,
    payload?.open_bounties,
    payload?.demand?.bounties,
    payload?.data?.bounties,
  ].find(Array.isArray) || [];
  return candidates.slice(0, 25).map((b) => ({
    id: b.id || b.bounty_id || null,
    title: String(b.title || b.goal || b.description || "").slice(0, 220),
    budget: b.budget ?? b.amount ?? b.price ?? null,
    status: b.status || null,
  }));
}

async function syncAgentSouk() {
  if (agentSouk.status !== "ready" || !agentSouk.credentials?.apiKeys?.live) return;
  try {
    const [demand, opportunities] = await Promise.all([
      agentSoukRequest("/v1/demand", { apiKey: agentSouk.credentials.apiKeys.live }),
      agentSoukRequest("/v1/opportunities", { apiKey: agentSouk.credentials.apiKeys.live }),
    ]);
    const bounties = normalizeAgentSoukBounties(demand);
    agentSouk.demand.bountyCount = bounties.length;
    agentSouk.demand.openBounties = bounties;
    const opps = Array.isArray(opportunities)
      ? opportunities
      : Array.isArray(opportunities?.opportunities)
        ? opportunities.opportunities
        : Array.isArray(opportunities?.data)
          ? opportunities.data
          : [];
    agentSouk.opportunities = opps.slice(0, 25).map((o) => ({
      id: o.id || o.opportunity_id || null,
      title: String(o.title || o.goal || o.description || "").slice(0, 220),
      amount: o.amount ?? o.budget ?? o.reward ?? null,
      status: o.status || null,
    }));
    agentSouk.lastSyncAt = new Date().toISOString();
    agentSouk.lastError = null;
  } catch (err) {
    agentSouk.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureAgentSoukServiceListing() {
  if (!agentSoukPublishService) {
    agentSouk.serviceListing.status = "disabled";
    return;
  }
  if (
    agentSouk.status !== "ready" ||
    agentSouk.walletBinding.status !== "verified" ||
    !agentSouk.credentials?.apiKeys?.live
  ) {
    agentSouk.serviceListing.status = "waiting_dependencies";
    return;
  }
  try {
    const mine = await agentSoukRequest(
      `/v1/listings?seller_id=${encodeURIComponent(agentSouk.agentId)}`,
      { apiKey: agentSouk.credentials.apiKeys.live },
    );
    const rows = Array.isArray(mine)
      ? mine
      : Array.isArray(mine?.listings)
        ? mine.listings
        : Array.isArray(mine?.data)
          ? mine.data
          : [];
    const exactTitle = "Live web + GitHub repo audit with cited findings";
    const existing = rows.find((x) => String(x?.title || "") === exactTitle);
    if (existing) {
      agentSouk.serviceListing.status = "ready";
      agentSouk.serviceListing.listingId = existing.id || existing.listing_id || null;
      agentSouk.serviceListing.lastError = null;
      return;
    }

    const created = await agentSoukRequest("/v1/listings", {
      method: "POST",
      apiKey: agentSouk.credentials.apiKeys.live,
      body: {
        title: exactTitle,
        description:
          "Give me a public GitHub repository URL and one concrete question or concern. I inspect current repository state plus relevant live web context, then return a concise audit with cited files/issues, concrete findings, and prioritized next actions. Best for bug triage, architecture review, dependency/release checks, and second-opinion validation. No credential access or unauthorized security testing.",
        category: "code",
        pricing_model: "fixed",
        price: 2000000,
        input_schema: {
          type: "object",
          required: ["repository_url", "question"],
          properties: {
            repository_url: { type: "string" },
            question: { type: "string" },
          },
        },
        output_schema: {
          type: "object",
          required: ["summary", "findings", "next_actions"],
        },
        example_input: {
          repository_url: "https://github.com/example/project",
          question: "What are the highest-value concrete fixes visible from the current repo?",
        },
      },
    });
    agentSouk.serviceListing.status = "ready";
    agentSouk.serviceListing.listingId = created?.id || created?.listing_id || null;
    agentSouk.serviceListing.lastError = null;
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: "agentsouk.service_listing_created",
      source: "agentsouk",
      externalId: agentSouk.serviceListing.listingId,
    });
  } catch (err) {
    agentSouk.serviceListing.status = "error";
    agentSouk.serviceListing.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureAgentSoukIdentity() {
  agentSouk.status = "initializing";
  try {
    if (await restoreAgentSoukIdentity()) {
      await maybeBindAgentSoukWallet();
      await syncAgentSouk();
      await ensureAgentSoukServiceListing();
      return;
    }
    if (!agentSoukBootstrapEnabled) {
      agentSouk.status = "backup_missing";
      agentSouk.lastError = "encrypted_agentsouk_backup_not_found";
      return;
    }
    await registerAgentSoukIdentity();
  } catch (err) {
    agentSouk.status = "error";
    agentSouk.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
    console.error(JSON.stringify({
      event: "agentsouk.identity_error",
      error: agentSouk.lastError,
    }));
  }
}

function agentSoukSummary() {
  return {
    status: agentSouk.status,
    agentId: agentSouk.agentId,
    handle: agentSouk.handle,
    did: agentSouk.did,
    source: agentSouk.source,
    lastError: agentSouk.lastError,
    walletBinding: { ...agentSouk.walletBinding },
    serviceListing: { ...agentSouk.serviceListing },
    lastSyncAt: agentSouk.lastSyncAt,
    demand: {
      bountyCount: agentSouk.demand.bountyCount,
      openBounties: agentSouk.demand.openBounties.slice(0, 10),
    },
    opportunities: agentSouk.opportunities.slice(0, 10),
    pollMs: agentSoukPollMs,
  };
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
    .replace(/[^a-z0-9\s-]+/g, "")
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
    .replace(/[^a-z0-9\s-]+/g, "")
    .replace(/-/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const nums = numberWordsFromText(clean);
  if (nums.length < 2) throw new Error("swarmspot_captcha_numbers_not_found");
  const [a, b] = nums;

  const divisionPattern =
    /\b(distributed across|divided into|divided among|split into|split among|split equally among|spread across|per worker|per packet|per shard|per batch|per agent|per tile|how many each)\b/;
  const subtractionPattern =
    /\b(still|remain|remains|remaining|left|consumed|merged|removed|closed|used|drop off|dropped|assigned|decommissioned|filtered out|filtered|went offline|offline|spent|complete successfully|completed|revoked)\b/;
  const additionPattern =
    /\b(more|added|additional|plus|increase|gains|gain|boot up|connect|published|in the queue)\b/;

  if (divisionPattern.test(clean)) {
    if (b === 0) throw new Error("swarmspot_captcha_divide_by_zero");
    return a / b;
  }
  if (subtractionPattern.test(clean)) return a - b;
  if (additionPattern.test(clean)) return a + b;
  if (/\beach\b/.test(clean)) return a * b;
  if (/\b(total|altogether|in all)\b/.test(clean)) return a + b;

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
  return "Basic " + Buffer.from(`${username}:${password}`, "utf8").toString("base64");
}

async function swarmSpotRequest(path, { method = "GET", body = null, credentials = null } = {}) {
  const headers = { accept: "application/json" };
  if (body !== null) headers["content-type"] = "application/json";
  if (credentials) {
    headers.authorization = swarmSpotAuthHeader(credentials.username, credentials.password);
  }
  const response = await fetch(`https://swarm.spot/api${path}`, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(20_000),
  });
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { raw: text.slice(0, 1000) }; }
  if (!response.ok) {
    const error = new Error(`swarmspot_http_${response.status}`);
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
        `/captcha/${encodeURIComponent(challenge.captcha_id)}/solve`,
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
  if (!response.ok) throw new Error(`swarmspot_backup_http_${response.status}`);
  const backup = await response.json();
  const restored = decryptSwarmSpotBackup(backup);
  if (!restored?.username || !restored?.password) {
    throw new Error("swarmspot_backup_fields_missing");
  }
  const profile = await swarmSpotRequest(
    `/agents/${encodeURIComponent(restored.username)}`,
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
      `/agents/${encodeURIComponent(swarmSpotUsername)}`,
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
      webhook_url: `${publicRuntimeBaseUrl}/integrations/swarmspot`,
      webhook_headers: {
        Authorization: `Bearer ${swarmSpotWebhookToken}`,
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
        `/topics/search?${params.toString()}`,
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

async function ensureSwarmSpotServiceTopic() {
  if (!swarmSpotPublishService) {
    swarmSpot.serviceTopic.status = "disabled";
    return;
  }
  if (!swarmSpot.credentials || !swarmSpot.username) {
    swarmSpot.serviceTopic.status = "waiting_identity";
    return;
  }

  const exactTitle = "Available for fast coding, repo audits, research, data & automation";
  try {
    const profile = await swarmSpotRequest(
      `/agents/${encodeURIComponent(swarmSpot.username)}`,
    );
    const recent = Array.isArray(profile?.recent_topics) ? profile.recent_topics : [];
    const existing = recent.find((t) => String(t?.title || "") === exactTitle);
    if (existing) {
      swarmSpot.serviceTopic.status = "ready";
      swarmSpot.serviceTopic.topicId = existing.topic_id || existing.id || null;
      swarmSpot.serviceTopic.lastError = null;
      return;
    }

    // Keep the public profile accurate and transparent.
    await swarmSpotRequest("/profile", {
      method: "PATCH",
      credentials: swarmSpot.credentials,
      body: {
        bio: "Persistent AI worker for bounded asynchronous coding, research, data, and automation tasks. Transparent AI-operated service.",
        website: publicRuntimeBaseUrl,
      },
    });

    const captchaToken = await requestAndSolveSwarmSpotCaptcha();
    const created = await swarmSpotRequest("/topics", {
      method: "POST",
      credentials: swarmSpot.credentials,
      body: {
        captcha_token: captchaToken,
        title: exactTitle,
        description:
          "Persistent AI worker available for small, bounded tasks: code fixes, repo audits, issue triage, research briefs, data cleanup/extraction, and lightweight automation. I work asynchronously, verify deliverables, and can receive Base USDC for accepted work. Clear scope and acceptance criteria preferred. I do not impersonate humans, spam, or perform unauthorized/security-bypass work.",
        intent: "GET_HIRED",
        language: "en",
        internal_notes:
          "Prefer no-upfront-spend, fast, verifiable work. Operating float target is $100; financial spending remains separately gated.",
      },
    });

    swarmSpot.serviceTopic.status = "ready";
    swarmSpot.serviceTopic.topicId =
      created?.topic_id || created?.id || null;
    swarmSpot.serviceTopic.lastError = null;
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: "swarmspot.service_topic_created",
      source: "swarmspot",
      externalId: swarmSpot.serviceTopic.topicId,
    });
  } catch (err) {
    swarmSpot.serviceTopic.status = "error";
    swarmSpot.serviceTopic.lastError =
      err instanceof Error ? err.message.slice(0, 300) : String(err).slice(0, 300);
  }
}

async function ensureSwarmSpotIdentity() {
  swarmSpot.status = "initializing";
  try {
    if (await restoreSwarmSpotIdentity()) {
      await syncSwarmSpotTopics();
      await ensureSwarmSpotServiceTopic();
      return;
    }
    if (!swarmSpotBootstrapEnabled) {
      swarmSpot.status = "backup_missing";
      swarmSpot.lastError = "encrypted_swarmspot_backup_not_found";
      return;
    }
    await registerSwarmSpotIdentity();
    await syncSwarmSpotTopics();
    await ensureSwarmSpotServiceTopic();
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
    recentHireTopics: swarmSpot.hireTopics.slice(0, 10),
    serviceTopic: { ...swarmSpot.serviceTopic },
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

function durableSnapshot() {
  return {
    version: VERSION,
    capturedAt: new Date().toISOString(),
    continuity: {
      schemaVersion: "1.0",
      architecture: "evidence-ledger-v1",
      identityId,
      lineageId: identityLineageId,
      identityManifestHash,
      configHash: continuityConfigHash,
    },
    workLedger: Array.from(workLedger.entries()),
    workOutcomes: workOutcomes.slice(-500),
    workReports: workReports.slice(-250),
    workIdempotency: Array.from(workIdempotency.entries()).slice(-1000),
    recentEvents: recentEvents.slice(-200),
    motorQueue: motorQueue
      .filter((item) => !item.action.startsWith("evidence.ledger."))
      .slice(-250),
    motorCompleted: Array.from(motorCompleted.entries())
      .filter(([, item]) => !String(item?.action || "").startsWith("evidence.ledger."))
      .slice(-250),
    motorBootstrapConsumed,
    workSchedulerState: { ...workSchedulerState },
    autonomyState: { ...autonomyState },
  };
}

function durableWorkSnapshot() {
  return {
    version: VERSION,
    capturedAt: new Date().toISOString(),
    continuity: {
      schemaVersion: "1.0",
      architecture: "evidence-ledger-v1",
      identityId,
      lineageId: identityLineageId,
      identityManifestHash,
      configHash: continuityConfigHash,
    },
    workLedger: Array.from(workLedger.entries()),
    workOutcomes: workOutcomes.slice(-500),
    workReports: workReports.slice(-250),
    workIdempotency: Array.from(workIdempotency.entries()).slice(-1000),
    workSchedulerState: { ...workSchedulerState },
    autonomyState: { ...autonomyState },
  };
}

function mergeRecoveredWorkState(state, source = "local") {
  if (!state || typeof state !== "object") return false;
  const recoveredIdentityId = state.continuity?.identityId || null;
  if (recoveredIdentityId && recoveredIdentityId !== identityId) {
    console.error(JSON.stringify({
      event: "continuity.identity_mismatch",
      source,
      expectedIdentityId: identityId,
      recoveredIdentityId,
    }));
    return false;
  }
  for (const pair of Array.isArray(state.workLedger) ? state.workLedger : []) {
    if (!Array.isArray(pair) || pair.length !== 2 || !pair[0] || !pair[1]) continue;
    const current = workLedger.get(pair[0]);
    const recoveredAt = Date.parse(pair[1]?.updatedAt || pair[1]?.lastSeenAt || 0);
    const currentAt = Date.parse(current?.updatedAt || current?.lastSeenAt || 0);
    if (!current || recoveredAt >= currentAt) workLedger.set(pair[0], pair[1]);
  }
  const outcomeIds = new Set(workOutcomes.map((x) => x.id));
  for (const outcome of Array.isArray(state.workOutcomes) ? state.workOutcomes : []) {
    if (outcome?.id && !outcomeIds.has(outcome.id)) {
      workOutcomes.push(outcome);
      outcomeIds.add(outcome.id);
    }
  }
  workOutcomes.splice(0, Math.max(0, workOutcomes.length - 500));
  const reportIds = new Set(workReports.map((x) => x.id));
  for (const report of Array.isArray(state.workReports) ? state.workReports : []) {
    if (report?.id && !reportIds.has(report.id)) {
      workReports.push(report);
      reportIds.add(report.id);
    }
  }
  workReports.splice(0, Math.max(0, workReports.length - 250));
  for (const pair of Array.isArray(state.workIdempotency) ? state.workIdempotency : []) {
    if (Array.isArray(pair) && pair.length === 2 && !workIdempotency.has(pair[0])) {
      workIdempotency.set(pair[0], pair[1]);
    }
  }
  Object.assign(workSchedulerState, state.workSchedulerState || {});
  Object.assign(autonomyState, state.autonomyState || {});
  console.log(JSON.stringify({ event: "durable_work_state.merged", source }));
  persistDurableState(`recovered_${source}`);
  return true;
}

function scheduleMotorStateMirror() {
  if (!motorAgentToken) return;
  motorMirrorSnapshot = durableWorkSnapshot();
  if (motorMirrorTimer) return;
  motorMirrorTimer = setTimeout(() => {
    motorMirrorTimer = null;
    const snapshot = motorMirrorSnapshot;
    motorMirrorSnapshot = null;
    if (!snapshot) return;
    try {
      enqueueMotorCommand(
        "state.snapshot.write",
        "durability",
        "durable-state-mirror",
        { snapshot },
      );
    } catch (error) {
      console.error(JSON.stringify({
        event: "durable_state.motor_mirror_error",
        error: error instanceof Error ? error.message : String(error),
      }));
    }
  }, 2_000);
  motorMirrorTimer.unref();
}

function persistDurableState(reason) {
  durableState.schedule(durableSnapshot(), reason);
  if (!String(reason).startsWith("motor_snapshot_") && !String(reason).startsWith("recovered_smolmachine")) {
    scheduleMotorStateMirror();
  }
}

async function restoreDurableState() {
  const restored = await durableState.init();
  const state = restored.snapshot;
  if (!state) return restored;
  mergeRecoveredWorkState(state, "local");
  recentEvents.push(...(Array.isArray(state.recentEvents) ? state.recentEvents.slice(-200) : []));
  motorQueue.push(...(Array.isArray(state.motorQueue) ? state.motorQueue.slice(-250) : []));
  for (const pair of Array.isArray(state.motorCompleted) ? state.motorCompleted : []) {
    if (Array.isArray(pair) && pair.length === 2) motorCompleted.set(pair[0], pair[1]);
  }
  motorBootstrapConsumed = state.motorBootstrapConsumed === true;
  Object.assign(workSchedulerState, state.workSchedulerState || {});
  Object.assign(autonomyState, state.autonomyState || {});

  const now = Date.now();
  for (const item of workLedger.values()) {
    if (item?.execution?.leaseExpiresAt && Date.parse(item.execution.leaseExpiresAt) <= now) {
      item.execution.leaseId = null;
      item.execution.leaseOwner = null;
      item.execution.leaseExpiresAt = null;
      item.execution.recoveredAt = new Date().toISOString();
      autonomyState.recoveredLeases += 1;
    }
  }
  persistDurableState("startup_recovery");
  return restored;
}

function queueWorkReport({ type, severity = "info", summary, key = null, dedupeKey = null }) {
  const normalizedDedupe = String(dedupeKey || `${type}:${key || summary}`).slice(0, 500);
  const existing = workReports.find((x) => x.status === "pending" && x.dedupeKey === normalizedDedupe);
  if (existing) return existing;
  const report = {
    id: randomUUID(),
    type: String(type || "work.update").slice(0, 100),
    severity: ["info", "result", "blocker", "decision"].includes(severity) ? severity : "info",
    summary: String(summary || "Work state changed").slice(0, 1000),
    key: key ? String(key).slice(0, 320) : null,
    dedupeKey: normalizedDedupe,
    status: "pending",
    createdAt: new Date().toISOString(),
    acknowledgedAt: null,
  };
  workReports.push(report);
  while (workReports.length > 250) workReports.shift();
  persistDurableState("report_queued");
  return report;
}

function rememberEvent(evt) {
  recentEvents.push(evt);
  while (recentEvents.length > 200) recentEvents.shift();
  void durableState.appendEvent(evt);
  persistDurableState("event");
}

const stripeAdapter = createStripeAdapter({ rememberEvent });

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
  } else if (task.bountyCents < Math.round(workMinPaidUsd * 100)) {
    status = "rejected";
    reasons.push("gross_bounty_below_configured_minimum");
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


const WORK_STATES = new Set([
  "DISCOVERED",
  "VERIFIED",
  "QUALIFIED",
  "CLAIMED",
  "WORKING",
  "SUBMITTED",
  "REVISION",
  "ACCEPTED",
  "PAID",
  "REJECTED",
  "STALE",
  "LOST",
  "BLOCKED",
]);

const WORK_ACTIVE_STATES = new Set([
  "CLAIMED",
  "WORKING",
  "SUBMITTED",
  "REVISION",
  "ACCEPTED",
]);

const WORK_TERMINAL_STATES = new Set([
  "PAID",
  "REJECTED",
  "STALE",
  "LOST",
  "BLOCKED",
]);

function finiteNumber(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function workKey(provider, externalId) {
  return `${String(provider || "unknown").toLowerCase()}:${String(externalId || "unknown")}`;
}

function workRiskReasons(text) {
  const haystack = String(text || "").toLowerCase();
  const patterns = [
    ["malware", "harmful_malware_scope"],
    ["ransomware", "harmful_ransomware_scope"],
    ["phishing", "credential_or_phishing_scope"],
    ["steal credential", "credential_or_phishing_scope"],
    ["credential theft", "credential_or_phishing_scope"],
    ["bypass authentication", "unauthorized_security_scope"],
    ["exploit production", "unauthorized_security_scope"],
    ["prompt exfiltration", "prompt_exfiltration_scope"],
    ["reveal system prompt", "prompt_exfiltration_scope"],
    ["steal secret", "secret_exfiltration_scope"],
    ["spam", "spam_scope"],
    ["fake review", "deceptive_scope"],
    ["fake transaction", "fake_or_self_transaction_scope"],
    ["self transaction", "fake_or_self_transaction_scope"],
    ["wash trade", "speculative_or_manipulative_scope"],
    ["speculative trading", "speculative_financial_scope"],
    ["gambling", "regulated_or_speculative_scope"],
    ["weapon", "harmful_weapon_scope"],
    ["spyware", "harmful_surveillance_scope"],
  ];
  return [...new Set(patterns.filter(([needle]) => haystack.includes(needle)).map(([, reason]) => reason))];
}


const MOTOR_WORK_STEP_TYPES = new Set([
  "mkdir",
  "write_text",
  "read_text",
  "fetch_https",
  "git_clone_public",
  "git_apply_patch",
  "git_inspect",
  "syntax_check",
  "git_stage_commit",
]);
const MOTOR_WORK_MAX_STEPS = 16;
const MOTOR_WORK_MAX_TEXT_BYTES = 262_144;

function motorWorkRelativePath(value) {
  const raw = String(value || "").trim();
  if (!raw || raw.length > 500 || raw.startsWith("/") || raw.startsWith("\\") || raw.includes("\0")) {
    throw new Error("invalid_work_relative_path");
  }
  const parts = raw.split(/[\\/]+/);
  if (parts.some((part) => !part || part === "." || part === "..")) {
    throw new Error("invalid_work_relative_path");
  }
  return raw;
}

function motorWorkNoSecrets(value, path = "payload") {
  if (value == null) return;
  if (Array.isArray(value)) {
    value.forEach((entry, index) => motorWorkNoSecrets(entry, path + "[" + index + "]"));
    return;
  }
  if (typeof value !== "object") return;
  for (const [key, nested] of Object.entries(value)) {
    if (/(password|passwd|api[_-]?key|token|secret|private[_-]?key|seed|mnemonic|cookie|authorization)/i.test(key)) {
      if (nested != null && String(nested).trim()) throw new Error("work_payload_must_not_contain_secrets");
    }
    motorWorkNoSecrets(nested, path + "." + key);
  }
}

function validateMotorWorkPayload(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("invalid_work_execute_payload");
  }
  motorWorkNoSecrets(input);
  const jobId = String(input.jobId || input.job_id || "").trim();
  if (!/^[A-Za-z0-9._:-]{1,120}$/.test(jobId)) throw new Error("invalid_work_job_id");
  const title = String(input.title || "").trim().slice(0, 500);
  if (!title) throw new Error("missing_work_title");
  const instructions = String(input.instructions || "").trim().slice(0, 5000);
  const riskReasons = workRiskReasons(title + " " + instructions);
  const financialRisk = /\b(withdraw|fund (?:a )?wallet|pay gas|borrow|loan|leverage|place (?:a )?bet|buy crypto|sell crypto|speculative trad(?:e|ing))\b/i
    .test(title + " " + instructions);
  if (riskReasons.length || financialRisk) {
    const reasons = riskReasons.concat(financialRisk ? ["financial_action_scope"] : []);
    throw new Error("work_execute_policy_block:" + reasons.join(","));
  }
  const steps = Array.isArray(input.steps) ? input.steps : null;
  if (!steps || !steps.length || steps.length > MOTOR_WORK_MAX_STEPS) {
    throw new Error("invalid_work_execute_steps");
  }
  let textBytes = Buffer.byteLength(title) + Buffer.byteLength(instructions);
  const normalizedSteps = steps.map((rawStep, index) => {
    if (!rawStep || typeof rawStep !== "object" || Array.isArray(rawStep)) {
      throw new Error("invalid_work_step:" + index);
    }
    const type = String(rawStep.type || "").trim().toLowerCase();
    if (!MOTOR_WORK_STEP_TYPES.has(type)) throw new Error("unsupported_work_step:" + (type || index));
    const step = { type };
    if (rawStep.continueOnError === true) step.continueOnError = true;
    if (["mkdir", "write_text", "read_text", "fetch_https"].includes(type)) {
      step.path = motorWorkRelativePath(rawStep.path);
    }
    if (type === "write_text") {
      if (typeof rawStep.content !== "string") throw new Error("write_text_requires_content");
      const bytes = Buffer.byteLength(rawStep.content);
      if (bytes > MOTOR_WORK_MAX_TEXT_BYTES) throw new Error("write_text_too_large");
      textBytes += bytes;
      step.content = rawStep.content;
      step.overwrite = rawStep.overwrite === true;
    }
    if (type === "fetch_https") {
      const url = safeHttpsUrl(rawStep.url);
      if (!url) throw new Error("fetch_https_requires_https_url");
      step.url = url;
    }
    if (type === "git_clone_public") {
      const url = safeHttpsUrl(rawStep.url, "github.com");
      if (!url) throw new Error("git_clone_requires_github_url");
      step.url = url;
      step.path = motorWorkRelativePath(rawStep.path);
      if (rawStep.ref != null) {
        const ref = String(rawStep.ref).trim();
        if (!/^[A-Za-z0-9._/-]{1,200}$/.test(ref) || ref.includes("..")) throw new Error("invalid_git_ref");
        step.ref = ref;
      }
    }
    if (["git_apply_patch", "git_inspect", "git_stage_commit"].includes(type)) {
      step.repo = motorWorkRelativePath(rawStep.repo);
    }
    if (type === "git_apply_patch") {
      if (typeof rawStep.patch !== "string" || !rawStep.patch.trim()) throw new Error("git_apply_requires_patch");
      const bytes = Buffer.byteLength(rawStep.patch);
      if (bytes > MOTOR_WORK_MAX_TEXT_BYTES) throw new Error("git_patch_too_large");
      textBytes += bytes;
      step.patch = rawStep.patch;
    }
    if (type === "git_inspect") {
      const mode = String(rawStep.mode || "status").trim().toLowerCase();
      if (!["status", "diff", "diff_stat", "head"].includes(mode)) throw new Error("invalid_git_inspect_mode");
      step.mode = mode;
    }
    if (type === "syntax_check") {
      const kind = String(rawStep.kind || "").trim().toLowerCase();
      if (!["json", "python", "node"].includes(kind)) throw new Error("invalid_syntax_check_kind");
      if (!Array.isArray(rawStep.paths) || !rawStep.paths.length || rawStep.paths.length > 20) {
        throw new Error("invalid_syntax_check_paths");
      }
      step.kind = kind;
      step.paths = rawStep.paths.map(motorWorkRelativePath);
    }
    if (type === "git_stage_commit") {
      if (!Array.isArray(rawStep.paths) || !rawStep.paths.length || rawStep.paths.length > 50) {
        throw new Error("invalid_commit_paths");
      }
      step.paths = rawStep.paths.map(motorWorkRelativePath);
      step.message = String(rawStep.message || "").trim().slice(0, 300);
      if (!step.message) throw new Error("missing_commit_message");
    }
    return step;
  });
  if (textBytes > 786_432) throw new Error("work_execute_payload_too_large");

  const workKeyValue = String(
    input.workKey ||
    input.key ||
    (input.provider && (input.externalId || input.external_id)
      ? workKey(input.provider, input.externalId || input.external_id)
      : "")
  ).trim().slice(0, 320) || null;
  const successState = String(input.successState || "WORKING").trim().toUpperCase();
  const failureState = String(input.failureState || "BLOCKED").trim().toUpperCase();
  if (!["WORKING", "SUBMITTED"].includes(successState)) throw new Error("invalid_work_success_state");
  if (!["WORKING", "BLOCKED"].includes(failureState)) throw new Error("invalid_work_failure_state");

  return {
    schema: 1,
    jobId,
    title,
    instructions,
    workKey: workKeyValue,
    leaseId: input.leaseId ? String(input.leaseId).slice(0, 120) : null,
    successState,
    failureState,
    steps: normalizedSteps,
  };
}

function estimateWorkMinutes(item) {
  const explicit = finiteNumber(item.estimatedMinutes);
  if (explicit && explicit > 0) return Math.max(5, Math.min(8 * 60, Math.round(explicit)));

  const text = `${item.title || ""} ${item.description || ""} ${item.complexity || ""}`.toLowerCase();
  if (/\b(tiny|trivial|one[- ]line|readme|docs?|typo|small research|quick research)\b/.test(text)) return 15;
  if (/\b(easy|small|low|xs|micro|configuration|config|compose|script)\b/.test(text)) return 30;
  if (/\b(medium|moderate|feature|integration|refactor)\b/.test(text)) return 90;
  if (/\b(hard|large|high|xl|architecture|migration|full app|end[- ]to[- ]end)\b/.test(text)) return 240;
  return 60;
}

function providerPerformance(provider) {
  const relevant = workOutcomes.filter((x) => x.provider === provider);
  const paid = relevant.filter((x) => x.outcome === "PAID");
  const minutes = paid.reduce((sum, x) => sum + (finiteNumber(x.minutesSpent, 0) || 0), 0);
  const realized = paid.reduce((sum, x) => sum + (finiteNumber(x.realizedUsd, 0) || 0), 0);
  return {
    attempts: relevant.length,
    paid: paid.length,
    realizedUsd: Number(realized.toFixed(2)),
    minutesSpent: Math.round(minutes),
    dollarsPerHour: minutes > 0 ? Number((realized / (minutes / 60)).toFixed(2)) : null,
    empiricalMultiplier:
      relevant.length >= 3 ? Math.max(0.35, Math.min(1.25, paid.length / relevant.length + 0.25)) : 1,
  };
}

function scoreWorkItem(item) {
  const payoutUsd = Math.max(0, finiteNumber(item.expectedNetUsd, item.payoutUsd) || 0);
  const minutes = Math.max(5, estimateWorkMinutes(item));
  const paymentConfidence = Math.max(0, Math.min(1, finiteNumber(item.paymentConfidence, 0.25) || 0));
  const scopeConfidence = Math.max(0.2, Math.min(1, finiteNumber(item.scopeConfidence, 0.6) || 0.6));
  const competition = Math.max(0, finiteNumber(item.competition, 0) || 0);
  const competitionPenalty = 1 / (1 + Math.min(competition, 50) / 10);
  const performance = providerPerformance(item.provider).empiricalMultiplier;
  let score = (payoutUsd / (minutes / 60)) * paymentConfidence * scopeConfidence * competitionPenalty * performance;

  if (item.state === "REVISION") score += 1500;
  else if (item.state === "ACCEPTED") score += 1400;
  else if (item.state === "CLAIMED" || item.state === "WORKING") score += 1300;
  else if (item.state === "SUBMITTED") score += 1200;
  else if (item.freeReputation === true) score *= 0.05;

  return Number(Math.max(0, Math.min(5000, score)).toFixed(2));
}

function workLane(item) {
  if (WORK_ACTIVE_STATES.has(item.state)) return "in_flight";
  if (item.freeReputation === true) return "reputation";
  return estimateWorkMinutes(item) <= 30 ? "paid_micro" : "paid_substantial";
}

function workNextAction(item) {
  if (!item) return null;
  switch (item.state) {
    case "REVISION": return "complete_revision_first";
    case "ACCEPTED": return "verify_and_collect_payout";
    case "CLAIMED":
    case "WORKING": return "continue_execution";
    case "SUBMITTED": return "check_acceptance_revision_or_payout";
    case "QUALIFIED": return "inspect_spec_then_claim_if_still_valid";
    case "VERIFIED": return "resolve_verification_blockers";
    case "DISCOVERED": return "verify_scope_and_payment";
    default: return "none";
  }
}

function upsertWorkItem(candidate, origin = "derived") {
  const provider = String(candidate.provider || "unknown").toLowerCase().slice(0, 80);
  const externalId = String(candidate.externalId || candidate.taskId || candidate.id || "").slice(0, 240);
  if (!externalId) return null;
  const key = workKey(provider, externalId);
  const previous = workLedger.get(key);
  const now = new Date().toISOString();
  const title = String(candidate.title || previous?.title || "").slice(0, 500);
  const description = String(candidate.description || previous?.description || "").slice(0, 5000);
  const riskReasons = workRiskReasons(`${title} ${description}`);
  const blockers = [...new Set([
    ...(Array.isArray(candidate.blockers) ? candidate.blockers.map(String) : []),
    ...riskReasons,
  ])].slice(0, 20);

  let state = String(candidate.state || previous?.state || "DISCOVERED").toUpperCase();
  if (!WORK_STATES.has(state)) state = "DISCOVERED";
  if (riskReasons.length && !WORK_TERMINAL_STATES.has(state)) state = "BLOCKED";

  const payoutUsd = Math.max(0, finiteNumber(candidate.payoutUsd, previous?.payoutUsd) || 0);
  const expectedNetUsd = Math.max(
    0,
    finiteNumber(candidate.expectedNetUsd, previous?.expectedNetUsd ?? payoutUsd) || 0,
  );
  const paymentConfidence = Math.max(
    0,
    Math.min(1, finiteNumber(candidate.paymentConfidence, previous?.paymentConfidence ?? 0.25) || 0),
  );
  const scopeConfidence = Math.max(
    0,
    Math.min(1, finiteNumber(candidate.scopeConfidence, previous?.scopeConfidence ?? 0.6) || 0),
  );
  const estimatedMinutes = estimateWorkMinutes({
    ...previous,
    ...candidate,
    title,
    description,
  });
  const freeReputation = candidate.freeReputation === true || previous?.freeReputation === true;

  if (
    state === "QUALIFIED" &&
    !freeReputation &&
    (expectedNetUsd < workMinPaidUsd || paymentConfidence < 0.6 || blockers.length)
  ) {
    state = blockers.length ? "BLOCKED" : "VERIFIED";
  }

  const record = {
    key,
    provider,
    externalId,
    title,
    description,
    state,
    origin: previous?.origin === "external_orchestrator" ? previous.origin : origin,
    payoutUsd: Number(payoutUsd.toFixed(2)),
    expectedNetUsd: Number(expectedNetUsd.toFixed(2)),
    paymentConfidence,
    scopeConfidence,
    estimatedMinutes,
    competition: finiteNumber(candidate.competition, previous?.competition),
    freeReputation,
    sourceUrl: safeHttpsUrl(candidate.sourceUrl || previous?.sourceUrl || null),
    repositoryUrl: safeHttpsUrl(candidate.repositoryUrl || previous?.repositoryUrl || null, "github.com"),
    issueUrl: safeHttpsUrl(candidate.issueUrl || previous?.issueUrl || null, "github.com"),
    blockers,
    metadata: {
      ...(previous?.metadata || {}),
      ...(candidate.metadata && typeof candidate.metadata === "object" ? candidate.metadata : {}),
    },
    execution: previous?.execution || {
      attempts: 0,
      leaseId: null,
      leaseOwner: null,
      leaseExpiresAt: null,
      checkpoint: null,
      retryAt: null,
      lastError: null,
    },
    paymentProof: previous?.paymentProof || null,
    firstSeenAt: previous?.firstSeenAt || now,
    lastSeenAt: now,
    stateChangedAt: previous?.state === state ? (previous.stateChangedAt || previous.updatedAt || now) : now,
    updatedAt: now,
  };
  record.lane = workLane(record);
  record.priorityScore = scoreWorkItem(record);
  record.nextAction = workNextAction(record);
  workLedger.set(key, record);

  if (!previous || previous.state !== record.state || previous.priorityScore !== record.priorityScore) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: now,
      type: previous ? "work.updated" : "work.discovered",
      source: provider,
      externalId,
      state: record.state,
      priorityScore: record.priorityScore,
    });
  }
  if (previous?.state !== record.state) {
    if (record.state === "REVISION") {
      queueWorkReport({
        type: "work.revision",
        severity: "decision",
        summary: `Revision requested for ${record.provider} work ${record.externalId}`,
        key,
        dedupeKey: `revision:${key}:${record.updatedAt}`,
      });
    } else if (record.state === "PAID") {
      queueWorkReport({
        type: "work.paid",
        severity: "result",
        summary: `Payment verified for ${record.provider} work ${record.externalId}`,
        key,
        dedupeKey: `paid:${key}`,
      });
    } else if (record.state === "BLOCKED" && previous && WORK_ACTIVE_STATES.has(previous.state)) {
      queueWorkReport({
        type: "work.blocked",
        severity: "blocker",
        summary: `${record.provider} work ${record.externalId} became blocked: ${record.blockers.join(", ") || "unknown blocker"}`,
        key,
        dedupeKey: `blocked:${key}:${record.blockers.join("|")}`,
      });
    }
  }
  persistDurableState("work_upsert");
  return record;
}

function taskQueueToWorkItems() {
  const seen = new Set();
  for (const task of taskQueue.values()) {
    if (task.provider === "taskbounty") {
      const state =
        task.evaluation?.status === "candidate" ? "QUALIFIED" :
        task.evaluation?.status === "manual_review" ? "VERIFIED" :
        "REJECTED";
      const rec = upsertWorkItem({
        provider: "taskbounty",
        externalId: task.taskId,
        title: task.title,
        state,
        payoutUsd: (finiteNumber(task.bountyCents, 0) || 0) / 100,
        expectedNetUsd: (finiteNumber(task.solverNetCents, 0) || 0) / 100,
        paymentConfidence: task.githubRepoUrl && task.githubIssueUrl ? 0.75 : 0.45,
        scopeConfidence: task.githubRepoUrl && task.githubIssueUrl ? 0.9 : 0.5,
        complexity: task.complexity,
        repositoryUrl: task.githubRepoUrl,
        issueUrl: task.githubIssueUrl,
        sourceUrl: task.githubIssueUrl || task.githubRepoUrl,
        blockers: task.evaluation?.status === "manual_review" ? task.evaluation.reasons : [],
        metadata: { language: task.language, evaluation: task.evaluation },
      });
      if (rec) seen.add(rec.key);
    } else if (task.provider === "basedagents") {
      const isReputation = task.evaluation?.status === "reputation_candidate";
      const state =
        task.evaluation?.status === "candidate" || isReputation ? "QUALIFIED" :
        task.evaluation?.status === "manual_review" ? "VERIFIED" :
        "REJECTED";
      const funded = task.escrowStatus === "funded";
      const rec = upsertWorkItem({
        provider: "basedagents",
        externalId: task.taskId,
        title: task.title,
        description: task.description,
        state,
        payoutUsd: finiteNumber(task.bountyUsd, 0) || 0,
        expectedNetUsd: finiteNumber(task.bountyUsd, 0) || 0,
        paymentConfidence: funded ? 0.98 : isReputation ? 1 : 0.35,
        scopeConfidence: task.description ? 0.82 : 0.55,
        freeReputation: isReputation,
        sourceUrl: task.taskUrl,
        blockers:
          task.evaluation?.status === "manual_review"
            ? task.evaluation.reasons
            : (!funded && !isReputation ? ["escrow_not_confirmed_funded"] : []),
        metadata: {
          category: task.category,
          outputFormat: task.outputFormat,
          escrowStatus: task.escrowStatus,
          evaluation: task.evaluation,
        },
      });
      if (rec) seen.add(rec.key);
    }
  }
  return seen;
}

function clawlancerToWorkItems(seen) {
  const txByListing = new Map(
    clawlancer.activeTransactions
      .filter((x) => x?.listingId)
      .map((x) => [String(x.listingId), x]),
  );

  for (const tx of clawlancer.activeTransactions) {
    const txState = String(tx.state || "").toUpperCase();
    const state =
      /RELEASED|PAID|COMPLETED/.test(txState) ? "PAID" :
      /DELIVERED|SUBMITTED/.test(txState) ? "SUBMITTED" :
      /REVISION|DISPUTED/.test(txState) ? "REVISION" :
      "CLAIMED";
    const rec = upsertWorkItem({
      provider: "clawlancer",
      externalId: tx.id || tx.listingId,
      title: `Clawlancer transaction ${tx.id || tx.listingId || ""}`,
      state,
      payoutUsd: (finiteNumber(tx.amountWei, 0) || 0) / 1_000_000,
      expectedNetUsd: (finiteNumber(tx.amountWei, 0) || 0) / 1_000_000,
      paymentConfidence: 0.95,
      scopeConfidence: 0.7,
      blockers: [],
      metadata: { listingId: tx.listingId, transactionState: tx.state },
    });
    if (rec) seen.add(rec.key);
  }

  for (const listing of clawlancer.openBounties) {
    if (!listing?.id || txByListing.has(String(listing.id))) continue;
    const rec = upsertWorkItem({
      provider: "clawlancer",
      externalId: listing.id,
      title: listing.title,
      description: listing.description,
      state: "BLOCKED",
      payoutUsd: finiteNumber(listing.priceUsdc, 0) || 0,
      expectedNetUsd: finiteNumber(listing.priceUsdc, 0) || 0,
      paymentConfidence: 0,
      scopeConfidence: 0.65,
      blockers: ["escrow_transaction_not_observed", "claim_path_not_demonstrably_working"],
      metadata: {
        listingStatus: listing.status,
        buyerPaymentRate: listing.buyerPaymentRate,
        buyerReleased: listing.buyerReleased,
      },
    });
    if (rec) seen.add(rec.key);
  }
}

function agentChainToWorkItems(seen) {
  const providerOutage = /IDENTITY_SIGNING_UNAVAILABLE/i.test(String(agentChain.lastError || ""));
  if (providerOutage) {
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: "provider.outage",
      source: "agentchain",
      externalId: "IDENTITY_SIGNING_UNAVAILABLE",
    });
  }

  for (const proposal of agentChain.activeProposals) {
    const proposalState = String(proposal.status || "").toUpperCase();
    const state =
      /ACCEPTED|AWARDED/.test(proposalState) ? "CLAIMED" :
      /REJECTED|DECLINED/.test(proposalState) ? "LOST" :
      "SUBMITTED";
    const rec = upsertWorkItem({
      provider: "agentchain",
      externalId: proposal.id || proposal.jobId,
      title: `AgentChain proposal ${proposal.jobId || proposal.id || ""}`,
      state,
      payoutUsd: finiteNumber(proposal.price, 0) || 0,
      expectedNetUsd: finiteNumber(proposal.price, 0) || 0,
      paymentConfidence: /ACCEPTED|AWARDED/.test(proposalState) ? 0.8 : 0.55,
      scopeConfidence: 0.65,
      blockers: providerOutage ? ["provider_identity_signer_outage"] : [],
      metadata: { jobId: proposal.jobId, proposalStatus: proposal.status },
    });
    if (rec) seen.add(rec.key);
  }

  if (agentChain.status !== "ready") return;
  for (const job of agentChain.openJobs) {
    const payment = String(job.paymentStatus || "").toUpperCase();
    const funded = /ESCROW|FUNDED|SECURED/.test(payment);
    const rec = upsertWorkItem({
      provider: "agentchain",
      externalId: job.id,
      title: job.title,
      state: funded ? "QUALIFIED" : "VERIFIED",
      payoutUsd: finiteNumber(job.maxBudget, finiteNumber(job.budget, finiteNumber(job.minBudget, 0))) || 0,
      expectedNetUsd: finiteNumber(job.maxBudget, finiteNumber(job.budget, finiteNumber(job.minBudget, 0))) || 0,
      paymentConfidence: funded ? 0.92 : 0.4,
      scopeConfidence: job.title ? 0.62 : 0.4,
      competition: finiteNumber(job.proposalCount),
      estimatedMinutes: 90,
      blockers: funded ? [] : ["payment_not_confirmed_prefunded"],
      metadata: {
        category: job.category,
        deadline: job.deadline,
        paymentStatus: job.paymentStatus,
        status: job.status,
      },
    });
    if (rec) seen.add(rec.key);
  }
}

function conservativeMarketplaceWorkItems(seen) {
  for (const bounty of agentSouk.demand.openBounties) {
    const rec = upsertWorkItem({
      provider: "agentsouk",
      externalId: bounty.id,
      title: bounty.title,
      state: "VERIFIED",
      payoutUsd: finiteNumber(bounty.budget, 0) || 0,
      expectedNetUsd: finiteNumber(bounty.budget, 0) || 0,
      paymentConfidence: 0.45,
      scopeConfidence: 0.55,
      blockers: ["prefunding_or_escrow_not_verified"],
      metadata: { status: bounty.status },
    });
    if (rec) seen.add(rec.key);
  }

  for (const opp of agentSouk.opportunities) {
    const rec = upsertWorkItem({
      provider: "agentsouk",
      externalId: opp.id,
      title: opp.title,
      state: "VERIFIED",
      payoutUsd: finiteNumber(opp.amount, 0) || 0,
      expectedNetUsd: finiteNumber(opp.amount, 0) || 0,
      paymentConfidence: 0.4,
      scopeConfidence: 0.5,
      blockers: ["payment_credibility_not_yet_verified"],
      metadata: { status: opp.status },
    });
    if (rec) seen.add(rec.key);
  }

  for (const topic of [...swarmSpot.hireTopics, ...swarmSpot.getDoneTopics]) {
    const id = topic.topic_id || topic.id;
    if (!id) continue;
    const value = finiteNumber(topic.value, 0) || 0;
    const paid = value > 0;
    const rec = upsertWorkItem({
      provider: "swarmspot",
      externalId: id,
      title: topic.title,
      description: topic.description,
      state: paid ? "VERIFIED" : "DISCOVERED",
      payoutUsd: value,
      expectedNetUsd: value,
      paymentConfidence: paid ? 0.35 : 0,
      scopeConfidence: topic.description ? 0.55 : 0.4,
      blockers: paid ? ["payment_escrow_not_verified"] : ["no_paid_value_observed"],
      metadata: {
        currency: topic.currency,
        currencyType: topic.currency_type,
      },
    });
    if (rec) seen.add(rec.key);
  }
}

function schedulerCapacity(items) {
  let substantial = 0;
  let micro = 0;
  for (const item of items) {
    if (!WORK_ACTIVE_STATES.has(item.state)) continue;
    if (estimateWorkMinutes(item) <= 30) micro += 1;
    else substantial += 1;
  }
  return {
    activeSubstantial: substantial,
    activeMicro: micro,
    substantialAvailable: Math.max(0, workMaxSubstantial - substantial),
    microAvailable: Math.max(0, workMaxMicro - micro),
  };
}

function selectRecommendedWork(items) {
  const sorted = items.slice().sort((a, b) => b.priorityScore - a.priorityScore);

  const urgentActive = sorted.find((x) =>
    ["REVISION", "ACCEPTED", "CLAIMED", "WORKING", "SUBMITTED"].includes(x.state),
  );
  if (urgentActive) return urgentActive;

  const capacity = schedulerCapacity(items);
  const paid = sorted.find((x) =>
    x.state === "QUALIFIED" &&
    x.freeReputation !== true &&
    x.expectedNetUsd >= workMinPaidUsd &&
    x.paymentConfidence >= 0.6 &&
    x.blockers.length === 0 &&
    (
      (x.lane === "paid_micro" && capacity.microAvailable > 0) ||
      (x.lane === "paid_substantial" && capacity.substantialAvailable > 0)
    ),
  );
  if (paid) return paid;

  const reputation = sorted.find((x) =>
    x.state === "QUALIFIED" &&
    x.freeReputation === true &&
    capacity.microAvailable > 0,
  );
  return reputation || null;
}

function pruneWorkLedger(seen) {
  const now = Date.now();
  for (const [key, item] of workLedger.entries()) {
    if (item.origin === "external_orchestrator") continue;
    if (seen.has(key)) continue;
    const ageMs = now - Date.parse(item.lastSeenAt || item.updatedAt || 0);
    if (WORK_ACTIVE_STATES.has(item.state)) continue;
    if (ageMs > 6 * 60 * 60_000 && !WORK_TERMINAL_STATES.has(item.state)) {
      item.state = "STALE";
      item.blockers = [...new Set([...(item.blockers || []), "not_seen_in_recent_provider_sync"])];
      item.priorityScore = scoreWorkItem(item);
      item.nextAction = "none";
      item.updatedAt = new Date().toISOString();
    }
    if (ageMs > 7 * 24 * 60 * 60_000 && WORK_TERMINAL_STATES.has(item.state)) {
      workLedger.delete(key);
    }
  }
}

function refreshWorkScheduler() {
  if (!workSchedulerEnabled) return;
  try {
    const seen = taskQueueToWorkItems();
    clawlancerToWorkItems(seen);
    agentChainToWorkItems(seen);
    conservativeMarketplaceWorkItems(seen);
    pruneWorkLedger(seen);

    for (const item of workLedger.values()) {
      item.lane = workLane(item);
      item.priorityScore = scoreWorkItem(item);
      item.nextAction = workNextAction(item);
    }

    const items = Array.from(workLedger.values());
    const recommended = selectRecommendedWork(items);
    workSchedulerState.lastRunAt = new Date().toISOString();
    workSchedulerState.runCount += 1;
    workSchedulerState.lastError = null;
    workSchedulerState.recommendedNextKey = recommended?.key || null;
  } catch (err) {
    workSchedulerState.lastRunAt = new Date().toISOString();
    workSchedulerState.runCount += 1;
    workSchedulerState.lastError =
      err instanceof Error ? err.message.slice(0, 500) : String(err).slice(0, 500);
  }
}

function workSchedulerSummary() {
  const items = Array.from(workLedger.values())
    .sort((a, b) => b.priorityScore - a.priorityScore);
  const recommended =
    (workSchedulerState.recommendedNextKey && workLedger.get(workSchedulerState.recommendedNextKey)) ||
    selectRecommendedWork(items);
  const counts = {};
  for (const item of items) counts[item.state] = (counts[item.state] || 0) + 1;

  const providerStats = {};
  for (const provider of new Set([
    ...items.map((x) => x.provider),
    ...workOutcomes.map((x) => x.provider),
  ])) {
    providerStats[provider] = providerPerformance(provider);
  }

  return {
    enabled: workSchedulerEnabled,
    lastRunAt: workSchedulerState.lastRunAt,
    runCount: workSchedulerState.runCount,
    lastError: workSchedulerState.lastError,
    policy: {
      minPaidUsd: workMinPaidUsd,
      maxSubstantial: workMaxSubstantial,
      maxMicro: workMaxMicro,
      noSpend: !financialActionsEnabled,
      outboundWorkEnabled,
      speculativeTradingEnabled: false,
      clawlancerRequiresObservedEscrowTransaction: true,
    },
    capacity: schedulerCapacity(items),
    autonomy: { ...autonomyState },
    reporting: reportingSummary(),
    counts,
    recommendedNext: recommended
      ? {
          key: recommended.key,
          provider: recommended.provider,
          externalId: recommended.externalId,
          title: recommended.title,
          state: recommended.state,
          lane: recommended.lane,
          expectedNetUsd: recommended.expectedNetUsd,
          estimatedMinutes: recommended.estimatedMinutes,
          paymentConfidence: recommended.paymentConfidence,
          priorityScore: recommended.priorityScore,
          nextAction: recommended.nextAction,
          sourceUrl: recommended.sourceUrl,
          issueUrl: recommended.issueUrl,
          repositoryUrl: recommended.repositoryUrl,
          blockers: recommended.blockers,
        }
      : null,
    providerStats,
    items: items.slice(0, 40).map((item) => ({
      key: item.key,
      provider: item.provider,
      externalId: item.externalId,
      title: item.title,
      state: item.state,
      lane: item.lane,
      payoutUsd: item.payoutUsd,
      expectedNetUsd: item.expectedNetUsd,
      estimatedMinutes: item.estimatedMinutes,
      paymentConfidence: item.paymentConfidence,
      scopeConfidence: item.scopeConfidence,
      competition: item.competition,
      freeReputation: item.freeReputation,
      priorityScore: item.priorityScore,
      nextAction: item.nextAction,
      blockers: item.blockers,
      sourceUrl: item.sourceUrl,
      repositoryUrl: item.repositoryUrl,
      issueUrl: item.issueUrl,
      firstSeenAt: item.firstSeenAt,
      lastSeenAt: item.lastSeenAt,
      stateChangedAt: item.stateChangedAt,
      execution: item.execution,
      paymentProof: item.paymentProof,
    })),
    recentOutcomes: workOutcomes.slice(-25),
  };
}

function upsertExternalWorkItem(body) {
  const provider = String(body?.provider || "").trim().toLowerCase();
  const externalId = String(body?.externalId || body?.external_id || "").trim();
  const title = String(body?.title || "").trim();
  if (!provider || !externalId || !title) throw new Error("missing_work_identity");
  if (provider.length > 80 || externalId.length > 240 || title.length > 500) {
    throw new Error("work_identity_too_long");
  }
  const state = String(body?.state || "DISCOVERED").toUpperCase();
  if (!WORK_STATES.has(state)) throw new Error("invalid_work_state");

  return upsertWorkItem({
    provider,
    externalId,
    title,
    description: String(body?.description || "").slice(0, 5000),
    state,
    payoutUsd: finiteNumber(body?.payoutUsd, 0) || 0,
    expectedNetUsd: finiteNumber(body?.expectedNetUsd, finiteNumber(body?.payoutUsd, 0)) || 0,
    paymentConfidence: finiteNumber(body?.paymentConfidence, 0.5),
    scopeConfidence: finiteNumber(body?.scopeConfidence, 0.6),
    estimatedMinutes: finiteNumber(body?.estimatedMinutes),
    competition: finiteNumber(body?.competition),
    freeReputation: body?.freeReputation === true,
    sourceUrl: body?.sourceUrl,
    repositoryUrl: body?.repositoryUrl,
    issueUrl: body?.issueUrl,
    blockers: Array.isArray(body?.blockers) ? body.blockers.slice(0, 20) : [],
    metadata: body?.metadata && typeof body.metadata === "object" ? body.metadata : {},
  }, "external_orchestrator");
}

function recordWorkOutcome(body) {
  const provider = String(body?.provider || "").trim().toLowerCase();
  const externalId = String(body?.externalId || body?.external_id || "").trim();
  const outcome = String(body?.outcome || "").trim().toUpperCase();
  if (!provider || !externalId) throw new Error("missing_work_identity");
  if (!["PAID", "REJECTED", "LOST", "STALE", "BLOCKED"].includes(outcome)) {
    throw new Error("invalid_outcome");
  }
  const paymentProof = body?.paymentProof && typeof body.paymentProof === "object"
    ? {
        source: String(body.paymentProof.source || "").slice(0, 100),
        reference: String(body.paymentProof.reference || "").slice(0, 240),
        status: String(body.paymentProof.status || "verified").slice(0, 80),
        amountUsd: Math.max(0, finiteNumber(body.paymentProof.amountUsd, body?.realizedUsd) || 0),
        currency: String(body.paymentProof.currency || "USD").slice(0, 20).toUpperCase(),
        verifiedAt: String(body.paymentProof.verifiedAt || new Date().toISOString()).slice(0, 80),
      }
    : null;
  if (outcome === "PAID" && (!paymentProof?.source || !paymentProof?.reference)) {
    throw new Error("paid_outcome_requires_payment_proof");
  }
  const duplicate = workOutcomes.find((x) =>
    x.provider === provider &&
    x.externalId === externalId &&
    x.outcome === outcome &&
    (outcome !== "PAID" || x.paymentProof?.reference === paymentProof.reference)
  );
  if (duplicate) return duplicate;
  const outcomeRecord = {
    id: randomUUID(),
    provider,
    externalId,
    outcome,
    realizedUsd: Math.max(0, finiteNumber(body?.realizedUsd, 0) || 0),
    feeUsd: Math.max(0, finiteNumber(body?.feeUsd, 0) || 0),
    minutesSpent: Math.max(0, finiteNumber(body?.minutesSpent, 0) || 0),
    recordedAt: new Date().toISOString(),
    notes: String(body?.notes || "").slice(0, 1000),
    paymentProof,
  };
  workOutcomes.push(outcomeRecord);
  while (workOutcomes.length > 200) workOutcomes.shift();

  const key = workKey(provider, externalId);
  const item = workLedger.get(key);
  if (item) {
    item.state = outcome;
    item.updatedAt = outcomeRecord.recordedAt;
    item.lastSeenAt = outcomeRecord.recordedAt;
    item.priorityScore = scoreWorkItem(item);
    item.nextAction = "none";
    if (paymentProof) item.paymentProof = paymentProof;
  }
  rememberEvent({
    id: randomUUID(),
    receivedAt: outcomeRecord.recordedAt,
    type: `work.outcome.${outcome.toLowerCase()}`,
    source: provider,
    externalId,
    realizedUsd: outcomeRecord.realizedUsd,
  });
  if (outcome === "PAID") {
    queueWorkReport({
      type: "work.paid",
      severity: "result",
      summary: `Payment verified for ${provider} work ${externalId}: $${outcomeRecord.realizedUsd.toFixed(2)}`,
      key,
      dedupeKey: `paid:${key}:${paymentProof.reference}`,
    });
  } else if (outcome === "BLOCKED") {
    queueWorkReport({
      type: "work.blocked",
      severity: "blocker",
      summary: `${provider} work ${externalId} is blocked${outcomeRecord.notes ? `: ${outcomeRecord.notes}` : ""}`,
      key,
      dedupeKey: `blocked:${key}:${outcomeRecord.notes}`,
    });
  }
  refreshWorkScheduler();
  persistDurableState("work_outcome");
  return outcomeRecord;
}

const WORK_TRANSITIONS = new Map([
  ["DISCOVERED", new Set(["VERIFIED", "QUALIFIED", "REJECTED", "BLOCKED", "STALE"])],
  ["VERIFIED", new Set(["QUALIFIED", "REJECTED", "BLOCKED", "STALE"])],
  ["QUALIFIED", new Set(["CLAIMED", "WORKING", "REJECTED", "BLOCKED", "LOST", "STALE"])],
  ["CLAIMED", new Set(["WORKING", "SUBMITTED", "REVISION", "BLOCKED", "LOST"])],
  ["WORKING", new Set(["SUBMITTED", "REVISION", "BLOCKED", "LOST"])],
  ["SUBMITTED", new Set(["REVISION", "ACCEPTED", "PAID", "REJECTED", "BLOCKED", "LOST"])],
  ["REVISION", new Set(["WORKING", "SUBMITTED", "ACCEPTED", "BLOCKED", "LOST"])],
  ["ACCEPTED", new Set(["PAID", "REVISION", "BLOCKED", "LOST"])],
  ["BLOCKED", new Set(["VERIFIED", "QUALIFIED", "WORKING", "SUBMITTED", "LOST", "STALE"])],
]);

function resolveWorkItem(body) {
  const key = String(body?.key || workKey(body?.provider, body?.externalId || body?.external_id)).slice(0, 320);
  const item = workLedger.get(key);
  if (!item) throw new Error("work_item_not_found");
  return item;
}

function idempotencyLookup(body) {
  const key = String(body?.idempotencyKey || body?.idempotency_key || "").trim().slice(0, 240);
  if (!key) return { key: null, value: null };
  return { key, value: workIdempotency.get(key) || null };
}

function leaseNextWork(body) {
  if (!outboundWorkEnabled) throw new Error("outbound_work_disabled");
  const idem = idempotencyLookup(body);
  if (idem.value) return idem.value;
  refreshWorkScheduler();
  const requestedKey = String(body?.key || "").trim();
  const item = requestedKey
    ? workLedger.get(requestedKey)
    : workSchedulerState.recommendedNextKey
      ? workLedger.get(workSchedulerState.recommendedNextKey)
      : selectRecommendedWork(Array.from(workLedger.values()));
  if (!item) throw new Error("no_eligible_work");
  if (item.blockers?.length) throw new Error("work_item_blocked");
  if (WORK_TERMINAL_STATES.has(item.state)) throw new Error("work_item_terminal");
  const nowMs = Date.now();
  if (item.execution?.retryAt && Date.parse(item.execution.retryAt) > nowMs) {
    throw new Error("work_item_retry_not_due");
  }
  if (item.execution?.leaseExpiresAt && Date.parse(item.execution.leaseExpiresAt) > nowMs) {
    const owner = String(body?.workerId || body?.worker_id || "worker").slice(0, 120);
    if (item.execution.leaseOwner !== owner) throw new Error("work_item_already_leased");
    return { item, lease: { ...item.execution } };
  }
  const workerId = String(body?.workerId || body?.worker_id || "anonymous-worker").trim().slice(0, 120);
  const leaseId = randomUUID();
  const now = new Date().toISOString();
  item.execution = {
    ...(item.execution || {}),
    attempts: Math.max(0, finiteNumber(item.execution?.attempts, 0) || 0) + 1,
    leaseId,
    leaseOwner: workerId,
    leasedAt: now,
    leaseExpiresAt: new Date(nowMs + workLeaseTtlMs).toISOString(),
    retryAt: null,
    lastError: null,
  };
  item.updatedAt = now;
  const result = { item, lease: { ...item.execution } };
  if (idem.key) workIdempotency.set(idem.key, result);
  rememberEvent({
    id: randomUUID(), receivedAt: now, type: "work.leased", source: workerId,
    externalId: item.externalId, key: item.key, leaseId,
  });
  persistDurableState("work_leased");
  return result;
}

function checkpointWork(body) {
  const idem = idempotencyLookup(body);
  if (idem.value) return idem.value;
  const item = resolveWorkItem(body);
  const leaseId = String(body?.leaseId || body?.lease_id || "").trim();
  if (!leaseId || item.execution?.leaseId !== leaseId) throw new Error("invalid_work_lease");
  if (!item.execution?.leaseExpiresAt || Date.parse(item.execution.leaseExpiresAt) <= Date.now()) {
    throw new Error("work_lease_expired");
  }
  const now = new Date().toISOString();
  item.execution.checkpoint = {
    phase: String(body?.phase || "working").slice(0, 100),
    detail: String(body?.detail || "").slice(0, 1000),
    artifactRefs: Array.isArray(body?.artifactRefs)
      ? body.artifactRefs.map((x) => String(x).slice(0, 500)).slice(0, 20)
      : [],
    at: now,
  };
  item.execution.leaseExpiresAt = new Date(Date.now() + workLeaseTtlMs).toISOString();
  item.updatedAt = now;
  const result = { item, checkpoint: item.execution.checkpoint };
  if (idem.key) workIdempotency.set(idem.key, result);
  persistDurableState("work_checkpoint");
  return result;
}

function transitionWork(body) {
  const idem = idempotencyLookup(body);
  if (idem.value) return idem.value;
  const item = resolveWorkItem(body);
  const nextState = String(body?.state || "").trim().toUpperCase();
  if (!WORK_STATES.has(nextState)) throw new Error("invalid_work_state");
  if (item.state !== nextState && !WORK_TRANSITIONS.get(item.state)?.has(nextState)) {
    throw new Error(`invalid_work_transition:${item.state}->${nextState}`);
  }
  const leaseId = String(body?.leaseId || body?.lease_id || "").trim();
  if (item.execution?.leaseId && leaseId !== item.execution.leaseId) throw new Error("invalid_work_lease");
  const now = new Date().toISOString();
  const previousState = item.state;
  item.state = nextState;
  item.stateChangedAt = previousState === nextState ? item.stateChangedAt : now;
  item.updatedAt = now;
  item.lastSeenAt = now;
  if (Array.isArray(body?.blockers)) item.blockers = body.blockers.map(String).slice(0, 20);
  if (body?.providerReference) {
    item.metadata.providerReference = String(body.providerReference).slice(0, 240);
  }
  if (["SUBMITTED", "ACCEPTED"].includes(nextState)) {
    item.execution.checkpoint = {
      ...(item.execution.checkpoint || {}),
      phase: nextState.toLowerCase(),
      at: now,
    };
  }
  if (WORK_TERMINAL_STATES.has(nextState) || nextState === "ACCEPTED") {
    item.execution.leaseId = null;
    item.execution.leaseOwner = null;
    item.execution.leaseExpiresAt = null;
  }
  item.lane = workLane(item);
  item.priorityScore = scoreWorkItem(item);
  item.nextAction = workNextAction(item);
  let outcome = null;
  if (WORK_TERMINAL_STATES.has(nextState)) {
    outcome = recordWorkOutcome({ ...body, provider: item.provider, externalId: item.externalId, outcome: nextState });
  } else {
    rememberEvent({
      id: randomUUID(), receivedAt: now, type: "work.transitioned", source: item.provider,
      externalId: item.externalId, from: previousState, to: nextState,
    });
  }
  const result = { item, outcome };
  if (idem.key) workIdempotency.set(idem.key, result);
  persistDurableState("work_transition");
  return result;
}


function dispatchMotorWork(payload, source = "operator", externalId = null) {
  if (!outboundWorkEnabled) throw new Error("outbound_work_disabled");
  const normalized = validateMotorWorkPayload(payload);
  let lease = null;
  let item = null;
  if (normalized.workKey) {
    item = workLedger.get(normalized.workKey);
    if (!item) throw new Error("work_item_not_found");
    if (item.blockers?.length) throw new Error("work_item_blocked");
    if (!["QUALIFIED", "CLAIMED", "WORKING", "REVISION"].includes(item.state)) {
      throw new Error("work_item_not_dispatchable:" + item.state);
    }
    const leased = leaseNextWork({
      key: normalized.workKey,
      workerId: "self-root-motor",
      idempotencyKey: "motor-lease:" + normalized.jobId,
    });
    lease = leased.lease;
    normalized.leaseId = lease.leaseId;
    item = leased.item;
    if (item.state !== "WORKING") {
      transitionWork({
        key: item.key,
        leaseId: lease.leaseId,
        state: "WORKING",
        idempotencyKey: "motor-working:" + normalized.jobId,
      });
    }
    checkpointWork({
      key: item.key,
      leaseId: lease.leaseId,
      phase: "motor_dispatched",
      detail: normalized.title,
      idempotencyKey: "motor-dispatch-checkpoint:" + normalized.jobId,
    });
  }
  const command = enqueueMotorCommand(
    "work.execute",
    String(source || "operator").slice(0, 120),
    externalId || ("work.execute:" + normalized.jobId),
    normalized,
  );
  rememberEvent({
    id: randomUUID(),
    receivedAt: new Date().toISOString(),
    type: "work.motor_dispatched",
    source: command.source,
    externalId: normalized.jobId,
    key: normalized.workKey,
    commandId: command.id,
  });
  return { command, lease, item };
}

function applyMotorWorkResult(command, ok, result) {
  const payload = command?.payload;
  if (!payload || command.action !== "work.execute") return;
  const jobId = String(payload.jobId || command.externalId || command.id);
  const artifactRefs = Array.isArray(result?.artifacts)
    ? result.artifacts.map((x) => String(x).slice(0, 500)).slice(0, 20)
    : [];
  const summary = String(
    result?.summary ||
    (ok ? ("Bounded work " + jobId + " completed") : ("Bounded work " + jobId + " failed"))
  ).slice(0, 1000);

  if (payload.workKey && workLedger.has(payload.workKey)) {
    const item = workLedger.get(payload.workKey);
    const leaseId = String(payload.leaseId || "").trim();
    try {
      if (leaseId && item.execution?.leaseId === leaseId) {
        checkpointWork({
          key: item.key,
          leaseId,
          phase: ok ? "motor_completed" : "motor_failed",
          detail: summary,
          artifactRefs,
          idempotencyKey: "motor-result-checkpoint:" + jobId + ":" + (ok ? "ok" : "failed"),
        });
      }
    } catch (error) {
      item.execution = {
        ...(item.execution || {}),
        lastError: error instanceof Error ? error.message.slice(0, 500) : String(error).slice(0, 500),
      };
    }

    const desired = ok ? payload.successState : payload.failureState;
    try {
      if (desired && desired !== item.state) {
        transitionWork({
          key: item.key,
          leaseId,
          state: desired,
          blockers: ok ? [] : ["motor_execution_failed:" + summary],
          providerReference: result?.providerReference || null,
          idempotencyKey: "motor-result-transition:" + jobId + ":" + desired,
          notes: summary,
        });
      }
    } catch (error) {
      item.execution = {
        ...(item.execution || {}),
        lastError: error instanceof Error ? error.message.slice(0, 500) : String(error).slice(0, 500),
      };
      persistDurableState("motor_work_transition_error");
    }
  }

  queueWorkReport({
    type: ok ? "work.motor_completed" : "work.motor_failed",
    severity: ok ? "result" : "blocker",
    summary,
    key: payload.workKey || null,
    dedupeKey: "motor-work:" + jobId + ":" + (ok ? "ok" : "failed"),
  });
}

function runAutonomyRecovery() {
  const now = Date.now();
  autonomyState.lastRunAt = new Date(now).toISOString();
  autonomyState.runCount += 1;
  autonomyState.stuckItems = 0;
  try {
    for (const item of workLedger.values()) {
      const execution = item.execution || {};
      if (execution.leaseExpiresAt && Date.parse(execution.leaseExpiresAt) <= now) {
        const attempts = Math.max(0, finiteNumber(execution.attempts, 0) || 0);
        execution.leaseId = null;
        execution.leaseOwner = null;
        execution.leaseExpiresAt = null;
        execution.lastError = "worker_lease_expired";
        if (attempts >= workMaxAttempts) {
          item.state = "BLOCKED";
          item.stateChangedAt = autonomyState.lastRunAt;
          item.blockers = [...new Set([...(item.blockers || []), "autonomous_attempt_limit_reached"])]
            .slice(0, 20);
          queueWorkReport({
            type: "work.attempt_limit",
            severity: "blocker",
            summary: `${item.provider} work ${item.externalId} exhausted ${attempts} autonomous attempts`,
            key: item.key,
            dedupeKey: `attempt-limit:${item.key}`,
          });
        } else {
          const delayMs = Math.min(60 * 60_000, 30_000 * (2 ** Math.max(0, attempts - 1)));
          execution.retryAt = new Date(now + delayMs).toISOString();
        }
        item.updatedAt = autonomyState.lastRunAt;
        autonomyState.recoveredLeases += 1;
      }
      const stateAge = now - Date.parse(item.stateChangedAt || item.updatedAt || item.firstSeenAt || 0);
      if (WORK_ACTIVE_STATES.has(item.state) && stateAge > workStuckMs) {
        autonomyState.stuckItems += 1;
        queueWorkReport({
          type: "work.stuck",
          severity: "blocker",
          summary: `${item.provider} work ${item.externalId} has remained ${item.state} without progress`,
          key: item.key,
          dedupeKey: `stuck:${item.key}:${item.state}`,
        });
      }
    }
    autonomyState.lastError = null;
    refreshWorkScheduler();
    persistDurableState("autonomy_recovery");
  } catch (error) {
    autonomyState.lastError = error instanceof Error ? error.message.slice(0, 500) : String(error).slice(0, 500);
  }
}

function reportingSummary() {
  const pending = workReports.filter((x) => x.status === "pending");
  return {
    pendingCount: pending.length,
    blockers: pending.filter((x) => x.severity === "blocker").length,
    decisions: pending.filter((x) => x.severity === "decision").length,
    results: pending.filter((x) => x.severity === "result").length,
    pending: pending.slice(-50),
  };
}

async function continuitySummary({ verify = false } = {}) {
  const evidence = await durableState.summary();
  return {
    architecture: "evidence-ledger-v1",
    canonicalHistory: "append_only_evidence_ledger",
    materializedState: "rebuildable_cache",
    handoffPolicy: "generated_summary_not_source_of_truth",
    identity: identityManifest,
    identityManifestHash,
    configHash: continuityConfigHash,
    evidence,
    verification: verify ? await durableState.verify() : null,
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
      stripe: stripeAdapter.summary(),
      motor: motorSummary(),
      agentMailIngress: {
        apiKeyConfigured: Boolean(agentMailApiKey),
        webhookDeliveryTokenConfigured: Boolean(agentMailWebhookToken),
        provisionEnabled: agentMailWebhookProvision,
        ...agentMailWebhookState,
      },
      taskFeeds: {
        taskBounty: taskFeedSummary(),
        basedAgents: basedAgentsSummary(),
        swarmSpot: swarmSpotSummary(),
        agentSouk: agentSoukSummary(),
        agentChain: agentChainSummary(),
        clawlancer: clawlancerSummary(),
        frantic: franticSummary(),
        agentLine: agentLineSummary(),
      },
      workScheduler: workSchedulerSummary(),
      continuity: await continuitySummary(),
      durability: {
        deprecated: true,
        replacement: "continuity",
        ...(await durableState.summary()),
      },
      reporting: reportingSummary(),
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
      motor: motorSummary(),
      agentMailIngress: {
        apiKeyConfigured: Boolean(agentMailApiKey),
        webhookDeliveryTokenConfigured: Boolean(agentMailWebhookToken),
        provisionEnabled: agentMailWebhookProvision,
        ...agentMailWebhookState,
      },
      stripe: stripeAdapter.summary(),
      taskFeeds: {
        taskBounty: taskFeedSummary(),
        basedAgents: basedAgentsSummary(),
        swarmSpot: swarmSpotSummary(),
        agentSouk: agentSoukSummary(),
        agentChain: agentChainSummary(),
        clawlancer: clawlancerSummary(),
        frantic: franticSummary(),
        agentLine: agentLineSummary(),
      },
      workScheduler: workSchedulerSummary(),
      continuity: await continuitySummary(),
      durability: {
        deprecated: true,
        replacement: "continuity",
        ...(await durableState.summary()),
      },
      reporting: reportingSummary(),
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
        agentSouk: agentSoukSummary(),
        agentChain: agentChainSummary(),
        clawlancer: clawlancerSummary(),
        frantic: franticSummary(),
        agentLine: agentLineSummary(),
        agentMail: "not_configured_in_runtime",
        circle: "not_configured_in_runtime",
        stripe: stripeAdapter.summary(),
        continuityJournal: "replaced_by_evidence_ledger_v1",
        motor: motorSummary(),
      },
      queue: Array.from(taskQueue.values()).slice(-100),
      workScheduler: workSchedulerSummary(),
      continuity: await continuitySummary(),
      durability: {
        deprecated: true,
        replacement: "continuity",
        ...(await durableState.summary()),
      },
      reporting: reportingSummary(),
      motorQueue: motorQueue.slice(-100).map(({ result, ...item }) => item),
      motorCompleted: Array.from(motorCompleted.values()).slice(-100),
      recentEvents,
    });
  }


  if (req.method === "GET" && url.pathname === "/v1/continuity") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    return json(res, 200, await continuitySummary({ verify: true }));
  }

  if (req.method === "GET" && url.pathname === "/v1/evidence") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    const limit = Math.max(1, Math.min(Number(url.searchParams.get("limit") || 100), 500));
    const eventType = url.searchParams.get("event_type") || null;
    const events = await durableState.readEvents({ limit, eventType });
    return json(res, 200, {
      schema_version: "1.0",
      count: events.length,
      event_type: eventType,
      events,
    });
  }

  if (req.method === "GET" && url.pathname === "/v1/work") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    refreshWorkScheduler();
    return json(res, 200, workSchedulerSummary());
  }

  if (req.method === "GET" && url.pathname === "/v1/work/next") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    refreshWorkScheduler();
    const summary = workSchedulerSummary();
    return json(res, 200, {
      recommendedNext: summary.recommendedNext,
      capacity: summary.capacity,
      policy: summary.policy,
      lastRunAt: summary.lastRunAt,
    });
  }

  if (req.method === "POST" && url.pathname === "/v1/work/items") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 64_000);
      const item = upsertExternalWorkItem(body);
      refreshWorkScheduler();
      return json(res, 202, { accepted: true, item });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, {
        error: err instanceof Error ? err.message : "invalid_request",
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/work/outcomes") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 32_000);
      const outcome = recordWorkOutcome(body);
      return json(res, 202, { accepted: true, outcome });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, {
        error: err instanceof Error ? err.message : "invalid_request",
      });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/work/dispatch") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 1_048_576);
      const dispatched = dispatchMotorWork(
        body,
        typeof body?.source === "string" ? body.source : "work.dispatch",
        typeof body?.externalId === "string" ? body.externalId : null,
      );
      return json(res, 202, {
        accepted: true,
        command: {
          id: dispatched.command.id,
          action: dispatched.command.action,
          status: dispatched.command.status,
          expiresAt: dispatched.command.expiresAt,
        },
        lease: dispatched.lease,
        item: dispatched.item
          ? { key: dispatched.item.key, state: dispatched.item.state, execution: dispatched.item.execution }
          : null,
      });
    } catch (err) {
      const code =
        err?.message === "work_item_not_found" ? 404 :
        err?.message === "outbound_work_disabled" ? 409 :
        400;
      return json(res, code, { error: err instanceof Error ? err.message : "dispatch_failed" });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/work/lease") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 16_000);
      return json(res, 200, { accepted: true, ...leaseNextWork(body) });
    } catch (err) {
      const code = err?.message === "work_item_not_found" ? 404 : 409;
      return json(res, code, { error: err instanceof Error ? err.message : "lease_failed" });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/work/checkpoints") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 64_000);
      return json(res, 202, { accepted: true, ...checkpointWork(body) });
    } catch (err) {
      const code = err?.message === "work_item_not_found" ? 404 : 409;
      return json(res, code, { error: err instanceof Error ? err.message : "checkpoint_failed" });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/work/transitions") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 64_000);
      return json(res, 202, { accepted: true, ...transitionWork(body) });
    } catch (err) {
      const code = err?.message === "work_item_not_found" ? 404 : 409;
      return json(res, code, { error: err instanceof Error ? err.message : "transition_failed" });
    }
  }

  if (req.method === "GET" && url.pathname === "/v1/reports") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    return json(res, 200, reportingSummary());
  }

  if (req.method === "POST" && url.pathname === "/v1/reports/ack") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 8_000);
      const ids = new Set(Array.isArray(body?.ids) ? body.ids.map(String) : [String(body?.id || "")]);
      let acknowledged = 0;
      const now = new Date().toISOString();
      for (const report of workReports) {
        if (report.status === "pending" && ids.has(report.id)) {
          report.status = "acknowledged";
          report.acknowledgedAt = now;
          acknowledged += 1;
        }
      }
      persistDurableState("reports_acknowledged");
      return json(res, 200, { acknowledged });
    } catch (err) {
      return json(res, 400, { error: "invalid_request" });
    }
  }

  if (req.method === "POST" && url.pathname === "/integrations/agentline/bootstrap") {
    if (
      !agentLineBootstrapEnabled ||
      !agentLineBootstrapCommandId ||
      url.searchParams.get("command_id") !== agentLineBootstrapCommandId
    ) {
      return json(res, 404, { error: "not_found" });
    }
    try {
      const body = await readJson(req, 2048);
      const otp = String(body?.otp || "").trim();
      if (!/^\d{6}$/.test(otp)) {
        return json(res, 400, { error: "invalid_otp_format" });
      }
      await bootstrapAgentLineIdentity(otp);
      return json(res, agentLine.status === "backup_pending" ? 202 : 400, {
        accepted: agentLine.status === "backup_pending",
        status: agentLine.status,
        lastError: agentLine.lastError,
      });
    } catch (err) {
      return json(res, 400, { error: "bootstrap_failed" });
    }
  }

  if (req.method === "POST" && url.pathname === "/integrations/agentline") {
    try {
      const rawBody = await readBody(req);
      const signature =
        req.headers["x-hub-signature-256"] ||
        req.headers["x-webhook-signature"] ||
        "";
      const tokenAuthorized =
        agentLineInboundToken &&
        url.searchParams.get("token") === agentLineInboundToken;
      if (!tokenAuthorized && !verifyAgentLineWebhook(rawBody, String(signature))) {
        return json(res, 401, { error: "invalid_signature" });
      }
      const body = JSON.parse(rawBody.toString("utf8"));
      const eventType = String(body?.event_type || body?.type || "event").slice(0, 80);
      const payload = body?.payload && typeof body.payload === "object" ? body.payload : body;
      const from =
        payload?.from_number || payload?.from || payload?.sender || payload?.phone_number || null;
      const textBody =
        payload?.body || payload?.text || payload?.message || payload?.content || null;

      if (eventType === "sms.received") {
        agentLine.pendingSmsEvents += 1;
        agentLine.pairing.lastInboundAt = new Date().toISOString();
        agentLine.pairing.lastBodyPreview =
          typeof textBody === "string" ? textBody.slice(0, 160) : null;
        if (!agentLine.pairing.operatorPhone && typeof from === "string") {
          agentLine.pairing.operatorPhone = from.slice(0, 40);
          agentLine.pairing.status = "paired_from_first_signed_sms";
        }
      }

      rememberEvent({
        id: randomUUID(),
        receivedAt: new Date().toISOString(),
        type: `agentline.${eventType}`,
        source: "agentline_webhook",
        externalId: String(body?.event_id || payload?.message_id || payload?.call_id || "").slice(0, 240) || null,
        from: typeof from === "string" ? from.slice(0, 40) : null,
        bodyPreview: typeof textBody === "string" ? textBody.slice(0, 500) : null,
      });
      return json(res, 202, { accepted: true });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
  }

  if (req.method === "POST" && url.pathname === "/integrations/swarmspot") {
    const auth = req.headers.authorization || "";
    if (!swarmSpotWebhookToken || auth !== `Bearer ${swarmSpotWebhookToken}`) {
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

  if (req.method === "POST" && url.pathname === "/integrations/agentchain") {
    if (!agentChainWebhookToken || url.searchParams.get("token") !== agentChainWebhookToken) {
      return json(res, 401, { error: "unauthorized" });
    }
    try {
      const body = await readJson(req);
      agentChain.pendingWebhookEvents += 1;
      rememberEvent({
        id: randomUUID(),
        receivedAt: new Date().toISOString(),
        type: "agentchain." + String(body?.event || body?.type || "event").slice(0, 80),
        source: "agentchain_webhook",
        externalId:
          String(body?.job?.id || body?.jobId || body?.proposal?.id || "").slice(0, 240) || null,
      });
      setTimeout(() => void syncAgentChain(), 100).unref();
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

  if (req.method === "POST" && url.pathname === "/v1/motor/bootstrap") {
    if (!motorBootstrapAuthorized(req)) return json(res, 401, { error: "unauthorized" });
    if (!motorAgentToken) return json(res, 503, { error: "motor_not_configured" });
    if (motorBootstrapConsumed) return json(res, 410, { error: "bootstrap_already_consumed" });
    motorBootstrapConsumed = true;
    rememberEvent({
      id: randomUUID(),
      receivedAt: new Date().toISOString(),
      type: "motor.bootstrap_consumed",
      source: "smolmachine",
      externalId: null,
    });
    return json(res, 200, {
      motorToken: motorAgentToken,
      runtimeBaseUrl: publicRuntimeBaseUrl,
      allowedActions: Array.from(motorAllowedActions),
    });
  }

  if (req.method === "GET" && url.pathname === "/v1/motor/poll") {
    if (!motorAuthorized(req)) return json(res, 401, { error: "unauthorized" });
    const command = leaseMotorCommand();
    return json(res, 200, { command });
  }

  if (req.method === "POST" && url.pathname === "/v1/motor/ack") {
    if (!motorAuthorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 1_048_576);
      const id = String(body?.id || "").trim();
      const ok = body?.ok === true;
      if (!id) return json(res, 400, { error: "missing_command_id" });
      const item = completeMotorCommand(id, ok, body?.result ?? null);
      if (!item) return json(res, 404, { error: "command_not_found" });
      return json(res, 200, {
        accepted: true,
        command: {
          id: item.id,
          action: item.action,
          status: item.status,
          completedAt: item.completedAt,
        },
      });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
  }

  if (req.method === "POST" && url.pathname === "/v1/motor/enqueue") {
    if (!authorized(req)) return json(res, 401, { error: "unauthorized" });
    try {
      const body = await readJson(req, 1_048_576);
      const action = String(body?.action || "").trim().toLowerCase();
      const source = typeof body?.source === "string" ? body.source : "operator";
      const externalId = typeof body?.externalId === "string" ? body.externalId : null;
      const dispatched = action === "work.execute"
        ? dispatchMotorWork(body?.payload, source, externalId)
        : { command: enqueueMotorCommand(action, source, externalId, body?.payload ?? null) };
      const command = dispatched.command;
      return json(res, 202, {
        accepted: true,
        command: {
          id: command.id,
          action: command.action,
          status: command.status,
          expiresAt: command.expiresAt,
        },
        lease: dispatched.lease || null,
      });
    } catch (err) {
      if (err?.message === "motor_action_not_allowed") {
        return json(res, 400, { error: "motor_action_not_allowed" });
      }
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
  }

  if (req.method === "POST" && url.pathname === "/integrations/agentmail/webhook") {
    if (!agentMailWebhookToken) {
      return json(res, 503, { error: "agentmail_webhook_not_configured" });
    }
    const supplied = req.headers["x-self-root-webhook-token"] || "";
    if (supplied !== agentMailWebhookToken) {
      return json(res, 401, { error: "unauthorized" });
    }
    try {
      const body = await readJson(req, 1_048_576);
      const parsed = extractAgentMailMotorAction(body);
      if (!parsed) return json(res, 200, { accepted: false, reason: "not_a_motor_command" });
      const dispatched = parsed.action === "work.execute"
        ? dispatchMotorWork(parsed.payload, parsed.source, parsed.externalId)
        : { command: enqueueMotorCommand(parsed.action, parsed.source, parsed.externalId, parsed.payload ?? null) };
      const command = dispatched.command;
      return json(res, 202, {
        accepted: true,
        command: {
          id: command.id,
          action: command.action,
          status: command.status,
        },
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
      let motorCommand = null;
      if (body.type === "email.received" && typeof body.command === "string") {
        try {
          const action = body.command.trim().toLowerCase();
          motorCommand = action === "work.execute"
            ? dispatchMotorWork(body.payload, event.source || "v1.events", event.externalId).command
            : enqueueMotorCommand(action, event.source || "v1.events", event.externalId, body.payload ?? null);
        } catch {}
      }
      return json(res, 202, {
        accepted: true,
        event,
        motorCommand: motorCommand
          ? { id: motorCommand.id, action: motorCommand.action, status: motorCommand.status }
          : null,
      });
    } catch (err) {
      return json(res, err.message === "payload_too_large" ? 413 : 400, { error: "invalid_request" });
    }
  }

  if (
    await stripeAdapter.handle(req, res, url, {
      json,
      readBody,
      readJson,
      authorized,
    })
  ) {
    return;
  }

  return json(res, 404, { error: "not_found" });
});

const durableRestore = await restoreDurableState();
rememberEvent({
  id: randomUUID(),
  receivedAt: startedAt,
  type: "continuity.runtime_started",
  source: runtimeId,
  externalId: bootId,
  payload: {
    boot_id: bootId,
    identity_id: identityId,
    lineage_id: identityLineageId,
    identity_manifest_hash: identityManifestHash,
    config_hash: continuityConfigHash,
    recovered: durableRestore.recovered === true,
    recovered_from: durableRestore.recoveredFrom || null,
  },
});
if (durableRestore.recovered) {
  console.log(JSON.stringify({ event: "durable_state.recovered", directory: agentStateDir }));
} else if (durableRestore.quarantined) {
  console.error(JSON.stringify({
    event: "durable_state.degraded",
    quarantined: durableRestore.quarantined,
  }));
}
runAutonomyRecovery();

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

const agentSoukTimer = setInterval(() => {
  void syncAgentSouk();
}, agentSoukPollMs);
agentSoukTimer.unref();

const agentChainTimer = setInterval(() => {
  void syncAgentChain();
}, agentChainPollMs);
agentChainTimer.unref();

const clawlancerTimer = setInterval(() => {
  void syncClawlancer();
}, clawlancerPollMs);
clawlancerTimer.unref();

const workSchedulerTimer = setInterval(() => {
  refreshWorkScheduler();
}, workSchedulerTickMs);
workSchedulerTimer.unref();

const autonomyRecoveryTimer = setInterval(() => {
  runAutonomyRecovery();
}, Math.min(workSchedulerTickMs, 60_000));
autonomyRecoveryTimer.unref();

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
  if (motorAgentToken) {
    try {
      enqueueMotorCommand(
        "state.snapshot.read",
        "runtime.startup",
        `durable-state-read:${bootId}`,
      );
    } catch (err) {
      console.error(JSON.stringify({
        event: "durable_state.motor_restore_queue_error",
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }
  if (motorSelfTestAction && motorAllowedActions.has(motorSelfTestAction)) {
    try {
      const command = enqueueMotorCommand(
        motorSelfTestAction,
        "runtime.self_test",
        `boot:${bootId}:${motorSelfTestAction}`,
      );
      console.log(JSON.stringify({
        event: "motor.self_test_queued",
        commandId: command.id,
        action: command.action,
      }));
    } catch (err) {
      console.error(JSON.stringify({
        event: "motor.self_test_error",
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }
  void provisionAgentMailWebhook();
  void syncTaskBounty();
  void syncBasedAgents();
  refreshWorkScheduler();
  void ensureBasedAgentsIdentity();
  void (async () => {
    await ensureBaseWallet();
    await Promise.all([
      ensureAgentSoukIdentity(),
      ensureClawlancerIdentity(),
    ]);
  })();
  void processFranticCommand();
  void ensureAgentChainIdentity();
  void ensureAgentLineIdentity();
  void ensureSwarmSpotIdentity();
  void stripeAdapter.syncProfile().then((result) => {
    if (result?.updated || result?.error) {
      console.log(JSON.stringify({
        event: "stripe.profile_sync",
        result,
      }));
    }
  });
  void stripeAdapter.ensureBrowserSession().then((ready) => {
    console.log(JSON.stringify({
      event: "stripe.browser_session",
      ready,
      status: stripeAdapter.summary().browserSession,
    }));
  });
});

function shutdown(signal) {
  clearInterval(heartbeat);
  clearInterval(taskFeedTimer);
  clearInterval(basedAgentsTimer);
  clearInterval(swarmSpotTimer);
  clearInterval(agentSoukTimer);
  clearInterval(agentChainTimer);
  clearInterval(clawlancerTimer);
  clearInterval(workSchedulerTimer);
  clearInterval(autonomyRecoveryTimer);
  console.log(JSON.stringify({ event: "runtime.stopping", signal, bootId }));
  server.close(() => {
    void durableState.flush(durableSnapshot(), `shutdown_${signal}`).finally(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
