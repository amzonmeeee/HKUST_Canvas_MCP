# HKUST Canvas MCP

**Built for the delicate constitution of UST bb.**

Lecture notes, assignment deadlines, announcements, and one fewer tab to click. Access HKUST Canvas from your terminal or an MCP-compatible AI agent.

Independently maintained by [amzonmeeee](https://github.com/amzonmeeee), based on [ynbh/canvasmcp](https://github.com/ynbh/canvasmcp). Authentication uses your existing **Chrome Canvas session**: sign in through Chrome, then let the local tools use that session.

- `canvas-mcp` — Canvas tools for MCP clients.
- `canvas` — the same tools in your terminal.
- Courses, assignments, grades, announcements, discussions, pages, modules, and files.
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
