const REVIEW_REPO = "xonoxo143-ux/Ai-Stuff";
const BUILT_IN_PROMPT_LIMIT = 5;

function qs(selector) {
  return document.querySelector(selector);
}

function statusText() {
  return qs("#globalStatus")?.textContent || "";
}

function appendReviewLog(message) {
  const box = qs("#statusLog");
  if (!box) return;
  const stamp = new Date().toLocaleTimeString();
  const lines = box.textContent.split("\n").filter(Boolean);
  lines.push(`[${stamp}] ${message}`);
  box.textContent = lines.slice(-60).join("\n") + "\n";
  box.scrollTop = box.scrollHeight;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(predicate, timeoutMs = 120000, intervalMs = 500) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (predicate()) return true;
    await wait(intervalMs);
  }
  return false;
}

function usablePromptOptions() {
  const select = qs("#promptSelect");
  if (!select) return [];
  return Array.from(select.options)
    .filter((option) => option.value !== "custom")
    .slice(0, BUILT_IN_PROMPT_LIMIT);
}

function clearSessionLogForBatch() {
  const cards = document.querySelectorAll(".result-card");
  if (!cards.length) return;
  qs("#clearLogBtn")?.click();
  appendReviewLog("Cleared existing session log before batch to avoid duplicate review rows.");
}

async function ensureModelReady() {
  if (/Ready/i.test(statusText())) return true;
  appendReviewLog("Batch runner is loading the selected model first.");
  qs("#loadModelBtn")?.click();
  return waitFor(() => /Ready/i.test(statusText()) || /Error/i.test(statusText()), 180000, 750);
}

async function runOnePrompt(option) {
  const select = qs("#promptSelect");
  const runButton = qs("#runPromptBtn");
  const saveButton = qs("#saveResultBtn");
  const outputBox = qs("#outputBox");
  if (!select || !runButton || !saveButton || !outputBox) return false;

  select.value = option.value;
  select.dispatchEvent(new Event("change"));
  outputBox.textContent = "";
  appendReviewLog(`Batch running: ${option.textContent}`);
  runButton.click();

  await waitFor(() => /Generating/i.test(statusText()) || /Error/i.test(statusText()), 60000, 500);
  const finished = await waitFor(() => /Ready/i.test(statusText()) || /Error/i.test(statusText()), 180000, 750);
  if (!finished || /Error/i.test(statusText())) {
    appendReviewLog(`Batch stopped on: ${option.textContent}`);
    return false;
  }

  await wait(400);
  saveButton.click();
  return true;
}

async function runPromptBatch() {
  const options = usablePromptOptions();
  if (!options.length) {
    appendReviewLog("No built-in prompts available for batch run.");
    return;
  }

  const ready = await ensureModelReady();
  if (!ready || /Error/i.test(statusText())) {
    appendReviewLog("Batch runner could not start because the model is not ready.");
    return;
  }

  clearSessionLogForBatch();
  appendReviewLog(`Starting batch: ${options.length} prompts.`);
  for (const option of options) {
    const ok = await runOnePrompt(option);
    if (!ok) break;
    await wait(500);
  }
  appendReviewLog("Batch run finished. Use the GitHub review buttons to send results for rating.");
}

function collectResultsFromDom() {
  const cards = Array.from(document.querySelectorAll(".result-card"));
  return cards.map((card, index) => {
    const title = card.querySelector("h3")?.textContent?.trim() || `${index + 1}. Untitled`;
    const meta = card.querySelector("p")?.textContent?.trim() || "No metadata";
    const blocks = Array.from(card.querySelectorAll("pre")).map((pre) => pre.textContent || "");
    return {
      title,
      meta,
      prompt: blocks[0] || "",
      output: blocks[1] || "",
    };
  });
}

