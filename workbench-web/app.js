const MODELS = [
  {
    id: "smollm2-360m-instruct-q4km",
    name: "SmolLM2 360M Instruct",
    filename: "SmolLM2-360M-Instruct-Q4_K_M.gguf",
    url: "https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/main/SmolLM2-360M-Instruct-Q4_K_M.gguf?download=true",
    sha256: "2fa3f013dcdd7b99f9b237717fa0b12d75bbb89984cc1274be1471a465bac9c2",
    context: 2048,
    threads: 4,
    maxTokens: 256
  },
  {
    id: "smollm2-1.7b-instruct-q4km",
    name: "SmolLM2 1.7B Instruct",
    filename: "smollm2-1.7b-instruct-q4_k_m.gguf",
    url: "https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF/resolve/main/smollm2-1.7b-instruct-q4_k_m.gguf?download=true",
    sha256: "decd2598bc2c8ed08c19adc3c8fdd461ee19ed5708679d1c54ef54a5a30d4f33",
    context: 4096,
    threads: 4,
    maxTokens: 512
  }
];

const AGENT_BENCHMARK = {
  schema: 1,
  name: "agent-ecology-v0-depth-context",
  description: "Measures recurrent thought depth, routing stability, and context-sensitive recruitment on the first learned Agent ecology.",
  depths: [1, 2, 3, 4, 6],
  programs: [
    { id: "heldout-add-square", events: [
      {op:"SET",arg:1.25},{op:"ADD",arg:0.75},{op:"SQUARE"},{op:"HALF"},{op:"NEG"},{op:"ABS"}
    ]},
    { id: "heldout-abs-sub", events: [
      {op:"SET",arg:-1.5},{op:"ABS"},{op:"SUB",arg:0.5},{op:"MUL",arg:2.0},{op:"NEG"},{op:"ADD",arg:1.0}
    ]},
    { id: "heldout-mul-neg", events: [
      {op:"SET",arg:0.8},{op:"MUL",arg:1.5},{op:"NEG"},{op:"ABS"},{op:"ADD",arg:0.4},{op:"SQUARE"}
    ]},
    { id: "square-half-chain", events: [
      {op:"SET",arg:-2.0},{op:"ADD",arg:0.5},{op:"SQUARE"},{op:"HALF"},{op:"SUB",arg:0.25},{op:"NEG"}
    ]},
    { id: "square-half-context-b", events: [
      {op:"SET",arg:1.2},{op:"SQUARE"},{op:"HALF"},{op:"MUL",arg:-1.0},{op:"ABS"},{op:"SUB",arg:0.3}
    ]},
    { id: "add-square-context-b", events: [
      {op:"SET",arg:-0.75},{op:"NEG"},{op:"ADD",arg:0.5},{op:"SQUARE"},{op:"HALF"},{op:"ABS"}
    ]},
    { id: "mul-neg-context-b", events: [
      {op:"SET",arg:2.0},{op:"MUL",arg:0.5},{op:"NEG"},{op:"ABS"},{op:"SUB",arg:0.25},{op:"ADD",arg:0.75}
    ]},
    { id: "abs-sub-context-b", events: [
      {op:"SET",arg:-0.4},{op:"ABS"},{op:"SUB",arg:0.1},{op:"SQUARE"},{op:"HALF"},{op:"ADD",arg:0.2}
    ]},
    { id: "same-add-different-history", events: [
      {op:"SET",arg:1.1},{op:"NEG"},{op:"ABS"},{op:"ADD",arg:0.3},{op:"HALF"},{op:"ADD",arg:0.3}
    ]},
    { id: "same-neg-different-history", events: [
      {op:"SET",arg:0.6},{op:"SQUARE"},{op:"NEG"},{op:"ABS"},{op:"MUL",arg:1.25},{op:"NEG"}
    ]}
  ]
};

const pending = new Map();
let requestCounter = 0;
let installed = [];
let loadedModel = null;
let history = [];
let activeStream = null;
let lastMetrics = null;
let remoteManifest = null;
let benchCancelled = false;
let lastBenchmark = null;
let lastAgentTest = null;
let githubState = null;
let githubPollTimer = null;

const $ = selector => document.querySelector(selector);

function nativeRequest(type, payload = {}) {
  return new Promise((resolve, reject) => {
    const id = String(++requestCounter);
    pending.set(id, { resolve, reject });
    WorkbenchNative.postMessage(JSON.stringify({ id, type, payload }));
  });
}

