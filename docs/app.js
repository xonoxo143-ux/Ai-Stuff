import { pipeline, env, TextStreamer, InterruptableStoppingCriteria } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.3";

const MAX_LOG_LINES = 60;
const PROGRESS_LOG_INTERVAL_MS = 2000;

const state = {
  generator: null,
  modelId: null,
  backend: "auto",
  prompts: [],
  lastRun: null,
  results: [],
  stoppingCriteria: null,
  logLines: [],
  progress: {
    files: new Set(),
    lastLogAt: 0,
    lastMessage: "",
  },
};

const el = {
  globalStatus: document.querySelector("#globalStatus"),
  browserValue: document.querySelector("#browserValue"),
  webgpuValue: document.querySelector("#webgpuValue"),
  wasmValue: document.querySelector("#wasmValue"),
  backendValue: document.querySelector("#backendValue"),
  statusLog: document.querySelector("#statusLog"),
  modelSelect: document.querySelector("#modelSelect"),
  customModelInput: document.querySelector("#customModelInput"),
  runtimeSelect: document.querySelector("#runtimeSelect"),
  maxTokensInput: document.querySelector("#maxTokensInput"),
  temperatureInput: document.querySelector("#temperatureInput"),
  topPInput: document.querySelector("#topPInput"),
  systemPromptInput: document.querySelector("#systemPromptInput"),
  promptSelect: document.querySelector("#promptSelect"),
  promptInput: document.querySelector("#promptInput"),
  outputBox: document.querySelector("#outputBox"),
  resultMeta: document.querySelector("#resultMeta"),
  sessionLog: document.querySelector("#sessionLog"),
  checkSupportBtn: document.querySelector("#checkSupportBtn"),
  clearStatusBtn: document.querySelector("#clearStatusBtn"),
  loadModelBtn: document.querySelector("#loadModelBtn"),
  unloadModelBtn: document.querySelector("#unloadModelBtn"),
  resetPageBtn: document.querySelector("#resetPageBtn"),
  runPromptBtn: document.querySelector("#runPromptBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  clearPromptBtn: document.querySelector("#clearPromptBtn"),
  copyPromptBtn: document.querySelector("#copyPromptBtn"),
  copyOutputBtn: document.querySelector("#copyOutputBtn"),
  saveResultBtn: document.querySelector("#saveResultBtn"),
  clearOutputBtn: document.querySelector("#clearOutputBtn"),
  exportJsonBtn: document.querySelector("#exportJsonBtn"),
  exportMarkdownBtn: document.querySelector("#exportMarkdownBtn"),
  copyAllBtn: document.querySelector("#copyAllBtn"),
  clearLogBtn: document.querySelector("#clearLogBtn"),
};

function setStatus(message, mode = "idle") {
  el.globalStatus.textContent = `Status: ${message}`;
  el.globalStatus.dataset.state = mode;
}

function renderStatusLog() {
  el.statusLog.textContent = state.logLines.join("\n");
  if (el.statusLog.textContent) el.statusLog.textContent += "\n";
  el.statusLog.scrollTop = el.statusLog.scrollHeight;
}

function logStatus(message) {
  const stamp = new Date().toLocaleTimeString();
  state.logLines.push(`[${stamp}] ${message}`);
  if (state.logLines.length > MAX_LOG_LINES) {
    state.logLines = state.logLines.slice(-MAX_LOG_LINES);
  }
  renderStatusLog();
}

function resetProgressSummary() {
  state.progress = {
    files: new Set(),
    lastLogAt: 0,
    lastMessage: "",
  };
}

function shortFileName(file) {
  if (!file) return "";
  const pieces = String(file).split("/");
  const name = pieces[pieces.length - 1] || file;
  return name.length > 46 ? `${name.slice(0, 20)}…${name.slice(-20)}` : name;
}

function handleModelProgress(progress) {
  if (!progress || !progress.status) return;
  if (progress.file) state.progress.files.add(progress.file);

  const now = Date.now();
  const pct = typeof progress.progress === "number" && Number.isFinite(progress.progress)
    ? ` · ${Math.round(progress.progress)}%`
    : "";
  const file = shortFileName(progress.file);
  const filePart = file ? ` · ${file}` : "";
  const message = `Loading model · ${state.progress.files.size} files seen · ${progress.status}${filePart}${pct}`;

  if (message === state.progress.lastMessage) return;
  if (now - state.progress.lastLogAt < PROGRESS_LOG_INTERVAL_MS && progress.status !== "ready") return;

  state.progress.lastMessage = message;
  state.progress.lastLogAt = now;
  logStatus(message);
}

function getSelectedModelId() {
  if (el.modelSelect.value === "custom") {
    return el.customModelInput.value.trim();
  }
  return el.modelSelect.value;
}

function getRating() {
  const checked = document.querySelector('input[name="rating"]:checked');
  return checked ? checked.value : "Unrated";
}

function clearRating() {
  document.querySelectorAll('input[name="rating"]').forEach((input) => {
    input.checked = false;
  });
}

function browserName() {
  const ua = navigator.userAgent;
  if (ua.includes("Edg/")) return "Edge";
  if (ua.includes("SamsungBrowser")) return "Samsung Internet";
  if (ua.includes("Chrome")) return "Chrome/Chromium";
  if (ua.includes("Firefox")) return "Firefox";
  if (ua.includes("Safari")) return "Safari";
  return "Unknown browser";
}

function checkSupport() {
  const hasWebGpu = Boolean(navigator.gpu);
  el.browserValue.textContent = browserName();
  el.webgpuValue.textContent = hasWebGpu ? "Available" : "Not available";
  el.wasmValue.textContent = typeof WebAssembly === "object" ? "Available" : "Not available";
  const selected = el.runtimeSelect.value;
  el.backendValue.textContent = selected === "auto" ? (hasWebGpu ? "Auto → WebGPU" : "Auto → WASM") : selected.toUpperCase();
  logStatus(hasWebGpu ? "WebGPU is available." : "WebGPU is not available. WASM fallback will be used.");
}

async function loadPrompts() {
  const response = await fetch("./prompts/smoke_coding_prompts.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Prompt file failed to load: HTTP ${response.status}`);
  state.prompts = await response.json();
  el.promptSelect.innerHTML = "";
  for (const item of state.prompts) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.title;
    el.promptSelect.appendChild(option);
  }
  const first = state.prompts[0];
  if (first) el.promptInput.value = first.prompt;
}

function selectedDevice() {
  const runtime = el.runtimeSelect.value;
  if (runtime === "webgpu") return "webgpu";
  if (runtime === "wasm") return "wasm";
  return navigator.gpu ? "webgpu" : "wasm";
}

function buildMessages(prompt) {
  return [
    { role: "system", content: el.systemPromptInput.value.trim() || "You are a concise coding assistant." },
    { role: "user", content: prompt },
  ];
}

async function loadModel() {
  const modelId = getSelectedModelId();
  if (!modelId) {
    setStatus("Missing model ID", "error");
    logStatus("Choose a model or enter a custom model ID.");
    return;
  }

  const device = selectedDevice();
  setStatus("Loading", "loading");
  resetProgressSummary();
  logStatus(`Loading ${modelId} on ${device}. First load may take a while.`);

  try {
    state.generator = null;
    state.stoppingCriteria = null;
    env.allowLocalModels = false;
    env.useBrowserCache = true;

    state.generator = await pipeline("text-generation", modelId, {
      device,
      dtype: device === "webgpu" ? "q4" : "q8",
      progress_callback: handleModelProgress,
    });

    state.modelId = modelId;
    state.backend = device;
    el.backendValue.textContent = device.toUpperCase();
    setStatus("Ready", "ready");
    logStatus(`Model ready. Loaded ${state.progress.files.size} files.`);
  } catch (error) {
    state.generator = null;
    setStatus("Error", "error");
    logStatus(`Model failed to load: ${error.message}`);
    if (device === "webgpu") {
      logStatus("Try Runtime → WASM, or use the 135M model first.");
    }
  }
}

function unloadModel() {
  state.generator = null;
  state.modelId = null;
  state.stoppingCriteria = null;
  setStatus("Not loaded", "idle");
  logStatus("Model unloaded from page state. Browser memory may fully clear after refresh.");
}

function extractGeneratedText(result) {
  if (Array.isArray(result) && result[0]) {
    const item = result[0];
    if (Array.isArray(item.generated_text)) {
      return item.generated_text.at(-1)?.content ?? JSON.stringify(item.generated_text, null, 2);
    }
    return item.generated_text ?? JSON.stringify(item, null, 2);
  }
  return String(result ?? "");
}

async function runPrompt() {
  const prompt = el.promptInput.value.trim();
  if (!prompt) {
    logStatus("Prompt is empty.");
    return;
  }
  if (!state.generator) {
    logStatus("No model is loaded yet. Loading selected model first.");
    await loadModel();
    if (!state.generator) return;
  }

  const maxNewTokens = Number(el.maxTokensInput.value || 256);
  const temperature = Number(el.temperatureInput.value || 0.2);
  const topP = Number(el.topPInput.value || 0.9);
  const promptItem = state.prompts.find((item) => item.id === el.promptSelect.value);
  const startTime = Date.now();
  let streamedText = "";

  setStatus("Generating", "generating");
  el.outputBox.textContent = "";
  clearRating();
  state.stoppingCriteria = new InterruptableStoppingCriteria();

  try {
    const streamer = new TextStreamer(state.generator.tokenizer, {
      skip_prompt: true,
      skip_special_tokens: true,
      callback_function: (text) => {
        streamedText += text;
        el.outputBox.textContent = streamedText;
        el.outputBox.scrollTop = el.outputBox.scrollHeight;
      },
    });

    const result = await state.generator(buildMessages(prompt), {
      max_new_tokens: maxNewTokens,
      temperature,
      top_p: topP,
      do_sample: temperature > 0,
      streamer,
      stopping_criteria: state.stoppingCriteria,
    });

    const finalText = streamedText.trim() || extractGeneratedText(result).trim();
    const durationMs = Date.now() - startTime;
    el.outputBox.textContent = finalText;
    el.resultMeta.textContent = `${state.modelId} · ${state.backend.toUpperCase()} · ${promptItem?.title ?? "Custom"} · ${(durationMs / 1000).toFixed(1)}s`;
    state.lastRun = {
      timestamp: new Date().toISOString(),
      model: state.modelId,
      backend: state.backend,
      promptTitle: promptItem?.title ?? "Custom",
      prompt,
      output: finalText,
      durationMs,
      settings: { maxNewTokens, temperature, topP },
      rating: "Unrated",
    };
    setStatus("Ready", "ready");
    logStatus("Generation complete.");
  } catch (error) {
    setStatus("Error", "error");
    logStatus(`Generation failed: ${error.message}`);
  } finally {
    state.stoppingCriteria = null;
  }
}

function stopGeneration() {
  if (state.stoppingCriteria && typeof state.stoppingCriteria.interrupt === "function") {
    state.stoppingCriteria.interrupt();
    setStatus("Stopping", "loading");
    logStatus("Stop requested.");
  } else {
    logStatus("No active generation to stop.");
  }
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    logStatus(`${label} copied.`);
  } catch {
    logStatus(`Could not copy ${label.toLowerCase()}. Select and copy manually.`);
  }
}

