# Privacy

HKUST Canvas Workbench is designed as a local-first application. The project
does not operate a central application backend that receives your Canvas
session, course data, chats or AI-provider credentials. The application has
no built-in telemetry or remote crash reporting; its diagnostic logs stay local.

Canvas authentication is read from your selected, signed-in Chrome profile.
Canvas cookies and CSRF credentials remain on the local Python backend and
are not returned to the browser frontend or sent to AI providers. Canvas
requests and source downloads contact HKUST Canvas using your existing permissions.

Course/source data is stored and indexed locally, alongside saved conversations,
notes and generated materials. These files may contain private course or student
data; keep them out of Git and public issues.

When you send or generate with a cloud AI provider, that provider receives
your prompt, relevant conversation history and retrieved excerpts from selected
sources under its terms and privacy policy. The app does not automatically upload
the full course. Explicitly enabled live Canvas tools can also supply requested
Canvas results. Codex and Claude Code inference uses their respective services
through the installed CLI. Temporary chat does not change a provider's data policy.

Provider API keys use a supported system credential store with no plaintext
fallback. Stored credentials are not returned to the browser frontend or
committed to the repository. CLI adapters use the CLI's existing authentication
without copying its login tokens. A provider connection test sends a short prompt
and may use billing or account quota.

Local-model configurations can keep model processing on your computer when
the endpoint runs there. A remote compatible endpoint receives the same request
context; configuring an endpoint does not make it local.

RVC lecture recordings are transcribed only when you ask. The optional
transcriber is a separate open-source component that the app downloads from
GitHub at a pinned version and checks against a fixed hash. To get a
recording's stream link, the backend reads your Chrome cookie for
`rvcmedia.ust.hk`; the cookie and the short-lived stream link stay in the
backend and are not sent to AI providers. The component streams the
recording's audio from HKUST and transcribes it on your computer. Temporary
audio stays in the component's own folder, and the stream link file is deleted
after each run. The transcript is stored like any other local source.

Canvas write actions require explicit confirmation; external MCP access is
read-only by default. An external MCP client's handling of tool results and
conversation data is governed by that client's settings and policies.

Unlinking Canvas preserves Chrome login and saved study data. Disconnecting a
provider removes its app configuration and app-owned credential-store item,
without signing out external accounts or CLI logins. To remove saved study
data, follow the separate [uninstall steps](docs/user-guide.md#uninstall).

See [SECURITY.md](SECURITY.md) for technical safeguards and private vulnerability
reporting. You are responsible for following institutional policies, service
terms and restrictions on the materials you process or share with providers.
