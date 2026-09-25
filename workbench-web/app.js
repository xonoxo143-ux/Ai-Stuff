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
