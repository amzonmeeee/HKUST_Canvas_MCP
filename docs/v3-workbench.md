# v3.0 Local AI Study Workbench

The feature branch extends `canvas web` into a study workspace while retaining the v2 CLI/MCP tool registry and Chrome-session authentication. Python changes and optional web dependencies stay in the project's virtual environment. Canvas and study data live outside the repository.

## Implementation and requirement map

| Requirement | Implementation | Verification |
| --- | --- | --- |
| Local browser UI and launch | `cli/web.py`, `webapp/launcher.py`, `webapp/security.py` | Port reservation, exact Host/Origin, HttpOnly session, CSRF and packaged assets |
| Course dashboard, course/custom workspaces | `webapp/db.py`, `webapp/api.py`, `web/src/features/Dashboard.tsx` | CRUD, course uniqueness, offline reopening, migration and concurrent initialization |
| Canvas source tree, selection and local sync | `webapp/services/sources.py`, `web/src/features/Sources.tsx` | Explicit inventory/sync/refresh, canonical module items, independent failures and checksum reuse |
| Local extraction and indexing | `webapp/parsers.py`, `webapp/store.py` | PDF, DOCX, PPTX, HTML, Markdown, text/caption fixtures, scoped FTS and Unicode search |
| Configurable providers and streaming | `webapp/providers.py`, `webapp/routes.py`, `web/src/features/Providers.tsx` | OpenAI Responses, Anthropic Messages and compatible Chat Completions stream/nonstream/tool/schema contracts |
| Native CLI providers and desktop setup | `webapp/native_providers.py`, `webapp/local_clients.py`, `web/src/features/LocalClients.tsx` | Codex/Claude Code login, ephemeral text-only inference, cancellation, native schema validation, safe desktop MCP configuration merge |
| Citation-aware chat and persisted history | `webapp/services/study.py`, `web/src/features/Chat.tsx` | Selected-source context, scope-aware history, SSE, partial failures, valid IDs and citation inspection |
| Quiz, flashcards and study guide | `webapp/services/study.py`, `web/src/features/Studio.tsx` | Schemas, provenance/citations, quiz practice, card reveal and Markdown/JSON exports |
| Local notes and saved artifacts | `webapp/store.py`, `web/src/features/Studio.tsx` | Note CRUD and saving answers/materials with provenance |
| Preserved v2 MCP and approval | `webapp/services/interactions.py`, `web/src/features/Actions.tsx` | Existing registry remains unchanged; previews pin arguments and hide single-use v2 tokens |
| Credentials and privacy | `webapp/providers.py`, `webapp/security.py`, `webapp/observability.py` | Keychain-only keys, private paths, no secrets in SQLite/API errors/model tool results and metadata-only logs |
| Versioned prompts and packaging | `webapp/prompts/*_v1.md`, `pyproject.toml`, `MANIFEST.in` | Wheel/source distribution include compiled assets, prompts, fonts and dependency notices |

## Sources and retrieval

Inventory lists syllabus, modules, pages, files, assignments, announcements and top-level discussion topics. Student discussion replies and submission files are not indexed automatically. Category permission/errors are independent. Limits are disclosed: 300 entries per category, 300 modules and 300 items per module. Canonical module-item endpoints avoid Canvas's partial inline arrays. Unmoduled resources remain in separate categories. Selecting a module also selects its available child sources.

Sync is explicit. Page/description checksums avoid unnecessary reindexing. File timestamps avoid unnecessary downloads; checksums avoid reparsing unchanged content when timestamps change. Unchanged refreshes preserve citation IDs. Updated/removed sources leave saved citation excerpts available in prior answers and artifacts, while the viewer explains an unavailable current-version citation.

Extraction runs in a separate Python process with a 45-second timeout and CPU limit. Linux adds an address-space limit. Files are limited to 25 MB, document archives to 100 MB expanded and 10,000 members, PDFs to 1,000 pages and extracted text to 2 million characters. Failed, empty and unsupported sources cannot enter AI scope. OCR, transcription, authenticated external/LTI fetches and XLSX parsing are outside v3.0. Captions can be uploaded as VTT/SRT.

FTS5 searches only ready sources in the selected workspace/scope, retrieves at most 30 candidates and chooses at most 12 excerpts while spreading them across sources. Unicode substring fallback supports CJK. Query and scope values use bound SQL parameters. Locators retain page, slide, heading, paragraph/table, module/item or caption timestamp. Citation validity means the ID belongs to the current retrieved context; readers should inspect the excerpt to judge whether an explanation is supported.

## Providers and grounding

