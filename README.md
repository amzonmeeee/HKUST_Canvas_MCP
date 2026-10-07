# HKUST Canvas Workbench

**Your Canvas. Your AI.**

Study with your Canvas materials beside your conversation. Use Claude Code, Codex, official APIs or a local model, and keep your saved workspace on your computer.

![Selected sources, cited chat and practice quiz. All data is synthetic.](docs/images/workspace.png)

**[Download for macOS · Apple Silicon](https://github.com/amzonmeeee/HKUST_Canvas_MCP/releases/tag/v3.0.0)** · [Developer install](docs/development.md) · [Security policy](SECURITY.md)

The app includes its backend and browser UI: no Python, Node.js or repository clone needed. This first release is **ad-hoc signed and not notarized**. Read the opening instructions below before installing.

## What it does

- Open Canvas courses or create your own workspaces; archive and restore them.
- Select and sync sources, or add your own PDF, Word, PowerPoint, HTML, Markdown and text files.
- Ask questions with source citations; inspect supporting excerpts and open originals in Canvas.
- Make quizzes, flashcards, study guides, mind maps, slides, infographics, Word documents and spreadsheets. Save notes and export materials.
- Use saved or temporary conversations; save a temporary conversation when you want to keep it.
- Check current Canvas information and preview supported writes before confirming them.
- Access Canvas through the browser, CLI or an MCP client.

## Safety and privacy

**Your Canvas session stays local.** Cookies and CSRF credentials stay in the Python backend. They are never returned to the browser frontend or sent to AI providers. Sources are extracted and indexed locally.

When you send or generate, a cloud provider receives your prompt, relevant conversation history and retrieved excerpts from selected sources. Explicitly enabled live tools can also supply requested Canvas results. A local model receives the same context on its configured server. Temporary chat does not change a provider's data policy.

API keys use the system credential store with no plaintext fallback; stored keys are not returned to the frontend. Codex and Claude Code use their supported CLI login without copying authentication tokens. Connection tests send a short prompt and may use billing or account quota.

Canvas writes require an exact preview and explicit confirmation. **External MCP clients are read-only by default.** Enabling write tools does not approve an action; existing backend confirmation remains required. Verify important submissions, grades and deadlines in Canvas.

**Unlink Canvas profile** removes the shared workbench/CLI/MCP profile binding, cancels pending web previews and blocks Canvas access until explicit reconnection. It preserves Chrome profiles, cookies, browser login and saved study data. Environment overrides do not bypass unlinking. Existing scheduled submissions cannot authenticate while unlinked; inspect their status before reconnecting. **Disconnect provider** removes only the app's configuration and its own stored key, preserving external accounts and CLI login.

See [SECURITY.md](SECURITY.md) for the threat model and private reporting. Never attach cookies, tokens, keys, private exports or unredacted logs to public issues.

## Why this exists

Your course material should work with the models and clients you choose.

[HKGAI's official product description](https://www.hkgai.org/products) identifies HKLearn as powered by HKGAI V3, with Canvas import, source-linked answers and study outputs. That is a familiar NotebookLM-like study-workbench pattern. This project keeps the sources + conversation + study materials workflow while adding model choice, local ownership, open-source transparency and MCP interoperability.

Instead of being limited to the HKGAI V3 model offered through HKLearn, connect the tools you already use. This comparison concerns the published product description, not a claim about its underlying implementation or model ancestry.

## 60-second setup

1. Download the Apple Silicon `.dmg` from the [v3.0.0 release](https://github.com/amzonmeeee/HKUST_Canvas_MCP/releases/tag/v3.0.0). Open it and drag **HKUST Canvas Workbench.app** to Applications.
2. Open the app. It opens your default browser and keeps a Dock icon while the service runs.
3. Choose the Chrome profile you normally use for Canvas. Click **Check connection** and verify the account shown. If needed, open `canvas.ust.hk` in Chrome, sign in normally, then retry. The app does not automate SSO.
4. Connect an already signed-in Codex/Claude Code CLI, add an API/local provider, or **skip for now**. Review the sharing notice and finish setup.
5. Open a course, **Find course sources**, select and sync sources, choose a provider, then ask a question.

Change the Chrome profile, disconnect a provider or revisit setup in **Settings**. The dashboard also has **Configure Canvas**. Quit through the app menu or ⌘Q to stop the service; closing a browser tab leaves the app running. Reopening the app reuses its existing local service.

### Opening this first macOS release

This release has no Apple Developer ID signature or notarization. Download only from this repository's release page; compare its SHA-256 checksum with `SHA256SUMS` to verify the file.

If Gatekeeper blocks it, first try opening the app, then use **System Settings → Privacy & Security → Open Anyway** if you trust the download. Follow [Apple's opening guidance](https://support.apple.com/en-au/102445). Do not disable Gatekeeper globally. A managed Mac may need its administrator's approval.

## Screenshots

These demonstrations use synthetic courses, sources, users and model responses. They contain no student records or private course material.

**Dashboard — courses and saved workspaces**

![Demo courses and saved workspace](docs/images/dashboard.png)

**Provider setup — existing CLI login, API or local endpoint**

![Provider setup with synthetic configuration](docs/images/providers.png)

**Citation inspection — check the excerpt used in an answer**

![Answer and supporting source excerpt](docs/images/citation.png)

**Write safety — exact account, target and payload before confirmation**

![Synthetic Inbox reply preview; no real message was sent](docs/images/write-preview.png)

## AI providers and compatibility

| Component | Validation for this release |
| --- | --- |
| Apple Silicon macOS app | Built and smoke-tested on macOS 27.0.1; isolated HOME, native Quit, restart and singleton tests. No fresh VM or downloaded-file Gatekeeper test. |
| Chrome / multiple profiles | HKUST read/sync smoke during v3 development; synthetic connect, expiry, unlink and reconnect tests. Chrome must already be signed in. |
| Codex CLI | Real login, short streaming and structured output tested during v3 development; release CI uses synthetic adapters. |
| Claude Code CLI | Implemented and tested with synthetic adapters; real signed-in inference not verified. |
| Claude Desktop / Codex app | MCP configuration contracts tested; live desktop accounts not verified. Settings → MCP clients. |
| OpenAI / Anthropic API | Official streaming/tool/schema and failure contracts tested; paid-account access not verified. API billing is separate from a chat subscription. |
| Compatible API / Ollama / LM Studio | Compatible gateway smoke-tested over loopback. Configure model and endpoint; particular local model installations are not certified. |
| Windows / Linux | Python/developer route; no desktop installer or platform support claim yet. |

Choose the model identifier yourself. Local endpoints must already be running. Scanned PDFs need OCR elsewhere; v3 does not provide OCR, transcription or authenticated LTI/external-site extraction. Sync and parsing limits are in the [implementation reference](docs/v3-workbench.md).

## Claude, Codex and other MCP clients

In **Settings → MCP clients**, connect a detected desktop app or copy the setup/configuration. The macOS app supplies an absolute path to its bundled MCP executable, so no separate Python package installation is needed. Keep the app in a stable location before configuring clients.

Adding Canvas MCP makes Canvas tools available to that client. To chat **inside this workbench**, also choose a provider in the workspace; MCP configuration alone does not select a chat provider.

For a developer installation:

```sh
canvas-mcp --transport stdio --read-only
```

To opt into writes, deliberately replace `--read-only` with `--allow-writes`; read-only overrides an environment opt-in. Obtain human approval for each exact preview before using confirmation tools. The direct CLI retains its v2 preview/confirmation commands. See [developer setup](docs/development.md) and the [CLI reference](docs/cli.md).

<a id="install"></a>

## Installation options

- **macOS app:** download the DMG or zipped `.app`. Both include the frontend and Python runtime.
- **Python package:** release wheel and source distribution are available for developers. Install the wheel with its `[web]` extra in a virtual environment, then run `canvas web`. Node is needed only to rebuild the frontend.
- **Source checkout:** follow [developer installation](docs/development.md). [Release engineering](docs/releasing.md) describes the build and checks.

Updating the application preserves study data. Never replace or remove your data folder just to update the app.

## Troubleshooting

| Problem | Next step |
| --- | --- |
| No Canvas session / expired session | Sign in normally in Chrome, verify the profile, then Check connection. |
| Chrome asks for credential access | Allow only if you trust the app and selected profile. Recheck the account. |
| No provider in a workspace | Connect one in Settings, then choose it in the workspace. MCP setup is separate. |
| API connection fails | Check model, quota and credential. For local servers, check endpoint and running model. |
| App cannot start | Use Show logs / Retry / Quit. Share only redacted metadata, never session links. |
| Default port occupied | The launcher chooses a free loopback port. Do not expose it on your network. |
| Write result uncertain | Check Canvas before another preview. Confirmations are single-use; ambiguous writes are not retried automatically. |
| Older web build rejects database | Use v3.0.0; schema 6 preserves data but older builds cannot open it. |

## Uninstall

1. **Credentials:** disconnect API providers in Settings to remove only their app-owned credential-store items. This does not sign out CLI accounts.
2. **Canvas:** unlink if you want the shared CLI/MCP profile binding removed. Chrome login and browser data are unaffected.
3. **Application:** quit, then move the app to Trash. Remove its MCP entry from clients if configured.
4. **Study data, optional:** back up wanted work, then remove `~/Library/Application Support/HKUST_Canvas_MCP`. This permanently deletes sources, conversations, notes and artifacts, separately from removing the app or unlinking Canvas.
5. **Profile settings, optional:** the app-owned binding lives in `~/.config/canvasmcp/settings.json` (or under `XDG_CONFIG_HOME`), shared with CLI/MCP. Do not remove Chrome profiles or cookies.

If the app is already gone, its API credentials are system credential-store entries under `HKUST_Canvas_MCP.providers`, keyed by provider ID. Remove only those entries; never clear your whole Keychain. Launcher logs/session metadata are inside the app data folder.

## Roadmap

For v3.1 or later: read-only MCP access to saved workspaces, indexed sources, search and artifacts, so external agents can use the same materials as the browser. These tools are planned, not included in v3.0. Signing/notarization and broader platform testing are next steps.

## Original project and acknowledgements

Built on [ynbh/canvasmcp](https://github.com/ynbh/canvasmcp), independently maintained by amzonmeeee for HKUST Canvas. The original CLI, MCP tools, Chrome-session authentication and tests form the foundation; the original copyright notice remains in [LICENSE](LICENSE).

Thanks to [vishalsachdev/canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) for informing submission status, peer review, Inbox, discussion, comment, module completion and course structure workflows. These additions use Canvas's official APIs.

MIT licensed. This independent project is not affiliated with or endorsed by HKUST, Instructure, OpenAI, Anthropic or Google. It uses only the signed-in user's permissions; connected services remain subject to their terms and institutional policies.
