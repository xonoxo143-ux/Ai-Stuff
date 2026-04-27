# APK Delivery

`TEST-2` is the disposable Android app branch for LocalAI Lab.

## Build trigger

APK builds are push-triggered but commit-message gated.

A push to `TEST-2` only builds an APK when the latest commit message contains the build marker.

Commits without the marker do not build an APK.

## Delivery

Successful APK builds publish or update the `android-TEST-2-latest` prerelease and attach a stable APK named `LocalAI-Lab-debug-latest.apk`.

The workflow also posts the direct APK file link to a delivery issue so the phone install link is easy to find.

## First target

The first app version only proves the delivery loop:

- APK builds
- APK installs
- app launches
- status screen renders

Local AI runtime work starts after this loop is reliable.
