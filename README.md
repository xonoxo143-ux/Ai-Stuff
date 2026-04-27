# LocalAI Lab

Disposable Android app branch for local AI experiments.

This branch is intentionally not preserving the upstream SmolLM repository shape. `TEST` can remain the reference fork; `TEST-2` is the scratch Android app lane.

## Current goal

Prove the phone testing loop:

```text
patch repo in chat
commit to TEST-2 with the APK build marker
GitHub builds a debug APK
GitHub publishes a stable release asset
the direct APK file link is posted to the delivery issue
install and test on Android
```

## v0 app

The first APK is only a shell:

- app launches
- status screen renders
- build/version details show
- runtime honestly says it is not wired yet

No local model runtime is included yet.

## Build workflow

The workflow is push-triggered but marker-gated. Normal commits do not build an APK. A commit with the build marker starts the APK pipeline.

See `docs/APK_DELIVERY.md`.
