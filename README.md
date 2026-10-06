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

Requires Python 3.11 or later and `uv`.

The package is named `hkust-canvas-mcp`; its commands are `canvas` and `canvas-mcp`. If you previously installed the original `canvasmcp` with `uv`, run `uv tool uninstall canvasmcp` before installing this project to avoid command-name conflicts.

```bash
uv tool install git+https://github.com/amzonmeeee/HKUST_Canvas_MCP.git
canvas --help
```

Append `@main` or `@<tag-or-commit>` to the repository URL to select a revision.

## Connect to HKUST Canvas

Open [canvas.ust.hk](https://canvas.ust.hk) in Chrome, complete your HKUST login, and make sure you can see your Canvas dashboard. Then run:

```bash
canvas auth-status
canvas courses --all --limit 5
```

The Canvas address is fixed to `https://canvas.ust.hk`. `CANVAS_BASE_URL` does not change it. If the selected Chrome profile has no usable HKUST Canvas session, the tools report an error. Sessions for other schools are never selected as a fallback.

On macOS, allow the Keychain prompt when reading Chrome cookies. When the session expires, sign in again through Chrome and retry.

If you use multiple Chrome profiles, select the one signed in to HKUST Canvas:

```bash
canvas settings profiles
canvas settings choose-profile
```

For non-interactive use, supply the actual profile name: `canvas settings choose-profile "Your Chrome profile name"`. You can also set `CANVAS_CHROME_PROFILE` or `CANVAS_CHROME_PROFILE_PATH`. Environment selection takes precedence over saved settings; without a selection, the Chrome `Default` profile is used. An unknown profile name produces an error.

## MCP setup

Add this configuration to your MCP client:

```json
{
  "mcpServers": {
    "hkust-canvas": {
      "command": "canvas-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

To select a Chrome profile for the MCP server, add an `env` object with `CANVAS_CHROME_PROFILE` set to your actual profile name, or `CANVAS_CHROME_PROFILE_PATH` set to its absolute path.

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
uv sync --locked
uv run canvas --help
uv run pytest
```

The Chrome-cookie adapter, Canvas SDK, and FastMCP versions are pinned to the versions in the existing lockfile. Regression tests exercise the real Canvas SDK's session injection, cookie refresh, CSRF decoding, and saved submission context. Tests mock browser access and HTTP requests.

## Original project and acknowledgements

This project builds on [ynbh/canvasmcp](https://github.com/ynbh/canvasmcp) and is independently maintained by amzonmeeee for HKUST Canvas.

Thanks to the original author for the Canvas CLI, MCP tools, Chrome-session authentication, and test foundation. The original project uses the MIT License; its copyright notice is retained in [LICENSE](LICENSE).
