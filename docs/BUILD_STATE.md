# Build State

## v0-prep

`TEST-2` has been converted into the LocalAI Lab Android scratch branch.

Included:

- minimal Android Gradle project
- launchable Java Activity
- APK marker workflow
- lightweight delivery and roadmap docs
- upstream SmolLM README replaced with LocalAI Lab notes

Expected first test:

- GitHub Actions starts only because this commit message contains the build marker.
- A debug APK is built from `TEST-2`.
- A stable release asset is published.
- The delivery issue receives the direct APK file link.

If this build fails, inspect the Actions log first. The most likely early failures are Gradle/Android plugin version mismatch or workflow permissions around issue creation.
