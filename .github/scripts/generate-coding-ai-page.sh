#!/usr/bin/env bash
set -euo pipefail

: "${SITE_DIR:?SITE_DIR is required}"
: "${SOURCE_DIR:?SOURCE_DIR is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"

html_escape() {
  local escaped="$1"
  escaped="${escaped//&/&amp;}"
  escaped="${escaped//</&lt;}"
  escaped="${escaped//>/&gt;}"
  escaped="${escaped//\"/&quot;}"
  escaped="${escaped//\'/&#39;}"
  printf '%s' "${escaped}"
}

mkdir -p "${SITE_DIR}"
cp "${SOURCE_DIR}/app.js" "${SITE_DIR}/app.js"
cp "${SOURCE_DIR}/style.css" "${SITE_DIR}/style.css"
mkdir -p "${SITE_DIR}/prompts"
cp "${SOURCE_DIR}/prompts/smoke_coding_prompts.json" "${SITE_DIR}/prompts/smoke_coding_prompts.json"

repository_escaped="$(html_escape "${GITHUB_REPOSITORY}")"
commit_escaped="$(html_escape "${GITHUB_SHA:0:7}")"
built_at_escaped="$(html_escape "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"

cat > "${SITE_DIR}/index.html" <<EOF
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="dark light">
    <title>Coding AI Lab</title>
    <link rel="stylesheet" href="./style.css">
  </head>
  <body>
    <main class="page-shell">
      <header class="hero panel">
        <div>
          <p class="eyebrow">Browser test bench</p>
          <h1>Coding AI Lab</h1>
          <p class="hero-copy">Load a small Hugging Face model in your browser, run coding prompts, and export the results before we fine-tune anything.</p>
        </div>
        <div class="status-pill" id="globalStatus" data-state="idle">Status: Not loaded</div>
      </header>

      <section class="panel grid-panel" aria-labelledby="runtimeTitle">
        <div>
          <p class="eyebrow">Runtime</p>
          <h2 id="runtimeTitle">Browser support</h2>
          <p class="muted">This checks whether your browser can use WebGPU or should fall back to WASM.</p>
        </div>
        <div class="status-grid">
          <div class="mini-card"><span>Browser</span><strong id="browserValue">Checking...</strong></div>
          <div class="mini-card"><span>WebGPU</span><strong id="webgpuValue">Checking...</strong></div>
          <div class="mini-card"><span>WASM</span><strong id="wasmValue">Available</strong></div>
          <div class="mini-card"><span>Backend</span><strong id="backendValue">Auto</strong></div>
        </div>
        <div class="button-row">
          <button id="checkSupportBtn" type="button">Check Browser Support</button>
          <button id="clearStatusBtn" type="button" class="secondary">Clear Status</button>
        </div>
        <pre id="statusLog" class="log-box" aria-live="polite"></pre>
      </section>

      <div class="main-grid">
        <section class="panel" aria-labelledby="modelTitle">
          <p class="eyebrow">Setup</p>
          <h2 id="modelTitle">Model</h2>
          <label for="modelSelect">Model</label>
          <select id="modelSelect">
            <option value="HuggingFaceTB/SmolLM2-135M-Instruct">SmolLM2 135M Instruct — fastest test</option>
            <option value="HuggingFaceTB/SmolLM2-360M-Instruct">SmolLM2 360M Instruct — better, slower</option>
            <option value="custom">Custom model ID — advanced</option>
          </select>
          <input id="customModelInput" class="hidden" type="text" placeholder="organization/model-name">

          <label for="runtimeSelect">Runtime</label>
          <select id="runtimeSelect">
            <option value="auto">Auto</option>
            <option value="webgpu">WebGPU</option>
            <option value="wasm">WASM</option>
          </select>

          <details class="advanced-box">
            <summary>Advanced settings</summary>
            <label for="maxTokensInput">Max new tokens</label>
            <input id="maxTokensInput" type="number" min="32" max="1024" step="32" value="256">
            <label for="temperatureInput">Temperature</label>
            <input id="temperatureInput" type="number" min="0" max="2" step="0.1" value="0.2">
            <label for="topPInput">Top-p</label>
            <input id="topPInput" type="number" min="0.1" max="1" step="0.05" value="0.9">
            <label for="systemPromptInput">System instruction</label>
            <textarea id="systemPromptInput" rows="3">You are a concise coding assistant. Prefer correct, simple code.</textarea>
          </details>

          <div class="button-row sticky-actions">
            <button id="loadModelBtn" type="button">Load Model</button>
            <button id="unloadModelBtn" type="button" class="secondary">Unload Model</button>
            <button id="resetPageBtn" type="button" class="danger">Reset Page</button>
          </div>
        </section>

        <section class="panel" aria-labelledby="promptTitle">
          <p class="eyebrow">Prompt</p>
          <h2 id="promptTitle">Coding prompt</h2>
          <label for="promptSelect">Template</label>
          <select id="promptSelect"></select>
          <label for="promptInput">Prompt text</label>
          <textarea id="promptInput" rows="11" spellcheck="false"></textarea>
          <div class="button-row sticky-actions">
            <button id="runPromptBtn" type="button">Run Prompt</button>
            <button id="stopBtn" type="button" class="secondary">Stop Generation</button>
            <button id="clearPromptBtn" type="button" class="secondary">Clear Prompt</button>
            <button id="copyPromptBtn" type="button" class="secondary">Copy Prompt</button>
          </div>
        </section>
      </div>

      <section class="panel" aria-labelledby="outputTitle">
        <p class="eyebrow">Output</p>
        <h2 id="outputTitle">Model response</h2>
        <div class="result-meta" id="resultMeta">No run yet.</div>
        <pre id="outputBox" class="output-box"></pre>
        <div class="button-row">
          <button id="copyOutputBtn" type="button">Copy Output</button>
          <button id="saveResultBtn" type="button" class="secondary">Save Result to Page Log</button>
          <button id="clearOutputBtn" type="button" class="secondary">Clear Output</button>
        </div>
        <fieldset class="rating-box">
          <legend>Rate answer</legend>
          <label><input type="radio" name="rating" value="Bad"> Bad</label>
          <label><input type="radio" name="rating" value="Okay"> Okay</label>
          <label><input type="radio" name="rating" value="Good"> Good</label>
        </fieldset>
      </section>

      <section class="panel" aria-labelledby="logTitle">
        <p class="eyebrow">Session</p>
        <h2 id="logTitle">Results log</h2>
        <p class="muted">Saved locally in this page session only. Export it before leaving the page.</p>
        <div id="sessionLog" class="session-log"></div>
        <div class="button-row">
          <button id="exportJsonBtn" type="button">Export Results JSON</button>
          <button id="exportMarkdownBtn" type="button" class="secondary">Export Results Markdown</button>
          <button id="copyAllBtn" type="button" class="secondary">Copy All Results</button>
          <button id="clearLogBtn" type="button" class="danger">Clear Session Log</button>
        </div>
      </section>

      <section class="panel" aria-labelledby="helpTitle">
        <details open>
          <summary id="helpTitle">What am I testing?</summary>
          <p>This page runs a small language model in your browser. The first goal is not perfect answer quality. The first goal is proving that the browser can load a model, answer coding prompts, and produce baseline results we can improve later.</p>
          <ul>
            <li><strong>Model</strong> = the AI brain.</li>
            <li><strong>Prompt</strong> = what you ask it.</li>
            <li><strong>Inference</strong> = asking the model for an answer.</li>
            <li><strong>Fine-tuning</strong> = training an existing model on better examples.</li>
            <li><strong>Eval</strong> = testing whether the model improved.</li>
          </ul>
        </details>
      </section>

      <footer class="footer">
        <span>Repository: <a href="https://github.com/${repository_escaped}">${repository_escaped}</a></span>
        <span>Commit: <code>${commit_escaped}</code></span>
        <span>Built: <code>${built_at_escaped}</code></span>
      </footer>
    </main>
    <script type="module" src="./app.js"></script>
  </body>
</html>
EOF

cp "${SITE_DIR}/index.html" "${SITE_DIR}/404.html"
