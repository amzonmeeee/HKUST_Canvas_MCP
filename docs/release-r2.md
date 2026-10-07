# R2: first-run onboarding

Welcome → Canvas → AI provider → Privacy & safety → optional MCP → Ready. Reuses existing profile/provider/client controls; Canvas and AI may be skipped. Completion and explicit privacy acknowledgement persist. Settings can reopen setup. Profile tests show the bounded Canvas account identity and human-readable Chrome directory label; no SSO automation or email/token exposure.

Fresh installs cannot implicitly read Chrome or Canvas before explicit profile selection. Existing workspace/provider users keep their bindings and skip repeat onboarding. SQLite migration 5 → 6 adds app_settings and preserves study data. Older web builds cannot open schema 6; the v2 CLI/MCP do not use this database.

Validation: **555 Python tests, 30 frontend tests, 14 Playwright flows passed**; TypeScript/production build and changed-file Ruff checks passed. Synthetic fixtures only; no real Canvas write, paid API call or personal settings change.

User explicitly authorized continuing R2–R5 without phase stops; R3 follows this commit.

Exact changed files (16):

```text
auth/probe.py
docs/release-r2.md
tests/test_onboarding.py
web/e2e/workbench.spec.ts
web/src/App.test.tsx
web/src/App.tsx
web/src/features/CanvasConfiguration.tsx
web/src/features/Onboarding.test.tsx
web/src/features/Onboarding.tsx
web/src/features/Settings.tsx
web/src/styles.css
webapp/api.py
webapp/db.py
webapp/routes.py
webapp/services/canvas.py
webapp/store.py
```