OpenAI uses official Responses with `store=false`; Anthropic uses Messages; compatible gateways/local servers use Chat Completions. Redirects are not followed, environment proxies are not inherited and raw error bodies never cross the UI boundary. Models are explicitly configured. Streaming, native tools and native JSON Schema output are configurable; vision/embeddings are unavailable in the v3 text pipeline.

Native structured output uses the API's schema format and validates the complete application schema locally. Other models receive a JSON schema prompt. Malformed output can be repaired once; invalid citation IDs prevent saving an artifact. Authentication, quota and network failures do not trigger automatic retries. A generation can therefore use two provider calls. Automated contracts do not spend API credits.

Conversation history persists independently of the provider. Requests include at most 16 bounded recent messages and omit turns involving now-unselected sources or previously enabled live data when live tools are disabled. Earlier turns remain inspectable locally. Source selection cannot indirectly resend old grounded material through history.

The four versioned prompts treat sources and tool results as untrusted data, require supplied citation IDs and uncertainty, and prohibit invented submission states. Prompt filenames/version are saved in artifact provenance.

## Acceptance audit

The complete v3.0 implementation is on `feat/v3-web-phase-a`; the branch name records its starting phase. Phases A–G are implemented. Optional workspace MCP tools, semantic retrieval, FAQ/timeline/Mermaid generation and the explicitly excluded features remain outside this release.

| Definition-of-done item | Evidence |
| --- | --- |
| `canvas web` launches locally | Installed wheel starts the protected loopback API and serves bundled assets without Node |
| Existing CLI/MCP compatibility | Existing regression suite, lazy CLI imports, unchanged 45-tool registry and installed MCP command |
| No Canvas PAT | Real Chrome-session authentication returned HTTP 200 |
| Course dashboard | Real bounded course list and synthetic browser navigation |
| Persistent course workspace | Installed API creation; SQLite persistence and migration tests |
| Sync and select Canvas sources | Real page/file sync; canonical module inventory and frontend scope tests |
| PDF/HTML/DOCX/PPTX indexing | All four formats parsed through the installed API with locators |
| Configured streaming provider | Real TCP connection to an isolated compatible test gateway |
| Anthropic adapter | Messages HTTP contracts cover streaming, nonstreaming, tools and structured output |
| OpenAI adapter | Responses HTTP contracts cover streaming, nonstreaming, tools and structured output |
| Custom compatible endpoint | Installed runtime gateway covers connection test, chat and Studio |
| Clickable verified citations | Scope/ID validation, browser source inspection and real-source local citation smoke |
| Quiz | Installed generation/export and browser answer checking |
| Flashcards | Installed generation/export and card schema tests |
| Study guide | Installed generation/export and guide schema tests |
| Local notes | CRUD, saved answers, server-pinned artifact excerpts and SQLite persistence |
| Local artifacts | Stored structured content/provenance and scoped Markdown/JSON exports |
| No plaintext provider keys in SQLite | Keychain-only implementation and sentinel secret tests |
| No saved keys returned to frontend | Public configuration allowlist and sanitized validation/errors |
| No Canvas cookies returned to frontend | Shared in-memory Python auth; API/tool-result privacy tests |
| Loopback binding | Launcher socket tests and installed runtime |
| Server-side write confirmation | v2 argument/token binding, single use, cancellation, workspace scoping and browser confirm tests |
| Existing tests pass | Full Python suite includes unchanged v2 regressions |
| Credential-free v3 tests pass | Synthetic backend/provider/browser fixtures; isolated Chromium |
| Setup/MCP/privacy documentation | README and this implementation/verification record |

Adapter contract validation does not establish live access or quota for a particular OpenAI/Anthropic account. No paid API credentials were available for this validation; those account-specific live checks remain unperformed.

## Approval boundary

The assistant sees an allowlisted subset of v2 read tools and preview-only interaction tools. Course actions are pinned to the workspace course. There is no generic dispatcher for filesystem reads, assignment submission paths, schedules or confirmation tokens. Models without native tools use ordinary chat and explicit Canvas controls.

Previews hold the tool, exact arguments and v2 token in server memory. Only the authenticated, CSRF-protected human confirm route can consume one. Confirmation calls the original v2 handler with stored arguments. Edited payloads, invented model confirmation calls, foreign-workspace previews, cancellation, repeats and expiry are rejected. Tokens never reach the model/frontend or SQLite. v2 still enforces account/profile/target/payload binding. An ambiguous write requires checking Canvas before preparing another action.

## Packaging and storage

The `[web]` extra adds FastAPI/Uvicorn, HTTPX, keyring, pypdf, python-docx, python-pptx and multipart parsing. CLI/MCP imports do not import the web app. Wheels/source distributions include the compiled React/TypeScript/Vite UI, self-hosted font, dependency notices and four prompts. Build the UI before packaging. Node is needed to develop/build, not to run a wheel.

