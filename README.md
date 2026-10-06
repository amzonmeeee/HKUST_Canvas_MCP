# HKUST Canvas MCP

**Built for the delicate constitution of UST bb.**

Lecture notes, assignment deadlines, announcements, and one fewer tab to click. Access HKUST Canvas from your terminal or an MCP-compatible AI agent.

Authentication uses your existing **Chrome Canvas session**: sign in through Chrome, then let the local tools use that session.

- `canvas-mcp` — Canvas tools for MCP clients.
- `canvas` — the same tools in your terminal.
- `canvas web` — a local study workbench with sources, grounded chat and Study Studio.
- Courses, assignments, grades, announcements, discussions, pages, modules, and files.
- Submission/missing status, peer-review TODOs, Canvas Inbox, and module-to-item course trees.
- Preview and confirm discussion posts/replies, Inbox messages, submission comments, and module completion updates.
- Preview and confirm assignment submissions, with optional local scheduling on macOS.

Agent skill: [`skills/canvas-cli/SKILL.md`](skills/canvas-cli/SKILL.md). Full command table: [`docs/cli.md`](docs/cli.md).

## Install

Requires Python 3.11 or later, Chrome, and [`uv`](https://docs.astral.sh/uv/getting-started/installation/). The examples below use macOS/Linux shell syntax.

### Project-local virtual environment (recommended)

```bash
git clone https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
cd HKUST_Canvas_MCP
```

If `uv --version` reports command not found, you can keep uv in this project too:

```bash
curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$PWD/.venv/.uv" sh
export PATH="$PWD/.venv/.uv:$PATH"
```

This uses uv's [unmanaged installer](https://docs.astral.sh/uv/reference/installer/#unmanaged-installations), which leaves shell startup files alone. The `PATH` change applies to the current terminal session.

Keep the Python runtime, download cache, package, and dependencies inside `.venv`:

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.venv/.runtime"
export UV_CACHE_DIR="$PWD/.venv/.uv-cache"
uv python install 3.12 --no-bin
uv venv --allow-existing --python 3.12 .venv
uv sync --locked --no-editable --python .venv/bin/python
source .venv/bin/activate
canvas --help
```

The [Python installation directory](https://docs.astral.sh/uv/reference/environment/#uv_python_install_dir) is scoped to this project; `--no-bin` avoids adding a Python executable to the user bin directory. System Python is unchanged. `--no-editable` also avoids editable-import failures seen in iCloud-backed folders on macOS. After changing project code or updating the checkout, reinstall the project:

```bash
uv sync --locked --no-editable --reinstall-package hkust-canvas-mcp --python .venv/bin/python
```

In a new terminal, enter the project directory and run `source .venv/bin/activate` again. You can also use `.venv/bin/canvas` and `.venv/bin/canvas-mcp` directly without activating. If uv was installed locally, use `.venv/.uv/uv` for later sync commands and set the two storage variables above again to keep its downloads local. Run `deactivate` when finished. Avoid moving the checkout after creating `.venv`, since its executable paths are absolute.

### Optional: commands available outside the project

The package is named `hkust-canvas-mcp`; its commands are `canvas` and `canvas-mcp`. Use this alternative if you want commands on your user `PATH`. If you previously installed the original `canvasmcp` with `uv`, uninstall that tool first to avoid command-name conflicts.

```bash
uv tool install git+https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
canvas --help
```

Append `@main` or `@<tag-or-commit>` to the repository URL to select a revision.

## Local web workbench (v3.0)

Open a Canvas course as a persistent workspace, or create a custom workspace for your own materials. Select sources, sync them locally, ask questions with clickable citations, and generate quizzes, flashcards or study guides. Conversations, materials and notes are saved on this computer. The v2 CLI and MCP tools retain their authentication and confirmation flows.

### Start from a source checkout

Build the UI once with Node.js 22.12 or later, then install the optional web dependencies **inside your project environment**:

```bash
cd web
npm ci
npm run build
cd ..
uv sync --locked --extra web --no-editable --reinstall-package hkust-canvas-mcp --python .venv/bin/python
.venv/bin/canvas web
```

Use the project-local uv/runtime settings from the installation section. Rebuild and reinstall after changing the checkout. Release wheels include the compiled UI and prompts; running a wheel does not require Node. Building a wheel or source distribution requires `npm run build` first.

`canvas web` binds only to `127.0.0.1`, opens the browser after startup and prints a private launch URL. Keep its terminal open; Ctrl+C stops it. If port 8765 is occupied, it selects an unused port. Use the full printed link on first connection: its fragment establishes a local HttpOnly session and is removed from browser history. Restarting the server invalidates old sessions.

```bash
canvas web --no-open
canvas web --port 0 --data-dir /absolute/path/outside-the-repository
```

### First workspace

1. Sign in to HKUST Canvas in your selected Chrome profile. The dashboard shares the CLI/MCP profile setting; no Canvas PAT is needed. Use `canvas settings choose-profile "Your Chrome profile name"` to change it, then retry in the dashboard.
2. Open a course, or create a custom workspace. Existing workspaces and saved notes remain accessible while Canvas is offline.
3. Use **Find course sources** to list syllabus, modules and their items, pages, files, assignments, announcements and discussion topics. Listing does not download course files. Select sources and use **Sync selected**, or explicitly choose **Sync course**. **Refresh source** checks and rebuilds one source. Each source shows its own status and error.
4. Upload PDF, DOCX, PPTX, UTF-8 TXT/Markdown/HTML, VTT or SRT files, or use **Add text**. Parsing stays local. Files are limited to 25 MB, PDFs to 1,000 pages and extracted text to 2 million characters. Scanned PDFs need OCR outside this app. Videos and external/LTI tools remain references; upload captions to index video text. XLSX parsing, OCR and transcription are outside v3.0.
5. Select ready sources and a provider, then send a question. Click a citation to inspect its text and page, slide, heading or timestamp, or open its canonical Canvas page. Unchanged refreshes preserve citation IDs. Changed or removed sources retain saved citation excerpts; the current-version viewer explains when an old citation is unavailable.
6. Use **Study Studio** to choose material, topic, difficulty and item count. Generated items require valid source citations and are saved with provider/model, prompt version and source provenance. Quizzes support answer checking; cards reveal their backs. Export Markdown/JSON or save a material/answer as a local note.

### Providers

Add a provider in **Settings → Model providers**, enter a model identifier available to your account/server, save and use **Test connection**. The test sends only a short test prompt and may incur an API charge.

| Provider | Configuration | Credential |
| --- | --- | --- |
| OpenAI | Official Responses API; enter your model identifier | Official API key |
| Anthropic | Official Messages API; enter your model identifier | Official API key |
| OpenAI-compatible gateway | HTTPS base URL ending in `/v1`, plus model identifier | Optional API key |
| Ollama | `http://127.0.0.1:11434/v1`; start the server and pull a model first | Usually none |
| LM Studio | `http://127.0.0.1:1234/v1`; enable its local server and load a model | Usually none |

Enable streaming, native tool calling or native JSON Schema output only when the selected model/endpoint supports them. Without native tools, chat remains available and explicit **Live Canvas actions** still work. Studio validates JSON and citations in either mode and permits at most one JSON repair request. Provider rate limits and network failures are not automatically retried. Native schema support follows the provider's API; gateways vary.

Keys are stored through `keyring` in a supported system credential store: macOS Keychain, Windows Credential Locker, Secret Service or KWallet. There is no plaintext fallback. The UI shows whether a key is saved, never its value. Keyless local configurations do not access Keychain. Changing a configured endpoint requires removing its old key before saving another. A ChatGPT/Claude consumer subscription is separate from API billing; use the existing MCP server with your subscription's MCP-capable client if preferred. The app never reuses an AI website's browser cookies.

### Live Canvas actions and approval

Source-grounded chat treats downloaded documents as course evidence, not as current submission state. Enable **Allow live Canvas tools** for requested current-state checks when your model supports tools, or use **Live Canvas actions** directly without a provider.

Discussion posts/replies, Inbox sends/replies, comments on your own submission and module done/undo first produce a card showing the exact account, target, recipients and content. **Confirm Canvas write** performs the saved action through v2's server-side, single-use confirmation. Tokens never reach the model or frontend. Previews expire after ten minutes or server restart; cancellation performs no Canvas write. The model cannot call the confirmation endpoint. Check Canvas before retrying an ambiguous/disconnected write. Assignment submission and scheduling remain available through their existing v2 CLI/MCP workflows.

### Storage and privacy

Application data lives **outside Git**: `~/Library/Application Support/HKUST_Canvas_MCP/` on macOS, `$XDG_DATA_HOME/HKUST_Canvas_MCP/` (or `~/.local/share/...`) on Linux, and `%LOCALAPPDATA%/HKUST_Canvas_MCP/` on Windows. `app.db` holds workspaces, source metadata/chunks, conversations, notes, artifacts and nonsecret provider settings. Files are kept under `sources/<generated-id>/`; uploaded filenames cannot select filesystem paths. The directory/database/downloads have owner-only permissions where supported. Schema migrations preserve existing Phase A workspaces. `--data-dir` cannot point inside a Git checkout. Deleting a local workspace removes its local files/index and saved data, without deleting Canvas content.

Sending/generating shares the prompt and required retrieved excerpts from **selected ready sources** with the configured provider. Chat also includes recent compatible conversation history; earlier turns involving now-unselected sources or disabled live tools remain saved locally but are omitted from model context. Explicit live tools may supply requested Canvas results. Changing provider does not delete local history. Source selection is visible for each request; course files are not automatically sent wholesale. A local endpoint keeps inference on that server; a remote gateway receives the same context.

Canvas cookies and CSRF credentials remain in Python memory. They are never stored in the workspace database, exposed to the frontend or sent to an AI provider. The local API checks exact Host/Origin, requires the launch session, protects mutations with a separate web CSRF token, and exposes no arbitrary filesystem read or arbitrary source-fetch URL. Markdown does not render raw HTML or remote images. Logs contain operation metadata, not private message text, cookies, provider keys or authorization headers. Keep application data, exports, credentials and browser profiles out of Git.

### Development and verification

```bash
uv sync --locked --extra web --no-editable --reinstall-package hkust-canvas-mcp --python .venv/bin/python
.venv/bin/python -m pytest -q
cd web
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Automated provider contracts and browser tests use synthetic data and mocked HTTP; they need no Chrome session or paid API credentials. For hot reload, run the Python server on port 8765 with `--no-open`, run `npm run dev`, and open `http://127.0.0.1:5173/#session=THE_TOKEN_FROM_THE_PRINTED_LAUNCH_URL`. The fixed development proxy translates only this frontend Origin. Keep the token private. Production uses the Python-served compiled assets.

See [v3 implementation, requirements and verification](docs/v3-workbench.md) for the architecture, test evidence and live-test boundaries. [Phase A notes](docs/v3-phase-a.md) are retained as historical foundation documentation.

## Connect to HKUST Canvas

Open [canvas.ust.hk](https://canvas.ust.hk) in Chrome, complete your HKUST login, and make sure you can see your Canvas dashboard. Select that Chrome profile **before checking authentication**:

```bash
export CANVAS_CHROME_PROFILE="Your Chrome profile name"
canvas auth-status
canvas courses --all --limit 5
```

Replace the profile name with the display name in Chrome's profile menu, including spaces. Successful authentication reports `auth_status: verified` and `auth_verified: true`; JSON output also reports `probe_status: 200`. `auth-status` can exit successfully while reporting failed authentication, so check these fields too.

The Canvas address is fixed to `https://canvas.ust.hk`. `CANVAS_BASE_URL` does not change it. If the selected Chrome profile has no usable HKUST Canvas session, the tools report an error. Sessions for other schools are never selected as a fallback.

On macOS, allow the Keychain prompt when reading Chrome cookies. When the session expires, sign in again through Chrome and retry.

If you use multiple Chrome profiles, select the one signed in to HKUST Canvas:

```bash
canvas settings profiles
canvas settings choose-profile
```

For non-interactive use, supply the actual profile name: `canvas settings choose-profile "Your Chrome profile name"`. You can also set `CANVAS_CHROME_PROFILE` or `CANVAS_CHROME_PROFILE_PATH`. Environment selection takes precedence over saved settings; without a selection, the Chrome `Default` profile is used. An unknown profile name produces an error.

### macOS permissions and troubleshooting

If reading `~/Library/Application Support/Google/Chrome` fails with `Operation not permitted`, open **System Settings → Privacy & Security → Full Disk Access** and enable the app running the command. For commands launched from Terminal, enable **Terminal**; for an agent or MCP client, enable its host app. Use the **+** button if it is absent, then quit and reopen the affected app if requested. Full Disk Access permits access to other apps' data; see [Apple's permissions guide](https://support.apple.com/guide/mac-help/mchl211c911f/mac).

Chrome cookie decryption may separately show a **Chrome Safe Storage** Keychain prompt. Enter your Mac login password and choose **Allow**. Then rerun `canvas auth-status`.

- **`canvas: command not found`:** activate `.venv`, or use `.venv/bin/canvas` from the project directory.
- **`ModuleNotFoundError: canvas_cli`:** rerun `uv sync --locked --no-editable --python .venv/bin/python`. On macOS, hidden `.pth` files in an iCloud-backed `.venv` can prevent editable packages from loading.
- **Profile cannot be resolved:** check the exact display name in Chrome, or set `CANVAS_CHROME_PROFILE_PATH` to the profile directory shown by `chrome://version` in the signed-in profile.
- **No cookies or authentication not verified:** open Canvas in the selected Chrome profile, complete login, refresh the dashboard, and retry. If inspection itself fails, resolve macOS permissions first.
- **Terminal works, MCP fails:** use the absolute executable path and explicitly set the profile in the MCP client's configuration below.

### Read-only smoke test

With the virtual environment active and the Chrome profile selected, run:

```bash
canvas auth-status
canvas courses --all --limit 5
canvas todo
canvas resolve "COMP"
```

`courses` should return courses you can access. `todo` may be empty. `resolve` searches favorites by default; if it finds nothing, try `canvas resolve "COMP" --all` or a course code from your own course list. No matches is a valid result.

For the URL check, open an assignment you can access in Chrome and copy its actual `https://canvas.ust.hk/courses/.../assignments/...` URL. Paste it into this prompt:

```bash
read -r CANVAS_SMOKE_ASSIGNMENT_URL
canvas url "$CANVAS_SMOKE_ASSIGNMENT_URL"
```

In JSON output (`canvas --output json url "$CANVAS_SMOKE_ASSIGNMENT_URL"`), check that `resource_type` is `assignment`, `details` contains the assignment, and `detail_error` is null. A zero exit code alone does not prove the details were fetched. These checks only read Canvas data.

### Keep personal data out of Git

Commit source code, synthetic tests, and configuration examples with placeholders. Keep Chrome profiles, cookies, SSO tokens, Keychain exports, personal profile settings, student/course exports, and live smoke-test or debug output on your machine. `.gitignore` excludes common locations and formats for these files; it does not remove files already tracked or secrets pasted into source files.

Authentication reads Chrome cookies into memory. Saved settings contain your profile name/path, and scheduled submission records contain course/assignment information and the profile path. Their default locations are outside the checkout. If you override their locations, use an ignored directory such as `data/`. Never include actual authentication or Canvas responses in test fixtures or documentation.

The new interaction confirmations store only a request/account fingerprint and expiry under `~/Library/Application Support/canvasmcp/write-confirmations/`, with private directory/file permissions. They do not store message bodies, recipient lists, cookies or profile paths. `CANVASMCP_CONFIRMATION_DIR` can override this location; choose a private directory outside Git or the ignored `data/` directory. Command output can contain personal Canvas data and confirmation tokens, so keep captured output private.

Before publishing, review `git status --short`, `git diff --cached`, and `git log origin/main..HEAD`. Check commit author/committer metadata too: use your public GitHub identity and a GitHub noreply email if you want to keep your personal name/email private. Deleting a file in a later commit does not remove it from earlier history.

## MCP setup

For the project-local installation, add this configuration to your MCP client. Replace `/absolute/path/HKUST_Canvas_MCP` with your checkout's absolute path and the profile name with your own. Keep paths containing spaces as one JSON string. To obtain the executable path, run `pwd` from the project directory and append `/.venv/bin/canvas-mcp`.

```json
{
  "mcpServers": {
    "hkust-canvas": {
      "command": "/absolute/path/HKUST_Canvas_MCP/.venv/bin/canvas-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "CANVAS_CHROME_PROFILE": "Your Chrome profile name"
      }
    }
  }
}
```

For the optional uv tool installation, use the absolute `canvas-mcp` executable path reported by `command -v canvas-mcp`. You can use `CANVAS_CHROME_PROFILE_PATH` instead of the profile name. Restart or reconnect the MCP client after changing its configuration; terminal activation and exports may not carry over to a desktop client.

You can also start the server manually:

```bash
canvas-mcp --transport stdio
canvas-mcp --transport http --host 127.0.0.1 --port 8000
```

## CLI examples

Find your courses and pending work:

```bash
canvas courses --all
canvas resolve "COMP1021" --all
canvas todo
```

Replace the example course ID `12345` and assignment ID `67890` with your actual IDs:

```bash
canvas course context 12345
canvas assignments list 12345 --bucket upcoming
canvas assignments show 12345 67890 --include-submission
canvas files list 12345
canvas url "https://canvas.ust.hk/courses/12345/assignments/67890"
```

Use `canvas --help` and each subcommand's `--help` for flags. Raw tools are available through `canvas tool list` and `canvas tool run <name> --args '{...}'`.

## Submission status, peer reviews, Inbox and course structure

These commands read Canvas without submitting work, posting content or changing Inbox/module state:

```bash
canvas submissions --course 12345
canvas submissions --course 12345 --missing
canvas submissions --course 12345 --status overdue
canvas peer-reviews todo --course 12345
canvas peer-reviews todo --course 12345 --assignment 67890
canvas inbox list --scope unread --limit 5
canvas inbox show 24680 --limit 20
canvas course structure 12345 --modules-limit 100 --items-limit 100
canvas course module-items 12345 13579
```

Omit `--course` from `submissions` or `peer-reviews todo` to scan active **student** enrollments, including courses outside favorites. The default scan covers 30 courses and 100 assignments per course. Peer reviews also inspect up to 100 reviews per assignment and 300 Planner records; other Planner item types count against that limit. Increase the corresponding `--courses-limit`, `--assignments-limit`, `--reviews-limit` or `--planner-limit` flags if needed (maximum 300 each). Output limits are separate from scan limits. JSON reports `partial`, `truncated` and `warnings` where applicable; an empty partial scan does not establish that you have no pending work.

Submission status distinguishes Canvas-marked `missing` from `overdue` inferred using your effective deadline, and includes submitted, graded, excused, unsubmitted, external-tool, not-required, unpublished and unknown states. External services such as Gradescope can have work that Canvas reports as unsubmitted: check that service rather than treating it as missing. Status counts describe the scanned assignments before output filtering.

Peer-review TODOs merge assignment-level reviews with the Planner's `assessment_request` items, filter assignment reviews to your assessor ID, remove completed reviews and deduplicate findings. A known assignment can be checked directly even when its listing lacks the `peer_reviews` flag. Permission failures are reported alongside any available findings. Reviewee names are omitted to preserve anonymous-review settings.

Inbox reads use `auto_mark_as_read=false`. The course structure fetches each module's canonical item list, including links, content details, prerequisites and completion requirements. It reports item-list failures and truncation; resources outside modules and content Canvas hides from your account are not included.

## Preview and confirm interactions

All the following commands **preview only** when `--confirm` is omitted. The example IDs and content are synthetic; replace them with the intended targets. Discussion posting means an entry in an existing topic; assignment comments are on your own submission.

```bash
canvas discussion post 12345 24680 --message '<p>My discussion post.</p>'
canvas discussion reply 12345 24680 35790 --message '<p>My reply.</p>'
canvas assignments submissions comment 12345 67890 --comment 'My submission comment.'
canvas inbox send --to 45670 --subject 'Question' --body 'My message.' --course 12345
canvas inbox reply 24680 --body 'My reply.'
canvas inbox update 24680 --state archived
canvas course module-done 12345 13579 35790
canvas course module-done 12345 13579 35790 --undo
```

Review the displayed account, target, recipients and exact payload. To execute, repeat the **same command and arguments** with `--confirm '<confirmation_token>'` from that preview. Tokens expire after 10 minutes, are single-use across CLI/MCP processes, and are bound to the account, Chrome profile, target and content. For MCP, repeat the same tool call with `confirmation_token` only after explicit user approval; the token itself is not proof of human approval. Pretty previews display the raw payload so HTML cannot hide part of the proposed content. Obtain recipient IDs from `canvas course people COURSE`; `--to` accepts Canvas user IDs, not names or emails. Multiple recipients receive individual conversations by default; `--group` makes a shared conversation.

Canvas can reuse an existing private conversation when sending to the same recipient, in which case it ignores the proposed subject. Replies use the conversation's audience, rather than the authors of forwarded messages, and pin those recipient IDs in the confirmed request.

Failed confirmed writes consume their token and are not retried automatically: check Canvas before starting a new preview, because a connection failure can occur after delivery. Module completion only supports an accessible `must_mark_done` item and reads back its state after the write. Already-completed items do not trigger a new write. Inbox state changes support `read`, `unread` and `archived`.

Discussion previews respect Canvas's explicit `permissions.reply` value. An instructor or owner may be allowed to reply to an unpublished or closed topic; posting through this tool does not publish or unlock that topic. Without explicit permission, locked or unpublished discussions remain blocked.

## Scheduled submissions

A successful preview records the HKUST Canvas address and the absolute Chrome profile path. Confirmation, file upload, scheduled execution, and cancellation cleanup use that saved context, even if you later change your profile settings.

Cookies and CSRF tokens are not saved in previews or jobs. They are read again from the original Chrome profile when needed. If that profile's HKUST session expires, scheduled execution reports `auth_failed`. Existing previews or jobs without saved Canvas/profile context must be recreated before they can submit.

Scheduling uses macOS `launchd`. The machine must be running and awake at the scheduled time; confirmation supports `--caffeinate` to keep it awake.

## Output

Terminal output uses readable views; redirected or piped output defaults to compact JSON. Global output options go before the subcommand:

```bash
canvas --output pretty assignments submissions scheduled
canvas --output json courses
export CANVAS_OUTPUT=json
```

`--output auto|pretty|json` overrides `CANVAS_OUTPUT`. Raw `tool` commands and internal scheduler execution default to JSON. JSON preserves the full response; pretty views mark omitted routine metadata.

Operational errors use structured JSON on stdout in JSON mode and readable diagnostics on stderr in pretty mode. Refused previews exit 1; invalid tool arguments exit 2. Auth-status and settings inspection report their status without failing the command. Framework help and option parsing errors retain Typer's text format. JSON profile selection requires an explicit name and never prompts.

## Development and tests

```bash
git clone https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
cd HKUST_Canvas_MCP
uv sync --locked --no-editable
.venv/bin/canvas --help
.venv/bin/python -m pytest
```

The Chrome-cookie adapter, Canvas SDK, and FastMCP versions are pinned to the versions in the existing lockfile. Regression tests exercise the real Canvas SDK's session injection, cookie refresh, CSRF decoding, and saved submission context. Tests mock browser access and HTTP requests; use the read-only smoke test above to verify your real Chrome session. For editable development in a folder without the hidden-file issue, use `uv sync --locked`; source changes then take effect without reinstalling.

## Original project and acknowledgements

This project builds on [ynbh/canvasmcp](https://github.com/ynbh/canvasmcp) and is independently maintained by amzonmeeee for HKUST Canvas.

Thanks to the original author for the Canvas CLI, MCP tools, Chrome-session authentication, and test foundation. The original project uses the MIT License; its copyright notice is retained in [LICENSE](LICENSE).

Thanks also to [vishalsachdev/canvas-mcp](https://github.com/vishalsachdev/canvas-mcp) for informing the additional student workflows: submission status, peer-review TODOs, Inbox, discussion posts/replies, submission comments, module completion and course structure. These features were implemented against Canvas's official APIs: [submissions](https://canvas.instructure.com/doc/api/submissions.html), [peer reviews](https://canvas.instructure.com/doc/api/peer_reviews.html), [Planner](https://canvas.instructure.com/doc/api/planner.html), [conversations](https://canvas.instructure.com/doc/api/conversations.html), [discussions](https://canvas.instructure.com/doc/api/discussion_topics.html) and [modules](https://canvas.instructure.com/doc/api/modules.html).