window.__nativeEvent = event => {
  if (event.type === "reply") {
    const payload = event.payload;
    const waiter = pending.get(payload.id);
    if (!waiter) return;
    pending.delete(payload.id);
    payload.ok ? waiter.resolve(payload.data) : waiter.reject(new Error(payload.error || "Kernel error"));
    return;
  }

  if (event.type === "token") {
    if (activeStream) activeStream(event.payload.chunk || "");
    return;
  }

  if (event.type === "download_progress") {
    const percent = Number(event.payload.percent || 0);
    $("#download-progress").value = percent;
    $("#model-status").textContent = "Downloading… " + percent.toFixed(1) + "%";
  }
};

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.style.display = "block";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.style.display = "none"; }, 3500);
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach(el => el.classList.toggle("active", el.id === name));
  document.querySelectorAll("#tabs button").forEach(el => el.classList.toggle("active", el.dataset.tab === name));
}

function show(selector, visible) {
  const el = $(selector);
  if (el) el.classList.toggle("hidden", !visible);
}

function selectedModel() {
  return MODELS[$("#model-select").selectedIndex || 0];
}

function generationSettings() {
  return {
    max_tokens: Number($("#max-tokens").value),
    temperature: Number($("#temperature").value),
    top_p: 0.95,
    top_k: 40,
    repeat_penalty: 1.1
  };
}

function buildPrompt(messages, systemText) {
  let output = "<|im_start|>system\n" + systemText.trim() + "<|im_end|>\n";
  for (const message of messages) {
    output += "<|im_start|>" + message.role + "\n" + message.content + "<|im_end|>\n";
  }
  return output + "<|im_start|>assistant\n";
}

function metricText(metrics) {
  if (!metrics) return "No metrics.";
  const evaluated = metrics.evaluated_prompt_tokens ?? metrics.prompt_tokens;
  const prefillRate = metrics.prompt_seconds > 0 ? evaluated / metrics.prompt_seconds : 0;
  return "Prompt " + metrics.prompt_tokens +
    " tok · cached " + (metrics.cached_prompt_tokens || 0) +
    " · evaluated " + evaluated +
    " · prefill " + prefillRate.toFixed(1) + " tok/s" +
    " · TTFT " + Number(metrics.ttft_seconds).toFixed(2) + "s" +
    " · decode " + Number(metrics.tokens_per_second).toFixed(2) + " tok/s" +
    " · total " + Number(metrics.total_seconds).toFixed(2) + "s";
}

function renderMetrics(metrics) {
  if (!metrics) return;
  lastMetrics = metrics;
  $("#metrics").textContent = metricText(metrics);
}

function appendMessage(role, content) {
  const box = document.createElement("div");
  box.className = "message";
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role === "user" ? "You" : "Assistant";
  const body = document.createElement("div");
  body.textContent = content;
  box.append(label, body);
  $("#chat-view").append(box);
  $("#chat-view").scrollTop = $("#chat-view").scrollHeight;
  return body;
}

async function refreshModels() {
  installed = await nativeRequest("models.list");
  const model = selectedModel();
  const available = installed.some(item => item.filename === model.filename);
  $("#download-button").disabled = available;
  $("#load-button").disabled = !available || loadedModel === model.filename;
  $("#delete-button").disabled = !available;
  $("#unload-button").disabled = !loadedModel;
}

async function refreshKernel() {
  const info = await nativeRequest("kernel.info");
  $("#kernel-line").textContent = "kernel " + info.kernel_version + " · workbench " + info.workbench_version;
  $("#runtime-info").textContent = info.runtime;
  await refreshModels();
}

async function loadModelSelection() {
  const model = selectedModel();
  $("#context").value = model.context;
  $("#threads").value = model.threads;
  $("#max-tokens").value = model.maxTokens;
  await refreshModels();
}

async function generate(prompt, onChunk) {
  activeStream = onChunk;
  try {
    const result = await nativeRequest("generation.start", { prompt, ...generationSettings() });
    renderMetrics(result);
    return result;
  } finally {
    activeStream = null;
  }
}