SQLite schema 4 transactionally extends Phase A. It stores sources/chunks/FTS, conversations/messages with source scope, artifacts/provenance, notes and nonsecret provider configuration plus a saved-key flag. No credential values are stored. Application/download paths are private and outside Git. Workspace deletion cascades rows and removes generated source directories. Exports contain private study material and must remain outside Git.

## Verification

Automated suites use synthetic course documents, mocked browser access and provider HTTP responses. Browser tests run in isolated Chromium and exercise desktop/mobile layout, provider setup, selected sync, streamed citations, source inspection, quiz answer checking, saved notes and a separate human confirmation. They make no actual Canvas write.

Validation on 2026-10-07:

- Python: **512 tests passed**, including existing CLI/MCP regression tests and new backend/provider contracts.
- Frontend: **22 tests passed**; TypeScript checking and production build passed.
- Browser: **6 isolated Playwright flows passed**; desktop/mobile screenshots were inspected, and mobile action spacing corrected.
- Ruff passed for the changed Python implementation and web tests. The repository's existing v2 style findings were not rewritten as part of v3.
- `npm audit --audit-level=low` reported **0 vulnerabilities**, including development dependencies.
- Wheel and source distribution contain the compiled UI, self-hosted fonts, dependency notices and versioned prompts; neither contains browser data, databases, environments or live test captures.
- Installed-wheel smoke ran outside the source checkout with Node absent from `PATH`. It served the UI, enforced local session/Host checks, created a course workspace, indexed four document formats, made five actual loopback provider HTTP calls, streamed valid citations, generated/exported all three artifact types, saved answers/excerpts and removed local source files when deleting the workspace.
- Real HKUST read smoke verified Chrome-session auth (**HTTP 200**), a bounded course list, course workspace creation, canonical source inventory, page/file sync and a citation stream through a temporary local synthetic gateway. The chosen course's empty syllabus correctly reported no extractable text. Submission-status, peer-review, Inbox and course-structure reads succeeded; bounded scans explicitly reported partial results where applicable.
- A real discussion write preview was prepared and cancelled. **No live Canvas write was confirmed.** All temporary real-course documents/index/history and preview records were removed after the smoke test. No real account, course identifiers or response bodies are committed.
- Git candidate files and distribution contents were reviewed for private paths, account identifiers, credential literals and runtime files; no such private data was found.

The real file smoke exposed two missing redirect hosts: Canvas browser-content and file-storage domains. The bounded downloader now accepts the documented HTTPS subdomains of `canvas-user-content.com` and `inscloudgate.net`, as well as its existing Canvas/Instructure/AWS hosts, while checking every redirect and removing Canvas CSRF headers on storage hosts. This follows [Instructure's domain documentation](https://community.instructure.com/en/kb/articles/485223-unknown). Requests remain limited to URLs returned by Canvas file metadata, HTTPS port 443, six hops and 25 MB; unrelated endpoints remain blocked.

Live cloud-provider tests require a configured key/model. HKUST read/sync requires a current Chrome login. The implementation does not automate SSO or perform unapproved live writes.

## API references

The adapters follow [OpenAI streaming](https://developers.openai.com/api/docs/guides/streaming-responses), [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming), [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) and [keyring system backends](https://keyring.readthedocs.io/en/latest/).


### Native-client setup verification

The follow-up provider setup work adds **Use existing login**, official CLI sign-in and native desktop handoffs. Codex uses app-server over stdio; Claude Code uses its documented noninteractive stream. Native adapter contracts use synthetic subprocesses and verify disabled tools/MCP, private inference input, final-answer filtering, streaming without duplicates, bounded output, cancellation/timeout cleanup and schema validation. Desktop configuration tests preserve other MCP entries and refuse malformed configuration. Login/connection routes require the normal local session and CSRF protection; no CLI tokens enter provider configuration or SQLite.

Real local Codex login, streamed text and JSON Schema generation passed with short generic prompts and no course data. Claude Code was detected but was not signed in, so real Claude inference is **not verified**; its setup presents the official login action. Standard Codex/Claude desktop apps were not installed on the test machine, so their native launch paths were tested with synthetic metadata and safe config fixtures, not live desktop accounts. One-click desktop discovery/configuration is macOS-specific; manual setup text and official guides remain available elsewhere.

The full regression suite also exposed a concurrent first-launch SQLite journal-mode lock race. Initialization now retries only SQLite busy/locked errors for a bounded ten seconds; concurrent migration coverage runs sixteen initializers. No Canvas write was performed by this provider follow-up.
