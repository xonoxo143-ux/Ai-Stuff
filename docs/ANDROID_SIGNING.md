# Stable Android signing

AI Workbench now uses one permanent Android application identity.

## Frozen package

`com.xonoxo.aiworkbench.k2`

Do not change this package name unless we intentionally create a separate app.

## Frozen signing certificate

SHA-256:

`E2:E3:D6:D0:FE:17:D9:7F:E7:68:55:F5:75:8D:92:3D:BA:2A:5F:7D:95:EA:59:DA:25:7B:38:B0:42:C9:07:EF`

All distributable native builds must pass `scripts/verify_android_signing.py`.
A workflow is not allowed to silently fall back to a freshly generated debug key.

## GitHub secret

The private PKCS#12 signing material is **not** stored in this public repository.

GitHub Actions expects exactly one repository secret:

`AI_WORKBENCH_SIGNING_BUNDLE`

The offline backup created for the project contains a file named
`GITHUB_SECRET_VALUE.txt`. Its complete contents are the value of this secret.

The envelope contains the keystore, alias, and password. The workflow decodes it
inside the ephemeral GitHub runner using `scripts/prepare_android_signing.py`.

Never commit:

- `AIWorkbench-Stable-Signing.p12`
- `GITHUB_SECRET_VALUE.txt`
- the decoded password
- the signing bundle itself

## Why this matters

Android only preserves app data across an APK update when both the package name
and signing certificate match.

With the stable identity in place, future native APKs can install **over** the
existing app. That preserves:

- GitHub authorization stored by the app
- device/workbench preferences
- app-private state
- downloaded local models

The web Workbench should still update through the built-in mutable bundle system
without an APK install.

## Versioning

Native CI assigns a monotonically increasing Unix-time `versionCode` and a
human-readable stable version name. This prevents a newer signed build from being
rejected as a downgrade.

## Migration note

Builds made before stable signing used disposable CI debug keys. Their private
keys were not preserved. Android therefore cannot update those installs in place.

There is one unavoidable migration reinstall from an old disposable-signature
build to the first stable-signature build. After that migration, routine native
updates must be in-place upgrades rather than uninstall/reinstall cycles.
