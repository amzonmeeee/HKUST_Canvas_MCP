# Your Canvas. Your AI.

The first public HKUST Canvas Workbench release adds a browser study workspace alongside the existing Canvas CLI and MCP server.

- First-run setup: choose/test the intended Chrome profile, verify the Canvas account, connect a provider or skip, and review sharing/safety.
- Selected source sync and local indexing, grounded streaming chat, inspectable citations, notes and study materials with export.
- Existing Codex/Claude Code CLI login, official OpenAI/Anthropic APIs and compatible/local endpoints.
- Safe disconnects: unlink Canvas without changing Chrome; disconnect providers without deleting external accounts.
- Read-only MCP defaults; supported writes retain exact previews and explicit backend confirmation.
- Self-contained Apple Silicon macOS app with Dock/menu launcher, browser opening, duplicate-service reuse and graceful Quit.

## Downloads

Use the Apple Silicon DMG or zipped app. Drag the app to Applications and open it; no Python, Node.js or repository clone is needed. Developers can install the wheel with its `[web]` extra in a virtual environment. The source distribution and `SHA256SUMS` are included.

**Signing:** macOS artifacts are ad-hoc signed, not Developer ID signed or notarized. If macOS blocks a trusted download, use its per-app Privacy & Security → Open Anyway flow as described in the README; do not disable Gatekeeper globally.

**Verification scope:** local macOS 27.0.1/arm64 tests use isolated HOME/app data and system-only runtime PATH. Native Quit, singleton reuse, restart persistence, bundled UI, bounded PDF/DOCX/PPTX/HTML/text extraction, session/CSRF enforcement and read-only MCP are checked. CI repeats synthetic Python/frontend/browser/package checks on Ubuntu and macOS 15, including a native build. No private Canvas credentials, real Chrome data or paid-provider calls enter these tests. Downloaded-file Gatekeeper behavior and real provider/Chrome permissions still need user verification; they are not certified by a headless smoke test.

## Upgrade / privacy

Application updates preserve saved work. Database schema 6 adds setup preferences without deleting existing workspaces; older web builds cannot open the newer database. The CLI/MCP retain v2 entry points and tools, with MCP mutations now an explicit opt-in.

Canvas cookies remain in the backend. Sending/generating with a cloud model shares the prompt, relevant history and retrieved selected-source excerpts, plus requested live results when enabled. Uninstall the app, delete study data and remove app-owned credentials separately; see README and SECURITY.md.

MIT licensed. Independent of HKUST, Instructure and AI providers. Credits to ynbh/canvasmcp and vishalsachdev/canvas-mcp. Read-only workspace MCP access is planned for a later release.
