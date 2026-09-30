import { createHash, randomUUID } from "node:crypto";
import {
  appendFile,
  copyFile,
  mkdir,
  readFile,
  rename,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

const MATERIALIZED_SCHEMA = 2;
const LEGACY_SNAPSHOT_SCHEMA = 1;
const EVIDENCE_SCHEMA_VERSION = "1.0";

function cleanReason(value) {
  return String(value || "unspecified").replace(/[^a-z0-9._-]/gi, "_").slice(0, 80);
}

function sortForCanonicalJson(value) {
  if (Array.isArray(value)) return value.map(sortForCanonicalJson);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, sortForCanonicalJson(value[key])]),
  );
}

function canonicalJson(value) {
  return JSON.stringify(sortForCanonicalJson(value));
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function validIso(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function validateEvidenceRecord(record) {
  if (!isObject(record)) throw new Error("invalid_evidence_record");
  if (record.schema_version !== EVIDENCE_SCHEMA_VERSION) {
    throw new Error("unsupported_evidence_schema");
  }
  for (const key of [
    "event_id",
    "correlation_id",
    "event_type",
    "occurred_at",
    "recorded_at",
    "source",
  ]) {
    if (typeof record[key] !== "string" || !record[key]) {
      throw new Error("invalid_evidence_" + key);
    }
  }
  if (!validIso(record.occurred_at) || !validIso(record.recorded_at)) {
    throw new Error("invalid_evidence_timestamp");
  }
  if (!isObject(record.payload) || !isObject(record.provenance)) {
    throw new Error("invalid_evidence_payload_or_provenance");
  }
  if (
    typeof record.provenance.software_version !== "string" ||
    typeof record.provenance.config_hash !== "string"
  ) {
    throw new Error("invalid_evidence_provenance");
  }
  return record;
}

function stripLegacyEnvelopeFields(event) {
  const payload = {};
  const reserved = new Set([
    "schema",
    "schema_version",
    "id",
    "event_id",
    "correlation_id",
    "correlationId",
    "parent_event_id",
    "parentEventId",
    "type",
    "event_type",
    "receivedAt",
    "occurredAt",
    "occurred_at",
    "recordedAt",
    "recorded_at",
    "source",
    "strategy_id",
    "strategyId",
    "strategy_version",
    "strategyVersion",
    "provenance",
    "payload",
  ]);
  for (const [key, value] of Object.entries(event || {})) {
    if (!reserved.has(key) && value !== undefined) payload[key] = value;
  }
  return payload;
}

export function createDurableState({
  directory,
  now = () => new Date(),
  debounceMs = 250,
  softwareVersion = "unknown",
  configHash = "unknown",
  datasetVersion = null,
  onEvidenceRecord = null,
} = {}) {
  if (!directory) throw new Error("durable_state_directory_required");

  const materializedPath = path.join(directory, "materialized-state-v1.json");
  const evidencePath = path.join(directory, "evidence-ledger-v1.jsonl");
  const legacySnapshotPath = path.join(directory, "agent-state-v1.json");
  const legacyEventPath = path.join(directory, "events-v1.jsonl");

  let status = "not_initialized";
  let lastError = null;
  let lastLoadedAt = null;
  let lastSavedAt = null;
  let lastSaveReason = null;
  let saveCount = 0;
  let eventCount = 0;
  let ledgerHeadHash = null;
  let chainValid = true;
  let lastEvidenceAt = null;
  let lastMaterializedHash = null;
  let migrationSource = null;
  let pendingTimer = null;
  let pendingSnapshot = null;
  let pendingReason = null;
  let ioChain = Promise.resolve();

  function enqueue(operation) {
    ioChain = ioChain.then(operation, operation);
    return ioChain;
  }

  function notifyRecord(record) {
    if (typeof onEvidenceRecord !== "function") return;
    try {
      const maybePromise = onEvidenceRecord(record);
      if (maybePromise?.catch) maybePromise.catch(() => {});
    } catch {}
  }

  function normalizeEvidenceEvent(event, {
    sourceOverride = null,
    softwareVersionOverride = null,
    configHashOverride = null,
    datasetVersionOverride = undefined,
  } = {}) {
    const input = isObject(event) ? event : {};
    const recordedAt = now().toISOString();
    const eventId = String(input.event_id || input.id || randomUUID()).slice(0, 240);
    const correlationId = String(
      input.correlation_id ||
      input.correlationId ||
      input.externalId ||
      input.key ||
      eventId
    ).slice(0, 320);
    const occurredAtRaw =
      input.occurred_at ||
      input.occurredAt ||
      input.receivedAt ||
      input.recorded_at ||
      input.recordedAt ||
      recordedAt;
    const occurredAt = validIso(occurredAtRaw) ? new Date(occurredAtRaw).toISOString() : recordedAt;
    const explicitPayload = isObject(input.payload) ? input.payload : {};
    const payload = {
      ...stripLegacyEnvelopeFields(input),
      ...explicitPayload,
    };
    const existingProvenance = isObject(input.provenance) ? input.provenance : {};
    const provenance = {
      software_version: String(
        softwareVersionOverride ||
        existingProvenance.software_version ||
        softwareVersion ||
        "unknown"
      ).slice(0, 160),
      config_hash: String(
        configHashOverride ||
        existingProvenance.config_hash ||
        configHash ||
        "unknown"
      ).slice(0, 160),
      dataset_version:
        datasetVersionOverride !== undefined
          ? datasetVersionOverride
          : existingProvenance.dataset_version ?? datasetVersion ?? null,
      ledger_seq: eventCount + 1,
      previous_event_hash: ledgerHeadHash,
    };
    const record = {
      schema_version: EVIDENCE_SCHEMA_VERSION,
      event_id: eventId,
      correlation_id: correlationId,
      parent_event_id: input.parent_event_id || input.parentEventId || null,
      event_type: String(input.event_type || input.type || "runtime.event").slice(0, 200),
      occurred_at: occurredAt,
      recorded_at: recordedAt,
      source: String(sourceOverride || input.source || "agent-core").slice(0, 200),
      strategy_id: input.strategy_id || input.strategyId || null,
      strategy_version: input.strategy_version || input.strategyVersion || null,
      payload,
      provenance,
    };
    validateEvidenceRecord(record);
    const eventHash = sha256(canonicalJson(record));
    record.provenance.event_hash = eventHash;
    return record;
  }

  async function appendRecordUnlocked(event, options = {}) {
    const record = normalizeEvidenceEvent(event, options);
    await mkdir(directory, { recursive: true, mode: 0o700 });
    await appendFile(evidencePath, JSON.stringify(record) + "\n", { mode: 0o600 });
    eventCount += 1;
    ledgerHeadHash = record.provenance.event_hash;
    lastEvidenceAt = record.recorded_at;
    chainValid = chainValid && true;
    notifyRecord(record);
    return record;
  }

  async function scanLedger() {
    let raw;
    try {
      raw = await readFile(evidencePath, "utf8");
    } catch (error) {
      if (error?.code === "ENOENT") {
        return { count: 0, headHash: null, checkpoint: null, chainValid: true };
      }
      throw error;
    }

    let expectedPrevious = null;
    let count = 0;
    let checkpoint = null;
    let valid = true;
    for (const line of raw.split("\n")) {
      if (!line.trim()) continue;
      const record = validateEvidenceRecord(JSON.parse(line));
      const expectedSeq = count + 1;
      const seq = Number(record.provenance?.ledger_seq);
      if (Number.isFinite(seq) && seq !== expectedSeq) valid = false;
      if (
        Object.prototype.hasOwnProperty.call(record.provenance, "previous_event_hash") &&
        (record.provenance.previous_event_hash ?? null) !== expectedPrevious
      ) {
        valid = false;
      }
      const suppliedHash = record.provenance?.event_hash || null;
      const copy = JSON.parse(JSON.stringify(record));
      if (copy.provenance) delete copy.provenance.event_hash;
      const calculatedHash = sha256(canonicalJson(copy));
      if (suppliedHash && suppliedHash !== calculatedHash) valid = false;
      expectedPrevious = suppliedHash || calculatedHash;
      count += 1;
      if (
        ["continuity.state_checkpoint", "continuity.legacy_snapshot_imported"].includes(record.event_type) &&
        isObject(record.payload?.state)
      ) {
        checkpoint = {
          state: record.payload.state,
          stateHash: record.payload.state_hash || sha256(canonicalJson(record.payload.state)),
          eventId: record.event_id,
          recordedAt: record.recorded_at,
          reason: record.payload.reason || record.event_type,
        };
      }
    }
    return { count, headHash: expectedPrevious, checkpoint, chainValid: valid };
  }

  async function loadMaterialized() {
    try {
      const raw = await readFile(materializedPath, "utf8");
      const parsed = JSON.parse(raw);
      if (parsed?.schema !== MATERIALIZED_SCHEMA || !isObject(parsed?.state)) {
        throw new Error("unsupported_or_invalid_materialized_state");
      }
      const computed = sha256(canonicalJson(parsed.state));
      if (parsed.state_hash && parsed.state_hash !== computed) {
        throw new Error("materialized_state_hash_mismatch");
      }
      return { envelope: parsed, state: parsed.state, stateHash: computed };
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      const quarantine = materializedPath + ".corrupt-" + Date.now();
      await copyFile(materializedPath, quarantine).catch(() => {});
      throw Object.assign(new Error(
        "materialized_load_failed:" + (error instanceof Error ? error.message : String(error))
      ), { quarantine });
    }
  }

  async function loadLegacySnapshot() {
    try {
      const raw = await readFile(legacySnapshotPath, "utf8");
      const parsed = JSON.parse(raw);
      if (parsed?.schema !== LEGACY_SNAPSHOT_SCHEMA || !isObject(parsed?.state)) {
        throw new Error("unsupported_or_invalid_legacy_snapshot");
      }
      return {
        state: parsed.state,
        capturedAt: parsed.capturedAt || null,
        reason: parsed.reason || "legacy_snapshot",
        hash: sha256(raw),
      };
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      const quarantine = legacySnapshotPath + ".corrupt-" + Date.now();
      await copyFile(legacySnapshotPath, quarantine).catch(() => {});
      throw Object.assign(new Error(
        "legacy_snapshot_load_failed:" + (error instanceof Error ? error.message : String(error))
      ), { quarantine });
    }
  }

  async function legacyEventDigest() {
    try {
      const raw = await readFile(legacyEventPath, "utf8");
      return {
        exists: true,
        bytes: Buffer.byteLength(raw),
        lines: raw.split("\n").filter((line) => line.trim()).length,
        sha256: sha256(raw),
      };
    } catch (error) {
      if (error?.code === "ENOENT") {
        return { exists: false, bytes: 0, lines: 0, sha256: null };
      }
      throw error;
    }
  }

  async function writeMaterializedUnlocked(state, reason, sourceEvent) {
    const capturedAt = now().toISOString();
    const stateHash = sha256(canonicalJson(state));
    const tempPath = materializedPath + ".tmp-" + process.pid + "-" + Date.now();
    const envelope = {
      schema: MATERIALIZED_SCHEMA,
      schema_version: EVIDENCE_SCHEMA_VERSION,
      generated_at: capturedAt,
      reason: cleanReason(reason),
      state_hash: stateHash,
      source_event_id: sourceEvent?.event_id || null,
      ledger_head_hash: ledgerHeadHash,
      ledger_event_count: eventCount,
      state,
    };
    await writeFile(tempPath, JSON.stringify(envelope) + "\n", { mode: 0o600 });
    await rename(tempPath, materializedPath);
    lastMaterializedHash = stateHash;
    lastSavedAt = capturedAt;
    lastSaveReason = envelope.reason;
    saveCount += 1;
    return envelope;
  }

  async function init() {
    status = "initializing";
    try {
      await mkdir(directory, { recursive: true, mode: 0o700 });

      const scanned = await scanLedger();
      eventCount = scanned.count;
      ledgerHeadHash = scanned.headHash;
      chainValid = scanned.chainValid;

      let materialized = null;
      try {
        materialized = await loadMaterialized();
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error);
      }

      if (materialized) {
        lastMaterializedHash = materialized.stateHash;
        lastLoadedAt = now().toISOString();
        status = chainValid ? "ready" : "degraded";
        return {
          snapshot: materialized.state,
          recovered: true,
          recoveredFrom: "materialized_cache",
          quarantined: null,
        };
      }

      if (scanned.checkpoint) {
        const envelope = await writeMaterializedUnlocked(
          scanned.checkpoint.state,
          "rebuild_from_evidence",
          { event_id: scanned.checkpoint.eventId },
        );
        lastMaterializedHash = envelope.state_hash;
        lastLoadedAt = now().toISOString();
        status = chainValid ? "ready" : "degraded";
        migrationSource = "evidence_checkpoint";
        return {
          snapshot: scanned.checkpoint.state,
          recovered: true,
          recoveredFrom: "evidence_ledger",
          quarantined: null,
        };
      }

      const legacy = await loadLegacySnapshot();
      if (legacy) {
        const legacyEvents = await legacyEventDigest();
        const stateHash = sha256(canonicalJson(legacy.state));
        const migrationRecord = await appendRecordUnlocked({
          type: "continuity.legacy_snapshot_imported",
          source: "legacy.continuity",
          receivedAt: legacy.capturedAt || now().toISOString(),
          correlationId: "continuity-migration-v1",
          payload: {
            reason: legacy.reason,
            state_hash: stateHash,
            state: legacy.state,
            legacy_snapshot: {
              path: path.basename(legacySnapshotPath),
              sha256: legacy.hash,
            },
            legacy_event_log: {
              path: path.basename(legacyEventPath),
              ...legacyEvents,
            },
            migration_policy: "preserve_legacy_files_read_only",
          },
        }, {
          softwareVersionOverride: "legacy-import",
          configHashOverride: "legacy-unknown",
          datasetVersionOverride: null,
        });
        await writeMaterializedUnlocked(legacy.state, "legacy_migration", migrationRecord);
        migrationSource = "legacy_snapshot";
        lastLoadedAt = now().toISOString();
        status = "ready";
        lastError = null;
        return {
          snapshot: legacy.state,
          recovered: true,
          recoveredFrom: "legacy_snapshot_migration",
          quarantined: null,
        };
      }

      status = chainValid ? "ready" : "degraded";
      lastError = chainValid ? null : "evidence_chain_invalid";
      return {
        snapshot: null,
        recovered: false,
        recoveredFrom: null,
        quarantined: null,
      };
    } catch (error) {
      status = "error";
      lastError = error instanceof Error ? error.message : String(error);
      return {
        snapshot: null,
        recovered: false,
        recoveredFrom: null,
        quarantined: error?.quarantine || null,
      };
    }
  }

  function schedule(snapshot, reason = "state_change") {
    pendingSnapshot = snapshot;
    pendingReason = cleanReason(reason);
    if (pendingTimer) return;
    pendingTimer = setTimeout(() => {
      pendingTimer = null;
      const state = pendingSnapshot;
      const why = pendingReason;
      pendingSnapshot = null;
      pendingReason = null;
      void save(state, why);
    }, debounceMs);
    pendingTimer.unref?.();
  }

  async function save(state, reason = "state_change") {
    if (!isObject(state)) return false;
    const requestedHash = sha256(canonicalJson(state));
    if (requestedHash === lastMaterializedHash) {
      lastSaveReason = cleanReason(reason);
      return true;
    }
    return enqueue(async () => {
      try {
        await mkdir(directory, { recursive: true, mode: 0o700 });
        const checkpoint = await appendRecordUnlocked({
          type: "continuity.state_checkpoint",
          source: "agent-core.materializer",
          correlationId: "state:" + requestedHash,
          payload: {
            reason: cleanReason(reason),
            state_hash: requestedHash,
            state,
          },
        });
        await writeMaterializedUnlocked(state, reason, checkpoint);
        status = chainValid ? "ready" : "degraded";
        lastError = chainValid ? null : "evidence_chain_invalid";
        return true;
      } catch (error) {
        status = "error";
        lastError = error instanceof Error ? error.message : String(error);
        return false;
      }
    });
  }

  async function appendEvent(event) {
    return enqueue(async () => {
      try {
        const record = await appendRecordUnlocked(event);
        if (status !== "degraded") status = "ready";
        lastError = null;
        return record;
      } catch (error) {
        status = "error";
        lastError = error instanceof Error ? error.message : String(error);
        return null;
      }
    });
  }

  async function flush(state = null, reason = "flush") {
    if (pendingTimer) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    const finalState = state ?? pendingSnapshot;
    pendingSnapshot = null;
    pendingReason = null;
    if (finalState) await save(finalState, reason);
    await ioChain;
  }

  async function readEvents({ limit = 100, eventType = null } = {}) {
    const safeLimit = Math.max(1, Math.min(Number(limit) || 100, 500));
    let raw = "";
    try {
      raw = await readFile(evidencePath, "utf8");
    } catch (error) {
      if (error?.code === "ENOENT") return [];
      throw error;
    }
    const records = [];
    for (const line of raw.split("\n")) {
      if (!line.trim()) continue;
      try {
        const record = validateEvidenceRecord(JSON.parse(line));
        if (!eventType || record.event_type === eventType) records.push(record);
      } catch {}
    }
    return records.slice(-safeLimit);
  }

  async function verify() {
    try {
      const scanned = await scanLedger();
      return {
        ok: scanned.chainValid,
        eventCount: scanned.count,
        headHash: scanned.headHash,
        latestCheckpoint: scanned.checkpoint
          ? {
              eventId: scanned.checkpoint.eventId,
              recordedAt: scanned.checkpoint.recordedAt,
              stateHash: scanned.checkpoint.stateHash,
            }
          : null,
      };
    } catch (error) {
      return {
        ok: false,
        eventCount,
        headHash: ledgerHeadHash,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  async function summary() {
    let materializedBytes = null;
    let evidenceBytes = null;
    let legacySnapshotBytes = null;
    let legacyEventBytes = null;
    try { materializedBytes = (await stat(materializedPath)).size; } catch {}
    try { evidenceBytes = (await stat(evidencePath)).size; } catch {}
    try { legacySnapshotBytes = (await stat(legacySnapshotPath)).size; } catch {}
    try { legacyEventBytes = (await stat(legacyEventPath)).size; } catch {}
    return {
      status,
      architecture: "evidence-ledger-v1",
      directory,
      materializedPath,
      evidencePath,
      lastError,
      lastLoadedAt,
      lastSavedAt,
      lastSaveReason,
      saveCount,
      eventCount,
      ledgerHeadHash,
      chainValid,
      lastEvidenceAt,
      lastMaterializedHash,
      migrationSource,
      materializedBytes,
      evidenceBytes,
      legacy: {
        snapshotPath: legacySnapshotPath,
        eventPath: legacyEventPath,
        snapshotBytes: legacySnapshotBytes,
        eventBytes: legacyEventBytes,
        policy: "read_only_migration_evidence",
      },
      pending: Boolean(pendingTimer || pendingSnapshot),
    };
  }

  return {
    init,
    schedule,
    save,
    appendEvent,
    flush,
    readEvents,
    verify,
    summary,
  };
}
