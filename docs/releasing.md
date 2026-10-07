# Releasing the workbench

Public users should start with the [macOS download and setup](../README.md). This document is for maintainers.

## Build inputs

Use the version tag, `uv.lock` and `web/package-lock.json`. The release uses Python 3.12, Node 22 and the packaging group (PyInstaller 6.22.3). Install tools inside the checkout's virtual environment; never copy a personal browser profile into a build directory.

```sh
uv sync --locked --extra web --group packaging --no-editable --python 3.12
cd web
npm ci
npm test
npm run build
npm exec playwright install chromium
npm run test:e2e
cd ..
.venv/bin/python -m pytest -q
uv build
```

Production assets, fonts and dependency notices must exist before `uv build`. Wheels and source distributions carry the browser UI; their runtime does not need Node.

## Native macOS app

Build on the architecture being distributed; do not relabel an arm64 app as universal.

```sh
.venv/bin/python scripts/build_macos.py --output dist/macos
.venv/bin/python scripts/smoke_macos.py 'dist/macos/HKUST Canvas Workbench.app'
```

The output directory must not already contain an app. Staging copies only application packages, static assets and entry points. Build provenance containing local installation paths is stripped. PyInstaller freezes the backend; Swift compiles the AppKit launcher and icon renderer. The script creates an app, ZIP and DMG, and verifies signatures and bundled parsing/frontend/auth boundaries.

By default the app is ad-hoc signed, **not notarized**. If available, pass a Developer ID Application identity through `MACOS_SIGNING_IDENTITY` and a preconfigured notarytool Keychain profile through `MACOS_NOTARY_PROFILE`. Do not commit certificates, passwords or Keychain exports. The build submits/staples the DMG when both are configured. The zipped app is not separately notarized by this script; document artifact-specific signing status accurately.

## Validation and publication

R5 adds automated PR/release-branch checks and a tag-driven release workflow. Required gates: Python tests, frontend unit tests, TypeScript/production build, isolated Playwright flows, secret scan, wheel install smoke and native installed-app smoke. All test data must be synthetic. No real Chrome cookies, HKUST calls or paid-provider requests belong in CI.

Before creating `v3.0.0`, verify Python and frontend versions agree, review the exact files to publish, build wheel/sdist/app/DMG, and hash the downloadable files into `SHA256SUMS`. A release must describe supported architectures, signing/notarization and actual test scope. Upload only release artifacts and checksums, never logs, session markers or app-data directories.

The installed-app smoke uses a temporary HOME and app-data directory, removes Node and repository tools from PATH, exercises native Quit, singleton reuse, authenticated HTTP, source extraction and persistence. This is an **isolated environment on the same OS**, not a clean VM or separate user account. Do not claim Gatekeeper, Chrome permissions or live provider accounts were tested by this smoke. A genuine fresh-user/download check remains a separate manual validation.

## Manual first-install checks

- Download the release DMG; compare its checksum; open using normal Gatekeeper handling.
- Copy to Applications and open; verify the browser opens, Dock reopen works and Quit closes only that app's service.
- Choose/test the intended Chrome profile, confirm the account, expire/retry the session, unlink and reconnect a different profile. Do not delete browser data.
- Connect a provider or skip; test invalid credentials/unavailable endpoint and disconnect. Any live test can consume account quota.
- Open a course, sync selected sources, ask a grounded question and inspect a citation; generate a quiz, flashcards and study guide. Restart and verify saved work.
- Check read-only MCP defaults and preview/cancel. A live write requires a safe target and explicit approval; automated fixtures cover confirmed writes and bypass rejection.
- Preserve existing study data on update. Remove app, study data and credentials separately during an uninstall test.
