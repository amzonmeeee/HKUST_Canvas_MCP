# v3 Phase A implementation map

This branch implements the foundation only. Phase B source sync and the later model/chat/studio phases remain out of scope. The implementation is authorized directly by the user's instruction to open a branch and proceed without questions; the approval pause in the suggested specification prompt does not apply.

## Shared integration

`webapp/services/canvas.py` calls existing `dispatch_tool_call` handlers for `list_courses` and `get_course_overview`. Authentication uses existing `get_auth_status`. Responses are projected onto a small allowlist; no Chrome paths, cookie values, probe redirects, teacher records or raw errors are returned. No ToolSpec names or handlers need refactoring for Phase A.

## Files and boundaries

- `webapp/`: optional FastAPI app, local security middleware, SQLite repository, shared Canvas adapter, launcher, packaged static assets.
- `web/`: React/TypeScript/Vite app, API client, dashboard/workspace/settings routes, CSS, frontend tests and build configuration.
- `cli/web.py`: lazy `canvas web` entrypoint.
- `tests/test_webapp.py`: isolated API/storage/security tests.
- `PRODUCT.md`, `DESIGN.md`: product and interface context.
- `docs/v3-phase-a.md`: implementation map and validation record.

The existing setuptools build includes `webapp/static` in wheels and source distributions. Build frontend assets before Python packaging. End users install the `web` extra and run `canvas web`; Node is required only to rebuild the frontend.

## Dependencies

Python optional extra: `fastapi>=0.115,<1`, `uvicorn>=0.30,<1`. Development tests additionally declare `httpx>=0.27,<1`. SQLite uses the standard library; no ORM is necessary for this small schema.

Frontend: `react`, `react-dom`, `lucide-react`, `@fontsource-variable/public-sans`. Development: `typescript`, `vite`, `@vitejs/plugin-react`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `@types/react`, `@types/react-dom`, `@types/node`, `@playwright/test`. Exact resolved versions are recorded in `web/package-lock.json`.

## Storage and settings

The default database is `~/Library/Application Support/HKUST_Canvas_MCP/app.db` on macOS; Linux uses XDG data storage and Windows uses local application data. `--data-dir` allows explicit isolated storage outside the repository. SQLite has schema version 1, a unique course/workspace relationship, transactions and owner-only storage permissions. Existing `~/.config/canvasmcp/settings.json` continues to own Chrome profile selection and is not rewritten by the web app.

## Compatibility and security

Web imports remain lazy so base CLI/MCP installations do not need FastAPI/Uvicorn. The server binds only `127.0.0.1`, validates the exact Host/port and Origin, establishes an HttpOnly SameSite session using a launch fragment, and requires a separate CSRF token for local mutations. There is no CORS, arbitrary filesystem read endpoint, generic tool dispatch or Canvas write endpoint. A user can reopen an existing workspace even when Canvas is unavailable.

The version remains 2.0 during this incomplete foundation. The release target is 3.0.0 after all specification definition-of-done items are implemented; Phase A must not be presented as a complete v3 release.

## Validation

Validated on 2026-10-06:

| Check | Result |
|---|---|
| Complete Python suite | **428 passed**: all 366 existing v2 tests plus 62 new web/storage/security/launcher tests |
| Frontend Vitest / Testing Library | **13 passed** |
| Mocked Playwright browser flows | **3 passed**: desktop course open/rename/delete, mobile custom workspace, Settings/keyboard navigation |
| TypeScript + production frontend build | Passed; includes frontend tests and Playwright sources in type checking |
| New Python Ruff checks | Passed |
| Production npm dependency audit | 0 vulnerabilities |
| Wheel and source distribution | Built with compiled HTML, JS, CSS, fonts and third-party licenses; no Node runtime needed |
| Installed `canvas web` smoke | Passed: random loopback port, static shell/assets, session gate, local CRUD, Origin protection and graceful stop |
| Base CLI lazy import / MCP entrypoint | Passed: importing CLI does not import FastAPI; existing MCP help works |
| Source privacy review / `git diff --check` | Passed; no real Canvas records, auth secrets, personal paths or runtime databases in changes |

Automated tests use synthetic data and mocks, without Chrome cookie reads or real Canvas/provider HTTP calls. Browser screenshots and temporary runtime data remain outside Git.

The separate real-session check reached Canvas, but the existing selected Chrome session returned HTTP 401 (`not_logged_in`). It therefore did **not** verify a live course list or a real course workspace. The app presents sign-in/retry guidance; no login automation, Canvas writes or paid model calls were attempted. A fresh Chrome sign-in is required to complete that manual acceptance check.

## Exact modified files

```text
.gitignore
README.md
cli/bootstrap.py
docs/cli.md
pyproject.toml
uv.lock
```

## Exact added files

```text
DESIGN.md
MANIFEST.in
PRODUCT.md
cli/web.py
docs/v3-phase-a.md
tests/test_webapp.py
web/e2e/workbench.spec.ts
web/index.html
web/package-lock.json
web/package.json
web/playwright.config.ts
web/scripts/licenses.mjs
web/src/App.test.tsx
web/src/App.tsx
web/src/api.test.ts
web/src/api.ts
web/src/components.tsx
web/src/features/Dashboard.tsx
web/src/features/Settings.tsx
web/src/features/Workspace.tsx
web/src/main.tsx
web/src/styles.css
web/src/test/setup.ts
web/src/types.ts
web/tsconfig.json
web/vite.config.ts
webapp/__init__.py
webapp/api.py
webapp/db.py
webapp/launcher.py
webapp/security.py
webapp/services/__init__.py
webapp/services/canvas.py
```

Generated `webapp/static/`, build artifacts, test output and `node_modules/` are ignored by Git. Static assets are nevertheless explicitly included by setuptools in a built wheel/sdist. The checkout's project virtual environment has the built UI installed.