async function sendChat() {
  if (!loadedModel) return toast("Load a model first.");
  const text = $("#chat-input").value.trim();
  if (!text) return;

  history.push({ role: "user", content: text });
  appendMessage("user", text);
  $("#chat-input").value = "";

  const responseBody = appendMessage("assistant", "");
  let response = "";

  try {
    await generate(
      buildPrompt(history, $("#system-prompt").value),
      chunk => {
        response += chunk;
        responseBody.textContent += chunk;
        $("#chat-view").scrollTop = $("#chat-view").scrollHeight;
      }
    );
    history.push({ role: "assistant", content: response });
  } catch (error) {
    responseBody.textContent += "\n[error: " + error.message + "]";
  }
}

async function checkUpdate(showToast = true) {
  try {
    const data = await nativeRequest("update.check");
    remoteManifest = data.manifest;
    const text = data.update_available
      ? "Update available: " + data.local_version + " → " + data.remote_version
      : "Current workbench is up to date (v" + data.local_version + ").";
    $("#update-status").textContent = text;
    $("#update-button").textContent = data.update_available ? "Update available" : "Up to date";
    if (showToast) toast(text);
    return data;
  } catch (error) {
    $("#update-status").textContent = "Update check failed: " + error.message;
    if (showToast) toast(error.message);
    return null;
  }
}

async function applyUpdate() {
  if (!remoteManifest) {
    const check = await checkUpdate(false);
    if (!check || !check.update_available) return;
  }

  try {
    $("#update-status").textContent = "Downloading and verifying workbench…";
    await nativeRequest("update.apply", { manifest: remoteManifest });
    $("#update-status").textContent = "Update installed. Reloading…";
    await nativeRequest("update.reload");
  } catch (error) {
    $("#update-status").textContent = "Update failed: " + error.message;
  }
}

function persistBenchmark(value) {
  lastBenchmark = value;
  try {
    localStorage.setItem("aiworkbench.lastBenchmark", JSON.stringify(value));
  } catch (_) {}
}

function loadSavedBenchmark() {
  try {
    const raw = localStorage.getItem("aiworkbench.lastBenchmark");
    if (!raw) return;
    lastBenchmark = JSON.parse(raw);
    const count = Array.isArray(lastBenchmark.turns) ? lastBenchmark.turns.length : 0;
    $("#bench-status").textContent = "Saved benchmark available · " + count + " turn(s).";
    if (count > 0) {
      const last = lastBenchmark.turns[count - 1];
      if (last.metrics) $("#bench-metrics").textContent = "Saved: " + metricText(last.metrics);
    }
  } catch (_) {
    lastBenchmark = null;
  }
}

function benchmarkSnapshot(suite, turns, complete) {
  return {
    schema: 1,
    type: "benchmark_result",
    suite: suite.id,
    generated_at: new Date().toISOString(),
    complete,
    model: loadedModel,
    turns
  };
}

async function runBenchmark() {
  if (!loadedModel) return toast("Load a model first.");

  benchCancelled = false;
  lastBenchmark = null;
  $("#bench-metrics").textContent = "Waiting for first completed turn…";

  let suite;
  try {
    suite = await fetch("benchmarks/chatbot-v0.json").then(response => {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    });
  } catch (error) {
    $("#bench-status").textContent = "Could not load benchmark: " + error.message;
    return;
  }

  const threads = new Map();
  const turns = [];
  $("#bench-progress").max = suite.turns.length;
  $("#bench-progress").value = 0;

  for (let i = 0; i < suite.turns.length && !benchCancelled; i++) {
    const turn = suite.turns[i];
    const thread = threads.get(turn.thread) || [];
    thread.push({ role: "user", content: turn.prompt });
    threads.set(turn.thread, thread);

    $("#bench-status").textContent = "Turn " + (i + 1) + "/" + suite.turns.length + " · " + turn.category;
    $("#bench-preview").textContent = "Prompt\n" + turn.prompt + "\n\nResponse\n";

    let response = "";
    try {
      const metrics = await generate(
        buildPrompt(thread, suite.system_prompt || "You are a capable local assistant."),
        chunk => {
          response += chunk;
          $("#bench-preview").textContent += chunk;
        }
      );

      thread.push({ role: "assistant", content: response });
      turns.push({ ...turn, response, metrics });
      $("#bench-progress").value = i + 1;
      $("#bench-metrics").textContent = "Turn " + (i + 1) + ": " + metricText(metrics);
      persistBenchmark(benchmarkSnapshot(suite, turns, false));
    } catch (error) {
      turns.push({ ...turn, response, error: error.message });
      persistBenchmark(benchmarkSnapshot(suite, turns, false));
      break;
    }
  }

  const complete = !benchCancelled && turns.length === suite.turns.length;
  persistBenchmark(benchmarkSnapshot(suite, turns, complete));
  $("#bench-status").textContent = complete
    ? "Benchmark complete."
    : "Stopped after " + turns.length + " turn(s).";
}

