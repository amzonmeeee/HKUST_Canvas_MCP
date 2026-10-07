# Security policy

## Supported versions

Security fixes target `main` and v3.0.0. Older version branches are not maintained separately. The first macOS artifacts are ad-hoc signed and not Apple-notarized.

## Threat model and machine boundary

The workbench is a single-user application on a trusted computer. Its Python backend binds to `127.0.0.1`; the local HTTP API checks the exact Host and Origin, requires a per-launch HttpOnly session and protects mutations with a separate CSRF token. It blocks cross-site requests and uses a restrictive Content Security Policy. It is not designed to be hosted publicly or shared between users. Local malware or another process running as your user can access your files and browser data; localhost protections do not replace operating-system security.

The web launcher prints a private, short-lived session link. Do not publish it or expose the server through a reverse proxy. MCP normally uses stdio; network MCP transports require their own secure deployment and are not a public multi-user service.

The desktop launcher keeps its session marker and readiness files in owner-only app-data folders instead of printing the link to logs. It authenticates an existing service before reusing it. A file lock prevents duplicate desktop backends; Quit stops only the launcher's owned process. The backend monitors its parent and stops when that launcher disappears. The browser UI and Python runtime are bundled; neither Chrome data nor user study data is included in release artifacts.

## Canvas authentication and unlinking

Authentication reads the selected Chrome profile's existing HKUST Canvas session. Cookies and Canvas CSRF credentials stay in Python/backend memory, not in the workspace database, model requests or web frontend. The application does not automate HKUST SSO or copy browser profiles.

Unlinking writes an explicit unconfigured marker in the shared profile settings. It blocks Canvas operations, including cached clients and explicit profile/environment overrides, until a profile is selected again. It clears pending web previews. It preserves Chrome profiles, cookies, browser login and cached workspace data. Removing cached workspace data is a separate action. Existing scheduled submissions cannot authenticate while unlinked; inspect scheduled-job status before reconnecting.

## Provider credentials and disconnecting

API keys are stored under `HKUST_Canvas_MCP.providers` in a supported system credential store, keyed by the app's generated provider ID. There is no plaintext fallback. Public provider responses expose only whether a key exists. Disconnect removes that provider configuration and only its app-owned credential item. A failed credential deletion leaves the configuration available for retry.

Native CLI adapters use the already-installed CLI's supported authentication. They do not copy CLI tokens, scrape consumer web sessions or delete external accounts/login data. Their inference requests disable inherited tools, MCP servers, hooks and plugins; unsupported CLI versions fail without falling back to unrestricted execution.

## Canvas writes

MCP defaults to read-only: mutation tools are hidden and their wrappers also reject calls. `--allow-writes` or `CANVAS_MCP_ALLOW_WRITES=1` enables them; `--read-only` overrides the environment opt-in. Invalid environment values fail closed. Generated client setups explicitly select read-only.

Opting in does not approve a write. The existing backend validates previews and confirmation tokens bound to the operation, content, account and Chrome profile, with expiration and single-use rules. External MCP clients and CLI users must obtain explicit human approval before confirming. A token validates a previewed action; it is not proof that a person read a conversation. In the web workbench, model tool schemas omit confirmation tokens and execution arguments; models can only propose previews. Human confirmation goes through the existing backend endpoint. Changing or unlinking the profile cancels pending web previews.

Verify submissions, grades and deadlines in Canvas. This project is not affiliated with or endorsed by HKUST, Instructure/Canvas or the supported AI providers.

## What leaves the machine

Canvas reads/writes contact `canvas.ust.hk`. Source extraction and indexing happen locally. When you send or generate, the configured AI endpoint receives your prompt, relevant conversation history and retrieved excerpts from selected sources. Explicitly enabled live tools can supply requested Canvas results. Cloud endpoints and remote compatible gateways receive this context; a local endpoint receives it on its configured machine. Provider connection tests send a short test prompt and may use billing/account quota. Temporary chat does not change what the provider receives.

Saved workspaces, source text, conversations, notes and exports may contain private course/student data. Keep them outside Git. Automated tests use synthetic data and mocked browser/network/provider interfaces rather than personal accounts.

## Reporting a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/amzonmeeee/HKUST_Canvas_MCP/security/advisories/new) when available. If the repository does not offer it, request a private contact channel in an issue without including vulnerability details.

Include the affected version, a minimal reproduction using synthetic data and the expected impact. Never attach Canvas cookies, CSRF/SSO tokens, API keys, Chrome profiles, Keychain exports, private course exports, session links or unredacted logs/debug dumps to public issues. Do not use another person's account or modify live coursework to demonstrate a vulnerability.
