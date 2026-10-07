# R5: automated checks and release engineering

Version is explicitly 3.0.0. PR/main/release CI covers Python, frontend, TypeScript/build, synthetic browser flows, full Git-history secret scan, wheel/sdist audit and fresh wheel installation on Ubuntu 24.04 and macOS 15. A subsequent arm64 macOS job builds and tests the self-contained app/ZIP/DMG. Tag publication reuses all gates, verifies versions, hashes assets and creates a GitHub Release; it cannot replace an existing release.

Actions/toolchains/scanner/build backend are pinned. The Swift deployment target and app metadata now both specify macOS 15; actual platform validation is reported separately. Credentials are not stored in workflow files. GitHub private vulnerability reporting was enabled using the existing repository authorization. PyPI is optional and remains unconfigured.

Local validation: **566 Python / 30 frontend / 14 Playwright tests passed**. TypeScript/production assets, fresh wheel install, bounded bundled PDF/DOCX/PPTX/HTML/text parsing, native Quit, singleton, restart persistence and static UI smoke passed. Archive inspections reject browser data, environment/database/log/session files and require the frontend/prompts. Source and Git-history Gitleaks scans passed after an exact historical official-public-API-example exception; newly introduced keys remain scanned.

The versioned tag workflow is the authoritative remote build/verification record. Release is published only after its checks pass. Downloaded-file Gatekeeper and real Chrome/provider permission prompts are manual checks; headless/isolated HOME smoke does not certify them. No real Canvas write or paid inference is performed during release validation. Remote validation identified remaining macOS-only screenshot paths and a detached-DOM timing race in a CSS assertion; paths now use test output folders and CSS checks retry against the current rendered node.

Upgrade risk: schema 6 is already covered by R2 migration/preservation tests; older web builds cannot open it. The v2 CLI/MCP commands are preserved, with MCP writes explicitly opt-in. The public installer is Apple Silicon only and ad-hoc signed, not notarized.

Exact changed files (14):

```text
.github/workflows/ci.yml
.github/workflows/release.yml
.gitleaksignore
MANIFEST.in
SECURITY.md
docs/release-notes-v3.0.0.md
docs/release-r5.md
docs/releasing.md
pyproject.toml
scripts/audit_release.py
scripts/build_macos.py
scripts/install_gitleaks.py
scripts/smoke_wheel.py
web/e2e/workbench.spec.ts
```
