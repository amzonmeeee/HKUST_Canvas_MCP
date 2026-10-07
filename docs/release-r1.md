# R1: safety and unlink/disconnect

Branch: `release/first-v3.0.0`, based on `main` at `d06598b`.
Date: 2026-10-07. Release gap analysis: [release-gap-v3.0.0.md](release-gap-v3.0.0.md).

## Implemented

- Settings and dashboard Canvas configuration offer an explicit, cancellable **Unlink Canvas profile** confirmation. The authenticated, CSRF-protected DELETE endpoint clears the shared binding, resets the web client and cancels pending web previews. Browser profiles/cookies/login and cached workspaces/sources are preserved.
- An atomic, owner-readable settings write persists `canvas_connection: unlinked`. Default-profile fallback, saved/env profile selection, explicit profile paths, cached clients and registered Canvas handlers cannot bypass it. Auth status becomes `unconfigured`; reconnect requires choosing a profile. CLI profile discovery remains available without reading cookies while unlinked.
- MCP hides nine mutation tools by default and also guards their callbacks against stale direct calls. `--allow-writes` or `CANVAS_MCP_ALLOW_WRITES=1` enables them; `--read-only` overrides the environment. Invalid environment values fail before auth/startup. Generated client setup pins `--read-only`. Original write names, payloads and preview/token confirmation are retained.
- Provider removal already deleted only the app binding and its own credential-store item. UI copy now says **Disconnect** and explains preserved external login/accounts and saved study data. Tests cover credential-deletion failure retaining the configuration, and keyless CLI disconnect preserving other providers/data.
- README now has a prominent safety/privacy section, write opt-in and unlink instructions, non-affiliation copy and critical-action verification. SECURITY.md describes supported versions, trust boundaries, Canvas/provider credential handling, data sent to model endpoints, confirmation limits and private reporting.
- All Python tests isolate profile settings outside the real user's configuration, in addition to the existing Chrome/network block.

## Verification

| Check | Result |
| --- | --- |
| Python suite | **552 passed**; baseline 532, plus 18 release-safety cases and 2 provider-disconnect regressions |
| Frontend unit suite | **29 passed** across 5 files; baseline 26, plus 3 unlink/cancel/failure/reconnect tests |
| Playwright | **13 distinct flows verified**: 12 existing flows passed in the full run; the new unlink/relink flow passed in a focused rerun after correcting selectors for same-name buttons and saved-workspace text |
| TypeScript + production frontend build | Passed; self-hosted production assets generated |
| Ruff | Changed Python files checked; passed |
| Git whitespace check | Passed |
| Targeted privacy audit | Repository source/docs checked for private file types, known personal Canvas identifiers/paths/session link and common credential formats; no findings |

Verification used synthetic profiles, settings, local databases and fake providers. No real Canvas writes, provider inference charges, live unlink, browser-data changes or system/global package installation occurred. A full CI secret-scan job and clean-machine installer smoke are still R5/R3 work; this audit does not stand in for those checks.

## Compatibility and remaining risks

SQLite stays at **schema 5**; there is no database migration or study-data deletion. Never-unlinked legacy installations retain their saved/env/Default profile behavior. Once explicitly unlinked, the marker takes precedence and even `canvas settings clear` preserves it; `canvas settings choose-profile` or an in-app profile choice reconnects.

MCP read-only is an intentional new default. Clients using write tools need explicit opt-in; generated `--read-only` must be replaced rather than combined with `--allow-writes`. Direct Canvas CLI write commands keep their existing confirmation contracts.

Unlink prevents subsequent operations; it cannot recall a request already in progress. Previously scheduled submissions cannot authenticate while unlinked. Relinking does not erase existing job records: inspect job state before reconnecting. External MCP clients must still show previews and obtain human approval; a confirmation token validates an action, not the identity of whoever read a chat. No second confirmation system was added.

GitHub private vulnerability reporting availability, signing/notarization and clean-machine installation have not been verified. No native installer, release tag, GitHub Release or remote push was created in R1.

## Exact changed files (26)

```text
README.md
SECURITY.md
auth/__init__.py
auth/inspect.py
auth/probe.py
auth/profiles.py
auth/settings.py
canvas_mcp/server.py
client/base.py
docs/release-gap-v3.0.0.md
docs/release-r1.md
specs/assignments.py
specs/registry.py
tests/conftest.py
tests/test_activity.py
tests/test_release_safety.py
tests/test_study_webapp.py
web/e2e/workbench.spec.ts
web/src/features/CanvasConfiguration.test.tsx
web/src/features/CanvasConfiguration.tsx
web/src/features/Dashboard.tsx
web/src/features/Providers.tsx
web/src/features/Settings.tsx
webapp/local_clients.py
webapp/routes.py
webapp/services/canvas.py
```

## Next phase

R2 is first-run onboarding. R3–R5 cover the native launcher/installer, public docs/screenshots and CI/release. HANDOFF §26 requires stopping after each verified phase unless explicitly asked to continue; those phases have not been started.