function saveResult() {
  if (!state.lastRun) {
    logStatus("No result to save yet.");
    return;
  }
  const entry = { ...state.lastRun, rating: getRating() };
  state.results.push(entry);
  renderSessionLog();
  logStatus("Result saved to page log.");
}

function renderSessionLog() {
  if (!state.results.length) {
    el.sessionLog.innerHTML = '<p class="muted">No saved results yet.</p>';
    return;
  }
  el.sessionLog.innerHTML = "";
  state.results.forEach((entry, index) => {
    const card = document.createElement("article");
    card.className = "result-card";
    card.innerHTML = `
      <h3>${index + 1}. ${escapeHtml(entry.promptTitle)}</h3>
      <p>${escapeHtml(entry.model)} · ${escapeHtml(entry.backend.toUpperCase())} · ${escapeHtml(entry.rating)} · ${(entry.durationMs / 1000).toFixed(1)}s</p>
      <details>
        <summary>Show prompt/output</summary>
        <pre>${escapeHtml(entry.prompt)}</pre>
        <pre>${escapeHtml(entry.output)}</pre>
      </details>
    `;
    el.sessionLog.appendChild(card);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function resultsAsMarkdown() {
  if (!state.results.length) return "# Coding AI Lab Results\n\nNo saved results.\n";
  return ["# Coding AI Lab Results", "", ...state.results.map((entry, index) => [
    `## ${index + 1}. ${entry.promptTitle}`,
    "",
    `- Model: ${entry.model}`,
    `- Backend: ${entry.backend}`,
    `- Rating: ${entry.rating}`,
    `- Duration: ${(entry.durationMs / 1000).toFixed(1)}s`,
    `- Timestamp: ${entry.timestamp}`,
    "",
    "### Prompt",
    "```text",
    entry.prompt,
    "```",
    "",
    "### Output",
    "```text",
    entry.output,
    "```",
    "",
  ].join("\n"))].join("\n");
}

function downloadText(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function resetPage() {
  if (!confirm("Reset the page state and clear unsaved output?")) return;
  unloadModel();
  state.results = [];
  state.lastRun = null;
  state.logLines = [];
  el.outputBox.textContent = "";
  el.resultMeta.textContent = "No run yet.";
  renderStatusLog();
  renderSessionLog();
  checkSupport();
}

el.checkSupportBtn.addEventListener("click", checkSupport);
el.clearStatusBtn.addEventListener("click", () => { state.logLines = []; renderStatusLog(); });
el.modelSelect.addEventListener("change", () => {
  el.customModelInput.classList.toggle("hidden", el.modelSelect.value !== "custom");
});
el.runtimeSelect.addEventListener("change", checkSupport);
el.loadModelBtn.addEventListener("click", loadModel);
el.unloadModelBtn.addEventListener("click", unloadModel);
el.resetPageBtn.addEventListener("click", resetPage);
el.promptSelect.addEventListener("change", () => {
  const item = state.prompts.find((candidate) => candidate.id === el.promptSelect.value);
  if (item && item.id !== "custom") el.promptInput.value = item.prompt;
});
el.runPromptBtn.addEventListener("click", runPrompt);
el.stopBtn.addEventListener("click", stopGeneration);
el.clearPromptBtn.addEventListener("click", () => { el.promptInput.value = ""; });
el.copyPromptBtn.addEventListener("click", () => copyText(el.promptInput.value, "Prompt"));
el.copyOutputBtn.addEventListener("click", () => copyText(el.outputBox.textContent, "Output"));
el.saveResultBtn.addEventListener("click", saveResult);
el.clearOutputBtn.addEventListener("click", () => {
  el.outputBox.textContent = "";
  el.resultMeta.textContent = "No run yet.";
  state.lastRun = null;
});
el.exportJsonBtn.addEventListener("click", () => downloadText("coding-ai-results.json", JSON.stringify(state.results, null, 2), "application/json"));
el.exportMarkdownBtn.addEventListener("click", () => downloadText("coding-ai-results.md", resultsAsMarkdown(), "text/markdown"));
el.copyAllBtn.addEventListener("click", () => copyText(resultsAsMarkdown(), "All results"));
el.clearLogBtn.addEventListener("click", () => {
  if (!confirm("Clear saved session results?")) return;
  state.results = [];
  renderSessionLog();
});

try {
  await loadPrompts();
  renderSessionLog();
  checkSupport();
  setStatus("Not loaded", "idle");
} catch (error) {
  setStatus("Error", "error");
  logStatus(error.message);
}