function buildReviewPacket() {
  const results = collectResultsFromDom();
  const model = qs("#modelSelect")?.value || "unknown";
  const runtime = qs("#runtimeSelect")?.value || "unknown";
  const support = [
    `Browser: ${qs("#browserValue")?.textContent || "unknown"}`,
    `WebGPU: ${qs("#webgpuValue")?.textContent || "unknown"}`,
    `WASM: ${qs("#wasmValue")?.textContent || "unknown"}`,
    `Backend: ${qs("#backendValue")?.textContent || "unknown"}`,
  ].join("\n");

  if (!results.length) {
    return "# Coding AI Review Request\n\nNo saved results are in the page log yet. Run prompts and tap `Save Result to Page Log` first.\n";
  }

  return [
    "# Coding AI Review Request",
    "",
    "Assistant task: rate each model answer as Bad / Okay / Good, identify concrete coding errors, and recommend the next model/prompt/settings change.",
    "",
    "## Run metadata",
    "",
    `- Page: https://xonoxo143-ux.github.io/Ai-Stuff/`,
    `- Repo branch: ${REVIEW_REPO} / CODING-AI`,
    `- Selected model field: ${model}`,
    `- Runtime field: ${runtime}`,
    "",
    "```text",
    support,
    "```",
    "",
    "## Results",
    "",
    ...results.map((entry, index) => [
      `### ${index + 1}. ${entry.title}`,
      "",
      `Metadata: ${entry.meta}`,
      "",
      "#### Prompt",
      "```text",
      entry.prompt,
      "```",
      "",
      "#### Output",
      "```text",
      entry.output,
      "```",
      "",
      "#### Review",
      "- Rating: ",
      "- Problems: ",
      "- Keep/change: ",
      "",
    ].join("\n")),
  ].join("\n");
}

async function copyReviewPacket() {
  const packet = buildReviewPacket();
  try {
    await navigator.clipboard.writeText(packet);
    appendReviewLog("Review packet copied.");
  } catch {
    appendReviewLog("Clipboard copy failed. Use Export Results Markdown instead.");
  }
}

function openGitHubReviewIssue() {
  const packet = buildReviewPacket();
  const title = `Coding AI review request - ${new Date().toISOString().slice(0, 10)}`;
  const base = `https://github.com/${REVIEW_REPO}/issues/new`;
  const url = `${base}?title=${encodeURIComponent(title)}&body=${encodeURIComponent(packet)}`;

  if (url.length > 7800) {
    navigator.clipboard?.writeText(packet).catch(() => {});
    appendReviewLog("Review packet was too large for a prefilled issue URL. Copied packet and opening a blank issue instead.");
    window.open(`${base}?title=${encodeURIComponent(title)}`, "_blank", "noopener,noreferrer");
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
  appendReviewLog("Opened prefilled GitHub review issue.");
}

function injectReviewControls() {
  const sessionPanel = qs("#sessionLog")?.closest("section");
  const promptPanel = qs("#promptSelect")?.closest("section");
  if (!sessionPanel || qs("#runBatchBtn")) return;

  const batchRow = document.createElement("div");
  batchRow.className = "button-row";
  batchRow.innerHTML = `
    <button id="runBatchBtn" type="button">Run Built-in Batch</button>
    <button id="copyReviewPacketBtn" type="button" class="secondary">Copy Review Packet</button>
    <button id="openReviewIssueBtn" type="button" class="secondary">Open GitHub Review Issue</button>
  `;

  if (promptPanel) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Batch mode clears the session log, runs the built-in prompts one at a time, and saves each output for review.";
    promptPanel.appendChild(note);
    promptPanel.appendChild(batchRow);
  } else {
    sessionPanel.appendChild(batchRow);
  }

  qs("#runBatchBtn")?.addEventListener("click", runPromptBatch);
  qs("#copyReviewPacketBtn")?.addEventListener("click", copyReviewPacket);
  qs("#openReviewIssueBtn")?.addEventListener("click", openGitHubReviewIssue);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", injectReviewControls);
} else {
  injectReviewControls();
}