async function refreshAgent() {
  try {
    const status = await nativeRequest("agent.model.status");
    if (!status.available) {
      $("#agent-status").textContent =
        "This kernel supports Agent v0, but this APK does not contain a learned Agent model.";
      $("#agent-selftest").disabled = true;
      $("#agent-benchmark").disabled = true;
      $("#agent-reset").disabled = true;
      return status;
    }

    $("#agent-selftest").disabled = false;
    $("#agent-benchmark").disabled = false;
    $("#agent-reset").disabled = false;
    if (status.loaded && status.model) {
      const m = status.model;
      $("#agent-status").textContent =
        "Loaded " + m.id + " · " + m.num_cells + " cells · " +
        m.active_cells + " active/thought · state " + m.state_dim +
        " · " + m.thought_steps + " trained thought steps/event";
    } else {
      $("#agent-status").textContent =
        "Learned Agent model is bundled and ready to load.";
    }
    return status;
  } catch (error) {
    $("#agent-status").textContent = "Agent runtime error: " + error.message;
    $("#agent-selftest").disabled = true;
    $("#agent-benchmark").disabled = true;
    $("#agent-reset").disabled = true;
    return null;
  }
}

function formatAgentTrace(result) {
  const lines = [];
  for (const item of result.program || []) {
    lines.push(
      item.event +
      "  expected=" + Number(item.expected).toFixed(4) +
      "  predicted=" + Number(item.predicted).toFixed(4) +
      "  |error|=" + Number(item.absolute_error).toFixed(4)
    );
    (item.thoughts || []).forEach((thought, index) => {
      lines.push(
        "  thought " + (index + 1) +
        "  cells=[" + thought.selected_cells.join(", ") + "]" +
        "  route=[" + thought.route_weights.map(x => Number(x).toFixed(3)).join(", ") + "]" +
        "  " + Number(thought.latency_ms).toFixed(3) + " ms"
      );
    });
  }
  return lines.join("\n");
}

async function runAgentSelfTest() {
  $("#agent-status").textContent = "Running learned Agent on this phone…";
  $("#agent-summary").textContent = "Executing recurrent sparse ecology…";
  $("#agent-trace").textContent = "Running…";
  $("#agent-bench-progress").value = 0;

  try {
    const result = await nativeRequest("agent.model.selfTest");
    lastAgentTest = {
      schema: 1,
      type: "agent_hardware_test",
      generated_at: new Date().toISOString(),
      ...result
    };

    const m = result.model;
    $("#agent-status").textContent =
      "Loaded " + m.id + " · " + m.num_cells + " cells · " +
      m.active_cells + " active/thought";

    $("#agent-summary").textContent =
      "MAE " + Number(result.mae).toFixed(4) +
      " · " + result.total_thoughts + " thoughts" +
      " · mean " + Number(result.mean_thought_latency_ms).toFixed(3) + " ms/thought" +
      " · total " + Number(result.total_latency_ms).toFixed(2) + " ms";

    $("#agent-trace").textContent = formatAgentTrace(result);
  } catch (error) {
    $("#agent-status").textContent = "Agent test failed: " + error.message;
    $("#agent-summary").textContent = "No result.";
    $("#agent-trace").textContent = String(error.stack || error);
  }
}

const AGENT_OPS = {
  SET: 0,
  ADD: 1,
  SUB: 2,
  MUL: 3,
  NEG: 4,
  ABS: 5,
  HALF: 6,
  SQUARE: 7
};

function clampAgentValue(value) {
  return Math.max(-8, Math.min(8, value));
}

function agentExpected(register, event) {
  const arg = Number(event.arg || 0);
  let next = register;
  switch (event.op) {
    case "SET": next = arg; break;
    case "ADD": next = register + arg; break;
    case "SUB": next = register - arg; break;
    case "MUL": next = register * arg; break;
    case "NEG": next = -register; break;
    case "ABS": next = Math.abs(register); break;
    case "HALF": next = register * 0.5; break;
    case "SQUARE": next = register * register; break;
    default: throw new Error("Unknown Agent operation: " + event.op);
  }
  return clampAgentValue(next);
}

