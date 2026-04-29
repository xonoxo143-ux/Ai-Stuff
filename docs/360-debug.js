import { pipeline, env } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.3";

const SMOLLM2_135M = "HuggingFaceTB/SmolLM2-135M-Instruct";
const SMOLLM2_360M = "HuggingFaceTB/SmolLM2-360M-Instruct";
const SMOLLM2_360M_ONNX = "onnx-community/SmolLM2-360M-ONNX";

let generator = null;
let currentConfig = null;
const logLines = [];

const el = {
  status: document.querySelector("#globalStatus"),
  model: document.querySelector("#modelSelect"),
  device: document.querySelector("#deviceSelect"),
  dtype: document.querySelector("#dtypeSelect"),
  inputMode: document.querySelector("#inputModeSelect"),
  returnFullText: document.querySelector("#returnFullTextSelect"),
  maxTokens: document.querySelector("#maxTokensInput"),
  temperature: document.querySelector("#temperatureInput"),
  prompt: document.querySelector("#promptInput"),
  log: document.querySelector("#logBox"),
  output: document.querySelector("#outputBox"),
  raw: document.querySelector("#rawBox"),
  load: document.querySelector("#loadBtn"),
  run: document.querySelector("#runBtn"),
  copy: document.querySelector("#copyBtn"),
  clear: document.querySelector("#clearBtn"),
};

function setStatus(text, mode = "idle") {
  el.status.textContent = `Status: ${text}`;
  el.status.dataset.state = mode;
}

function log(text) {
  const stamp = new Date().toLocaleTimeString();
  logLines.push(`[${stamp}] ${text}`);
  el.log.textContent = logLines.slice(-80).join("\n") + "\n";
  el.log.scrollTop = el.log.scrollHeight;
}

function is360Model() {
  return el.model.value === SMOLLM2_360M || el.model.value === SMOLLM2_360M_ONNX;
}

function is135Model() {
  return el.model.value === SMOLLM2_135M;
}

function applyModelDefaults({ announce = true } = {}) {
  generator = null;
  currentConfig = null;

  if (is360Model()) {
    el.device.value = "wasm";
    el.dtype.value = "q8";
    el.inputMode.value = "chat";
    el.returnFullText.value = "false";
    el.maxTokens.value = "64";
    el.temperature.value = "0";
    if (announce) log("Applied 360M debug defaults: WASM/q8, chat, 64 tokens, temperature 0.");
    return;
  }

  if (is135Model()) {
    el.device.value = "webgpu";
    el.dtype.value = "q4";
    el.inputMode.value = "chat";
    el.returnFullText.value = "false";
    el.maxTokens.value = "64";
    el.temperature.value = "0.2";
    if (announce) log("Applied 135M debug defaults: WebGPU/q4, chat, 64 tokens, temperature 0.2.");
  }
}

function isUnsafePhoneConfig() {
  return is360Model() && ["omit", "fp16", "fp32"].includes(el.dtype.value);
}

function guardUnsafeConfig() {
  if (!isUnsafePhoneConfig()) return true;
  const ok = confirm("This 360M dtype can crash a phone browser. Use q8/WASM unless you intentionally want to risk a crash. Continue anyway?");
  if (!ok) {
    el.device.value = "wasm";
    el.dtype.value = "q8";
    log("Unsafe dtype cancelled. Switched back to WASM/q8.");
    return false;
  }
  log("Unsafe dtype confirmed by user.");
  return true;
}

function configKey() {
  return JSON.stringify({
    model: el.model.value,
    device: el.device.value,
    dtype: el.dtype.value,
  });
}

function pipelineOptions() {
  const options = {
    device: el.device.value,
    progress_callback: (progress) => {
      if (!progress?.status) return;
      const file = progress.file ? ` · ${progress.file.split("/").pop()}` : "";
      const pct = typeof progress.progress === "number" ? ` · ${Math.round(progress.progress)}%` : "";
      if (["ready", "done", "progress"].includes(progress.status)) {
        log(`load ${progress.status}${file}${pct}`);
      }
    },
  };
  if (el.dtype.value !== "omit") options.dtype = el.dtype.value;
  return options;
}

function buildInput() {
  const prompt = el.prompt.value.trim();
  if (el.inputMode.value === "chat") {
    return [
      { role: "system", content: "You are a concise coding assistant. Answer only the requested task." },
      { role: "user", content: prompt },
    ];
  }
  return `Task: ${prompt}\nAnswer:`;
}

