# Android APK release process

Ngozi Smart Campus distributes one Android APK for all roles directly through the web application. It does not use Google Play or create role-specific applications.

## Identity and versioning

The stable Android application ID is `com.ngozi.smartcampus`. The display name, public semantic `version`, and monotonically increasing Android `versionCode` are controlled in `mobile/app.json`. The matching package version is kept in `mobile/package.json`.

For every release, increment `version` according to the scope of change (`1.0.1`, `1.1.0`, `2.0.0`) and always increment `versionCode` (`2`, `3`, `4`). Never reuse either value.

## Build and signing

Expo SDK 54 is built with the `apk` EAS profile in `mobile/eas.json`:

```sh
cd mobile
npx eas-cli login
npx eas-cli build --platform android --profile apk
```

The profile explicitly produces an installable APK, not an AAB, and does not configure store submission. An Expo account and network access are required. EAS-managed Android credentials are the preferred signing strategy: the encrypted keystore stays in EAS credential storage and is reused for every update. Losing or replacing that signing key prevents Android from installing future versions over existing installations. Do not commit a keystore, passwords, `credentials.json`, or downloaded credentials.

The internal `apk` profile is bound explicitly to the EAS `preview` environment. During physical LAN testing, that environment may provide an `http://<LAN-IP>:8000/api/v1` endpoint. Android cleartext traffic is enabled through the SDK 54-compatible `expo-build-properties` plugin, and preview builds show the effective non-sensitive API URL on the login screen. Before a public production release, switch the API to HTTPS, disable `usesCleartextTraffic`, and use a production EAS environment/profile. Public releases must not depend on cleartext HTTP.

If production policy later requires a locally controlled key, use EAS credentials tooling to upload the stable production keystore through the interactive encrypted workflow. Keep all local credential files ignored.

## Publish through the campus website

1. Download the completed EAS APK.
2. Verify the configured version and versionCode.
3. Sign in to the web Admin portal and open **Mobile App Releases**.
4. Upload the APK with its version, versionCode, and release notes.
5. Publish the draft. Publishing makes it the single latest Android release and supersedes the prior latest flag without deleting history.
6. Verify `/download-app`, download the APK, and install it on an Android device before announcing the release.

The backend renames the public download to `ngozi-smart-campus-android-v<version>.apk`, computes file size and SHA-256 itself, and stores the binary under ignored `runtime/mobile_releases/`. PostgreSQL stores only release metadata and an opaque file reference. Draft and retired artifacts are never publicly downloadable.

For independent local artifact verification:

```sh
sha256sum ngozi-smart-campus-android-v1.0.0.apk
```

Compare that value with the checksum shown by the public download page. Retire obsolete releases instead of deleting their records.
