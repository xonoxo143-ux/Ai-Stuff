# Architecture

## Boundary 1: Godot

Godot owns everything visible to the user:

- model catalogue
- chat history
- prompt formatting
- settings
- download/load controls
- streamed text display
- APK project

Godot never performs tensor math and never touches JNI directly.

## Boundary 2: Android plugin

`LocalAIPlugin.kt` exposes a small Godot singleton named `LocalAI`.

Public calls:

```text
downloadModel(id, url, filename, sha256)
cancelDownload()
listLocalModels()
getModelPath(filename)
deleteModel(filename)
loadModel(path, contextSize, threads, gpuLayers)
unloadModel()
generate(prompt, maxTokens, temperature, topP, topK, repeatPenalty)
stopGeneration()
systemInfo()
```

All long work is moved off Godot's render thread. Results return through one-string JSON signals so the interface stays stable even when native details change.

## Boundary 3: llama.cpp

The native library owns:

- GGUF loading
- tokenization
- context allocation
- sampler construction
- decode loop
- cancellation flag
- performance timing
- cleanup

The initial build is CPU-only and ARM64-only. `n_gpu_layers` is already part of the API so a later Vulkan/OpenCL build does not require an interface rewrite.

## Model storage

Models are downloaded to:

```text
Android/data/<package>/files/models/
```

They are not included in the APK and survive normal app updates. Uninstalling the app may remove this app-specific directory.

## Catalogue

`app/data/models.json` is the source of truth. Each entry includes:

- stable id
- display name
- source
- exact download URL
- expected filename
- byte size
- SHA-256
- prompt template
- recommended settings