function extractText(result, input) {
  if (Array.isArray(result) && result[0]) {
    const item = result[0];
    if (Array.isArray(item.generated_text)) {
      const assistantMessages = item.generated_text.filter((part) => part?.role === "assistant");
      if (assistantMessages.length) {
        return assistantMessages.map((part) => part.content ?? "").join("\n").trim();
      }
      return item.generated_text.map((part) => part.content ?? JSON.stringify(part)).join("\n").trim();
    }
    if (typeof item.generated_text === "string") {
      let text = item.generated_text;
      if (typeof input === "string" && text.startsWith(input)) {
        text = text.slice(input.length);
      }
      return text.trim();
    }
    return JSON.stringify(item, null, 2);
  }
  return String(result ?? "").trim();
}

async function loadPipeline() {
  if (!guardUnsafeConfig()) return;
  setStatus("Loading", "loading");
  el.output.textContent = "";
  el.raw.textContent = "";
  const options = pipelineOptions();
  currentConfig = configKey();
  log(`Loading ${el.model.value}`);
  log(`Options: ${JSON.stringify({ device: options.device, dtype: options.dtype ?? "omitted" })}`);

  try {
    env.allowLocalModels = false;
    env.useBrowserCache = true;
    generator = await pipeline("text-generation", el.model.value, options);
    setStatus("Ready", "ready");
    log("Pipeline ready.");
  } catch (error) {
    generator = null;
    setStatus("Error", "error");
    log(`Load failed: ${error.message}`);
    el.raw.textContent = error.stack || String(error);
  }
}

async function runOnce() {
  if (!generator || currentConfig !== configKey()) {
    await loadPipeline();
    if (!generator) return;
  }

  const input = buildInput();
  const max_new_tokens = Number(el.maxTokens.value || 64);
  const temperature = Number(el.temperature.value || 0);
  const do_sample = temperature > 0;
  const return_full_text = el.returnFullText.value === "true";

  setStatus("Generating", "generating");
  el.output.textContent = "";
  el.raw.textContent = "";
  log(`Run inputMode=${el.inputMode.value}, return_full_text=${return_full_text}, max_new_tokens=${max_new_tokens}, temperature=${temperature}`);

  const started = performance.now();
  try {
    const result = await generator(input, {
      max_new_tokens,
      temperature,
      do_sample,
      return_full_text,
    });
    const ms = Math.round(performance.now() - started);
    const text = extractText(result, input);
    el.output.textContent = text || "[EMPTY TEXT]";
    el.raw.textContent = JSON.stringify(result, null, 2);
    setStatus("Ready", "ready");
    log(`Generation finished in ${(ms / 1000).toFixed(1)}s. Output chars: ${text.length}`);
  } catch (error) {
    setStatus("Error", "error");
    log(`Generation failed: ${error.message}`);
    el.raw.textContent = error.stack || String(error);
  }
}

async function copyReport() {
  const report = [
    "# 360M Diagnostic Report",
    "",
    `Model: ${el.model.value}`,
    `Device: ${el.device.value}`,
    `Dtype: ${el.dtype.value}`,
    `Input mode: ${el.inputMode.value}`,
    `Return full text: ${el.returnFullText.value}`,
    `Max new tokens: ${el.maxTokens.value}`,
    `Temperature: ${el.temperature.value}`,
    "",
    "## Prompt",
    "```text",
    el.prompt.value,
    "```",
    "",
    "## Output",
    "```text",
    el.output.textContent,
    "```",
    "",
    "## Raw",
    "```json",
    el.raw.textContent,
    "```",
    "",
    "## Log",
    "```text",
    el.log.textContent,
    "```",
  ].join("\n");

  try {
    await navigator.clipboard.writeText(report);
    log("Diagnostic report copied.");
  } catch {
    log("Clipboard copy failed; select the report fields manually.");
  }
}

function clearAll() {
  generator = null;
  currentConfig = null;
  logLines.length = 0;
  el.log.textContent = "";
  el.output.textContent = "";
  el.raw.textContent = "";
  setStatus("Idle", "idle");
  applyModelDefaults({ announce: false });
}

el.model.addEventListener("change", () => applyModelDefaults());
el.load.addEventListener("click", loadPipeline);
el.run.addEventListener("click", runOnce);
el.copy.addEventListener("click", copyReport);
el.clear.addEventListener("click", clearAll);

setStatus("Idle", "idle");
applyModelDefaults({ announce: false });
log("Diagnostic page loaded. Model-aware defaults are active.");
