# R3: native macOS packaging

Adds a thin AppKit launcher, the existing book logo as an app icon, and a frozen Python backend containing the production React assets. Launch opens the default browser after readiness. Dock/menu reopen and Quit work through the owned process. A private authenticated handshake and file lock reuse an existing desktop service; occupied ports fall back to a free loopback port. Parent monitoring closes a backend when its launcher disappears. Startup failures offer Show logs / Retry / Quit.

The bundled executable also supports the existing CLI and read-only MCP entry points, so generated client configurations do not need a separate Python installation. Source staging excludes browser databases, user data, logs and caches. Local installation provenance is removed before signing. No application was installed into the builder's Applications folder.

Validation: **566 Python tests passed**. Swift launcher/icon compilation, app code-sign verification, frozen backend self-test and an installed-app smoke passed on **macOS 27.0.1 / arm64**. The smoke uses an isolated HOME, working directory and app data, with only system tools on PATH: native Quit, singleton reuse, static frontend, unconfigured Canvas, session/CSRF authentication and persisted workspace after restart. Frozen parser workers extract PDF, DOCX, PPTX, HTML and text; scheduled submissions point at the bundled CLI entry. Existing frontend validation remains 30 unit tests / 14 Playwright flows from R2; no frontend code changes in R3.

Artifacts built: `.app`, `.zip` and `.dmg`. No Developer ID Application identity is available: local artifacts are **ad-hoc signed, not notarized**. A fresh VM/user account and downloaded-file Gatekeeper handling have not been manually tested; isolated HOME testing is not represented as that stronger test. No runtime Node/Python installation is required. The builder accepts optional signing identity/notary profile; user study data is never copied into the bundle.

Compatibility: no database migration beyond R2 schema 6; CLI/MCP use the existing entry points. The macOS installer is arm64-only until another architecture is built and tested.

Exact changed files (15):

```text
MANIFEST.in
desktop/Icon.swift
desktop/Launcher.swift
desktop/backend_entry.py
docs/release-r3.md
pyproject.toml
schedule/launchd.py
scripts/build_macos.py
scripts/smoke_macos.py
tests/test_desktop.py
uv.lock
webapp/desktop.py
webapp/launcher.py
webapp/local_clients.py
webapp/parsers.py
```
