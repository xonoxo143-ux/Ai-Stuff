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

const SNAPSHOT_SCHEMA = 1;

function cleanReason(value) {
  return String(value || "unspecified").replace(/[^a-z0-9._-]/gi, "_").slice(0, 80);
}

export function createDurableState({
  directory,
  now = () => new Date(),
  debounceMs = 250,
} = {}) {
  if (!directory) throw new Error("durable_state_directory_required");

  const snapshotPath = path.join(directory, "agent-state-v1.json");
  const eventPath = path.join(directory, "events-v1.jsonl");
  let status = "not_initialized";
  let lastError = null;
  let lastLoadedAt = null;
  let lastSavedAt = null;
  let lastSaveReason = null;
  let saveCount = 0;
  let eventCount = 0;
  let pendingTimer = null;
  let pendingSnapshot = null;
  let pendingReason = null;
  let ioChain = Promise.resolve();

  function enqueue(operation) {
    ioChain = ioChain.then(operation, operation);
    return ioChain;
  }

  async function init() {
    status = "initializing";
    try {
      await mkdir(directory, { recursive: true, mode: 0o700 });
      let snapshot = null;
      try {
        const raw = await readFile(snapshotPath, "utf8");
        const parsed = JSON.parse(raw);
        if (parsed?.schema !== SNAPSHOT_SCHEMA || typeof parsed?.state !== "object") {
          throw new Error("unsupported_or_invalid_snapshot");
        }
        snapshot = parsed.state;
        lastLoadedAt = now().toISOString();
      } catch (error) {
        if (error?.code !== "ENOENT") {
          const quarantine = `${snapshotPath}.corrupt-${Date.now()}`;
          await copyFile(snapshotPath, quarantine).catch(() => {});
          lastError = `snapshot_load_failed:${error instanceof Error ? error.message : String(error)}`;
          status = "degraded";
          return { snapshot: null, recovered: false, quarantined: quarantine };
        }
      }
      status = "ready";
      lastError = null;
      return { snapshot, recovered: Boolean(snapshot), quarantined: null };
    } catch (error) {
      status = "error";
      lastError = error instanceof Error ? error.message : String(error);
      return { snapshot: null, recovered: false, quarantined: null };
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
    const capturedAt = now().toISOString();
    return enqueue(async () => {
      try {
        await mkdir(directory, { recursive: true, mode: 0o700 });
        const tempPath = `${snapshotPath}.tmp-${process.pid}-${Date.now()}`;
        const envelope = {
          schema: SNAPSHOT_SCHEMA,
          capturedAt,
          reason: cleanReason(reason),
          state,
        };
        await writeFile(tempPath, `${JSON.stringify(envelope)}\n`, { mode: 0o600 });
        await rename(tempPath, snapshotPath);
        status = "ready";
        lastError = null;
        lastSavedAt = capturedAt;
        lastSaveReason = envelope.reason;
        saveCount += 1;
        return true;
      } catch (error) {
        status = "error";
        lastError = error instanceof Error ? error.message : String(error);
        return false;
      }
    });
  }

  async function appendEvent(event) {
    const record = {
      schema: SNAPSHOT_SCHEMA,
      recordedAt: now().toISOString(),
      ...event,
    };
    return enqueue(async () => {
      try {
        await mkdir(directory, { recursive: true, mode: 0o700 });
        await appendFile(eventPath, `${JSON.stringify(record)}\n`, { mode: 0o600 });
        eventCount += 1;
        if (status !== "degraded") status = "ready";
        return true;
      } catch (error) {
        status = "error";
        lastError = error instanceof Error ? error.message : String(error);
        return false;
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

  async function summary() {
    let snapshotBytes = null;
    let eventBytes = null;
    try { snapshotBytes = (await stat(snapshotPath)).size; } catch {}
    try { eventBytes = (await stat(eventPath)).size; } catch {}
    return {
      status,
      directory,
      snapshotPath,
      eventPath,
      lastError,
      lastLoadedAt,
      lastSavedAt,
      lastSaveReason,
      saveCount,
      eventCount,
      snapshotBytes,
      eventBytes,
      pending: Boolean(pendingTimer || pendingSnapshot),
    };
  }

  return { init, schedule, save, appendEvent, flush, summary };
}