function encodeAgentEvent(event) {
  const vector = Array(11).fill(0);
  const opId = AGENT_OPS[event.op];
  if (opId === undefined) throw new Error("Unknown Agent operation: " + event.op);
  vector[opId] = 1;
  if (Object.prototype.hasOwnProperty.call(event, "arg")) {
    vector[8] = Number(event.arg);
    vector[9] = 1;
  }
  vector[10] = 1;
  return vector;
}

function jaccardCells(a, b) {
  const left = new Set(a || []);
  const right = new Set(b || []);
  const union = new Set([...left, ...right]);
  if (!union.size) return 1;
  let intersection = 0;
  for (const value of left) if (right.has(value)) intersection++;
  return intersection / union.size;
}

function average(values) {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function pairwiseAverageJaccard(sets) {
  const values = [];
  for (let i = 0; i < sets.length; i++) {
    for (let j = i + 1; j < sets.length; j++) {
      values.push(jaccardCells(sets[i], sets[j]));
    }
  }
  return average(values);
}

function summarizeAgentDepth(depth, runs, numCells) {
  let errorSum = 0;
  let eventCount = 0;
  let latency = 0;
  let thoughtCount = 0;
  const usedCells = new Set();
  const withinEventOverlaps = [];
  const firstThoughtByOp = new Map();

  for (const run of runs) {
    for (const event of run.events) {
      errorSum += Number(event.absolute_error);
      eventCount++;
      latency += Number(event.total_latency_ms);

      const thoughts = event.thoughts || [];
      thoughtCount += thoughts.length;
      for (const thought of thoughts) {
        for (const cell of thought.selected_cells || []) usedCells.add(cell);
      }

      if (thoughts.length > 1) {
        withinEventOverlaps.push(
          jaccardCells(
            thoughts[0].selected_cells,
            thoughts[thoughts.length - 1].selected_cells
          )
        );
      }

      if (thoughts.length) {
        if (!firstThoughtByOp.has(event.op)) firstThoughtByOp.set(event.op, []);
        firstThoughtByOp.get(event.op).push(thoughts[0].selected_cells || []);
      }
    }
  }

  const contextOverlaps = [];
  for (const sets of firstThoughtByOp.values()) {
    const value = pairwiseAverageJaccard(sets);
    if (value !== null) contextOverlaps.push(value);
  }

  return {
    depth,
    mae: errorSum / Math.max(1, eventCount),
    total_model_latency_ms: latency,
    mean_thought_latency_ms: latency / Math.max(1, thoughtCount),
    event_count: eventCount,
    thought_count: thoughtCount,
    used_cells: usedCells.size,
    total_cells: numCells,
    mean_within_event_first_last_jaccard: average(withinEventOverlaps),
    mean_same_op_cross_context_jaccard: average(contextOverlaps)
  };
}

function renderAgentBenchmarkSummary(result) {
  const lines = result.depth_metrics.map(metric =>
    "depth " + metric.depth +
    " · MAE " + Number(metric.mae).toFixed(4) +
    " · " + Number(metric.mean_thought_latency_ms).toFixed(3) + " ms/thought" +
    " · cells " + metric.used_cells + "/" + metric.total_cells +
    (metric.mean_within_event_first_last_jaccard == null
      ? ""
      : " · recurrent overlap " +
        Number(metric.mean_within_event_first_last_jaccard).toFixed(3)) +
    (metric.mean_same_op_cross_context_jaccard == null
      ? ""
      : " · same-op/context overlap " +
        Number(metric.mean_same_op_cross_context_jaccard).toFixed(3))
  );
  return lines.join("\n");
}

async function runAgentBenchmark() {
  $("#agent-status").textContent = "Starting depth/context benchmark…";
  $("#agent-summary").textContent = "Preparing 50 controlled runs…";
  $("#agent-trace").textContent = "Benchmark started.";

  // Keep this benchmark definition inside the UI bundle. The previous version
  // awaited a WebView fetch before changing visible state, which could hang
  // silently on some devices and made a working click look dead.
  const suite = AGENT_BENCHMARK;

  const status = await refreshAgent();
  if (!status?.available) return;

  const numCells = status.model?.num_cells || 16;
  const totalRuns = suite.depths.length * suite.programs.length;
  $("#agent-bench-progress").max = totalRuns;
  $("#agent-bench-progress").value = 0;
  $("#agent-status").textContent =
    "Running depth/context benchmark on this phone…";
  $("#agent-summary").textContent =
    "Testing recurrence depth without changing the model weights.";
  $("#agent-trace").textContent = "Running…";

  const depthResults = [];
  let completedRuns = 0;

  try {
    for (const depth of suite.depths) {
      const programRuns = [];

      for (const program of suite.programs) {
        await nativeRequest("agent.model.reset");
        let register = 0;
        const events = [];

        for (const event of program.events) {
          register = agentExpected(register, event);
          const result = await nativeRequest("agent.model.thought", {
            event: encodeAgentEvent(event),
            steps: depth
          });
          const predicted = Number(result.output[0]);
          events.push({
            op: event.op,
            arg: Object.prototype.hasOwnProperty.call(event, "arg")
              ? Number(event.arg)
              : null,
            expected: register,
            predicted,
            absolute_error: Math.abs(predicted - register),
            total_latency_ms: Number(result.total_latency_ms),
            thoughts: result.thoughts
          });
        }

        programRuns.push({
          id: program.id,
          events
        });

        completedRuns++;
        $("#agent-bench-progress").value = completedRuns;
        $("#agent-summary").textContent =
          "Completed " + completedRuns + "/" + totalRuns +
          " program/depth runs.";
      }

      depthResults.push({
        depth,
        programs: programRuns
      });
    }

    const metrics = depthResults.map(item =>
      summarizeAgentDepth(item.depth, item.programs, numCells)
    );

    lastAgentTest = {
      schema: 1,
      type: "agent_depth_context_benchmark",
      generated_at: new Date().toISOString(),
      suite: suite.name,
      model: (await nativeRequest("agent.model.status")).model,
      depth_metrics: metrics,
      depth_results: depthResults
    };

    $("#agent-status").textContent =
      "Depth/context benchmark complete.";
    $("#agent-summary").textContent =
      "Measured recurrence cost, accuracy, cell usage, and routing stability.";
    $("#agent-trace").textContent = renderAgentBenchmarkSummary(lastAgentTest);
  } catch (error) {
    $("#agent-status").textContent =
      "Agent benchmark failed: " + error.message;
    $("#agent-summary").textContent =
      "Stopped after " + completedRuns + "/" + totalRuns + " runs.";
    $("#agent-trace").textContent = String(error.stack || error);
  }
}

async function resetAgent() {
  try {
    await nativeRequest("agent.model.reset");
    $("#agent-summary").textContent = "Agent recurrent state reset.";
    toast("Agent state reset.");
    await refreshAgent();
  } catch (error) {
    toast("Reset failed: " + error.message);
  }
}

async function pushAgentTest() {
  if (!lastAgentTest) return toast("Run an Agent test first.");

  await refreshGitHub();
  if (!githubState?.signed_in || !githubState?.repo_access) {
    switchTab("data");
    return toast("Connect GitHub and grant Ai-Stuff access first.");
  }

  try {
    const prefix = lastAgentTest.type === "agent_depth_context_benchmark"
      ? "agent-depth-context-"
      : "agent-hardware-";
    await nativeRequest("github.pushResult", {
      filename: prefix + Date.now() + ".json",
      content: JSON.stringify(lastAgentTest, null, 2)
    });
    toast("Agent result pushed to GitHub.");
  } catch (error) {
    toast("Push failed: " + error.message);
    await refreshGitHub();
  }
}

function githubButtons(state) {
  const discovered = !!state.app_discovered;
  const signedIn = !!state.signed_in;
  const repoAccess = !!state.repo_access;

  show("#github-create", !discovered);
  show("#github-discover", !discovered);
  show("#github-client-id-card", !discovered);
  show("#github-settings", discovered && !repoAccess);
  show("#github-install", discovered && !repoAccess);
  show("#github-signin", discovered && !signedIn);
  show("#github-check-auth", false);
  show("#github-signout", signedIn);
  show("#github-code-card", false);
}

function renderGitHub(state) {
  githubState = state || {};
  githubButtons(githubState);

  if (githubState.signed_in && githubState.repo_access) {
    $("#github-status").textContent =
      "Connected as " + githubState.login + " · " + githubState.target_repo + " is writable.";
    $("#github-help").textContent =
      "Ready. Benchmark uploads will use your GitHub authorization stored in Android Keystore.";
    return;
  }

  if (githubState.signed_in && !githubState.repo_access) {
    $("#github-status").textContent =
      "Signed in as " + githubState.login + ", but AI Workbench does not have access to " + githubState.target_repo + ".";
    $("#github-help").textContent =
      "Tap Grant repo access and install the private AI Workbench GitHub App on Ai-Stuff.";
    show("#github-install", true);
    return;
  }

  if (githubState.app_discovered) {
    if (githubState.client_id) $("#github-client-id").value = githubState.client_id;
    $("#github-status").textContent = "GitHub connection created, but not signed in.";
    $("#github-help").textContent =
      "Open App settings and enable Device Flow, grant access to Ai-Stuff, then tap Sign in with GitHub.";
    return;
  }

  $("#github-status").textContent = githubState.error
    ? "GitHub setup: " + githubState.error
    : "GitHub connection has not been created yet.";
  $("#github-help").textContent =
    "Tap Create connection. GitHub will open a pre-filled device-specific GitHub App registration. Create it, return here, then tap Continue. No keys or tokens are copied manually.";
}

async function refreshGitHub() {
  try {
    renderGitHub(await nativeRequest("github.status"));
  } catch (error) {
    renderGitHub({ signed_in: false, app_discovered: false, error: error.message });
  }
}

async function createGitHubConnection() {
  const info = await nativeRequest("github.setupInfo");
  githubState = info;
  await nativeRequest("github.openUrl", { url: info.registration_url });
  $("#github-status").textContent = "GitHub registration opened. Create the pre-filled private app, then return and tap Continue.";
}

async function discoverGitHubConnection() {
  try {
    const info = await nativeRequest("github.discoverApp");
    renderGitHub({ ...info, signed_in: false, repo_access: false });
    toast("Connection found. Enable Device Flow in App settings next.");
  } catch (error) {
    $("#github-status").textContent =
      "Auto-detect failed. Paste the public Client ID from the GitHub page above.";
    show("#github-client-id-card", true);
  }
}

async function saveGitHubClientId() {
  const clientId = $("#github-client-id").value.trim();
  if (!clientId) return toast("Paste the GitHub App Client ID first.");

  await nativeRequest("secret.set", {
    name: "github_client_id",
    value: clientId
  });

  const info = await nativeRequest("github.setupInfo");
  renderGitHub({
    ...info,
    client_id: clientId,
    app_discovered: true,
    signed_in: false,
    repo_access: false
  });
  toast("Client ID saved. Continue with App settings.");
}

async function openGitHubField(field) {
  const info = githubState && githubState[field]
    ? githubState
    : await nativeRequest("github.setupInfo");
  if (!info[field]) return toast("GitHub connection is not ready yet.");
  await nativeRequest("github.openUrl", { url: info[field] });
}

function scheduleGitHubPoll(seconds) {
  clearTimeout(githubPollTimer);
  githubPollTimer = setTimeout(() => pollGitHubAuthorization(), Math.max(5, Number(seconds || 5)) * 1000);
}

async function startGitHubSignIn() {
  try {
    const auth = await nativeRequest("github.deviceStart");
    $("#github-code").textContent = auth.user_code;
    show("#github-code-card", true);
    show("#github-check-auth", true);
    $("#github-status").textContent = "Waiting for GitHub authorization…";
    await nativeRequest("clipboard.copy", {
      label: "GitHub authorization code",
      text: auth.user_code
    });
    await nativeRequest("github.openUrl", { url: auth.verification_uri });
    scheduleGitHubPoll(auth.interval);
  } catch (error) {
    $("#github-status").textContent = error.message;
    if (String(error.message).includes("Device Flow")) {
      toast("Open App settings, enable Device Flow, then try again.");
    }
  }
}

async function pollGitHubAuthorization() {
  try {
    const result = await nativeRequest("github.devicePoll");
    if (result.status === "authorized") {
      clearTimeout(githubPollTimer);
      show("#github-code-card", false);
      show("#github-check-auth", false);
      await refreshGitHub();
      toast("GitHub signed in.");
      return;
    }
    scheduleGitHubPoll(result.interval);
  } catch (error) {
    clearTimeout(githubPollTimer);
    $("#github-status").textContent = error.message;
    show("#github-check-auth", true);
  }
}

async function signOutGitHub() {
  clearTimeout(githubPollTimer);
  await nativeRequest("github.signOut");
  await refreshGitHub();
  toast("Signed out of GitHub.");
}

async function pushBenchmark() {
  if (!lastBenchmark) {
    return toast("Run a benchmark first.");
  }

  await refreshGitHub();
  if (!githubState?.signed_in || !githubState?.repo_access) {
    switchTab("data");
    return toast("Connect GitHub and grant Ai-Stuff access first.");
  }

  try {
    await nativeRequest("github.pushResult", {
      filename: "benchmark-" + Date.now() + ".json",
      content: JSON.stringify(lastBenchmark, null, 2)
    });
    toast("Benchmark result pushed to GitHub.");
  } catch (error) {
    toast("Push failed: " + error.message);
    await refreshGitHub();
  }
}

async function boot() {
  MODELS.forEach(model => $("#model-select").add(new Option(model.name, model.id)));

  document.querySelectorAll("#tabs button").forEach(button =>
    button.addEventListener("click", () => switchTab(button.dataset.tab))
  );

  $("#model-select").addEventListener("change", loadModelSelection);

  $("#download-button").addEventListener("click", async () => {
    const model = selectedModel();
    $("#model-status").textContent = "Starting download…";
    try {
      const result = await nativeRequest("model.download", model);
      $("#model-status").textContent = "Verified: " + result.filename;
      await refreshModels();
    } catch (error) {
      $("#model-status").textContent = "Download failed: " + error.message;
    }
  });

  $("#load-button").addEventListener("click", async () => {
    const model = selectedModel();
    $("#model-status").textContent = "Loading…";
    try {
      const result = await nativeRequest("model.load", {
        filename: model.filename,
        context: Number($("#context").value),
        threads: Number($("#threads").value)
      });
      loadedModel = model.filename;
      $("#model-status").textContent = "Loaded " + model.name + " · " + result.parameters + " parameters";
      $("#runtime-info").textContent = result.system_info || $("#runtime-info").textContent;
      await refreshModels();
    } catch (error) {
      $("#model-status").textContent = "Load failed: " + error.message;
    }
  });

  $("#unload-button").addEventListener("click", async () => {
    await nativeRequest("model.unload");
    loadedModel = null;
    $("#model-status").textContent = "No model loaded.";
    await refreshModels();
  });

  $("#delete-button").addEventListener("click", async () => {
    const model = selectedModel();
    await nativeRequest("model.delete", { filename: model.filename });
    if (loadedModel === model.filename) loadedModel = null;
    await refreshModels();
  });

  $("#agent-selftest").addEventListener("click", runAgentSelfTest);
  $("#agent-benchmark").addEventListener("click", runAgentBenchmark);
  $("#agent-reset").addEventListener("click", resetAgent);
  $("#push-agent-test").addEventListener("click", pushAgentTest);

  $("#send-button").addEventListener("click", sendChat);
  $("#stop-button").addEventListener("click", () => nativeRequest("generation.stop"));
  $("#bench-run").addEventListener("click", runBenchmark);
  $("#bench-stop").addEventListener("click", async () => {
    benchCancelled = true;
    await nativeRequest("generation.stop");
  });

  $("#check-update").addEventListener("click", () => checkUpdate());
  $("#update-button").addEventListener("click", async () => {
    const result = await checkUpdate(false);
    if (result?.update_available) await applyUpdate();
  });
  $("#apply-update").addEventListener("click", applyUpdate);

  $("#github-create").addEventListener("click", createGitHubConnection);
  $("#github-discover").addEventListener("click", discoverGitHubConnection);
  $("#github-save-client-id").addEventListener("click", saveGitHubClientId);
  $("#github-settings").addEventListener("click", () => openGitHubField("settings_url"));
  $("#github-install").addEventListener("click", () => openGitHubField("install_url"));
  $("#github-signin").addEventListener("click", startGitHubSignIn);
  $("#github-check-auth").addEventListener("click", pollGitHubAuthorization);
  $("#github-signout").addEventListener("click", signOutGitHub);
  $("#push-benchmark").addEventListener("click", pushBenchmark);

  await loadModelSelection();
  await refreshKernel();
  await refreshAgent();
  loadSavedBenchmark();
  await refreshGitHub();
  checkUpdate(false);
}

boot().catch(error => {
  document.body.innerHTML =
    "<pre style='padding:20px;color:white'>Workbench boot failed\n" +
    String(error.stack || error) +
    "</pre>";
});
