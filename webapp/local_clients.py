"""Bounded native-client discovery and user-initiated desktop handoffs."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

from .native_providers import KINDS, find_cli
from .providers import ProviderError

APP_NAMES = {"codex": "Codex.app", "claude": "Claude.app"}


def desktop_path(kind):
    if sys.platform == "darwin":
        for root in (Path("/Applications"), Path.home() / "Applications"):
            candidate = root / APP_NAMES[kind]
            if candidate.is_dir():
                return candidate
    return None


def mcp_launcher(profile):
    command = Path(sys.executable).with_name("canvas-mcp")
    args = ["--transport", "stdio", "--no-banner"]
    if not command.is_file():
        command = Path(sys.executable)
        args = ["-c", "from mcp_entry import main; main()", *args]
    entry = {"command": str(command), "args": args}
    # Never forward cookies, tokens, arbitrary environment variables or profile paths.
    if profile and profile != "Selected by profile path":
        entry["env"] = {"CANVAS_CHROME_PROFILE": profile}
    return entry


def client_options(profile):
    launch = mcp_launcher(profile)
    command = shlex.join([launch["command"], *launch["args"]])
    env = launch.get("env", {})
    cli = []
    for kind, name in KINDS.items():
        try:
            binary = find_cli(kind)
        except ProviderError:
            binary = "codex" if kind == "codex" else "claude"
            available = False
        else:
            available = True
        login = [binary, "login"] if kind == "codex" else [binary, "auth", "login"]
        env_args = [
            arg for key, value in env.items() for arg in ("--env", f"{key}={value}")
        ]
        setup = (
            [
                binary,
                "mcp",
                "add",
                "hkust-canvas",
                *env_args,
                "--",
                launch["command"],
                *launch["args"],
            ]
            if kind == "codex"
            else [
                binary,
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "stdio",
                "hkust-canvas",
                *env_args,
                "--",
                launch["command"],
                *launch["args"],
            ]
        )
        cli.append(
            {
                "kind": kind,
                "name": name,
                "available": available,
                "login_command": shlex.join(login),
                "mcp_command": shlex.join(setup),
            }
        )
    return {
        "cli": cli,
        "desktop": [
            {
                "kind": kind,
                "name": "Codex app" if kind == "codex" else "Claude Desktop",
                "available": desktop_path(kind) is not None,
            }
            for kind in APP_NAMES
        ],
        "mcp_config": json.dumps({"mcpServers": {"hkust-canvas": launch}}, indent=2),
        "mcp_command": command,
        "can_open_login": sys.platform == "darwin",
    }


async def open_login(kind):
    binary = find_cli(kind)
    command = shlex.join(
        [binary, "login"] if kind == "codex" else [binary, "auth", "login"]
    )
    if sys.platform != "darwin":
        return {"opened": False, "command": command}
    # JSON quoted strings are valid AppleScript literals here. No user-supplied shell text.
    script = (
        'tell application "Terminal"\nactivate\ndo script '
        + json.dumps(command, ensure_ascii=False)
        + "\nend tell"
    )
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/osascript",
        "-e",
        script,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), 15)
    except TimeoutError:
        process.kill()
        await process.wait()
        return {"opened": False, "command": command}
    return {"opened": process.returncode == 0, "command": command}


async def open_desktop(kind):
    path = desktop_path(kind)
    if path is None:
        raise ProviderError(
            "desktop_missing",
            "This desktop app was not found. Install it, then refresh availability.",
            503,
        )
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/open",
        str(path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), 15)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise ProviderError(
            "desktop_unavailable", "Opening the desktop app timed out.", 504
        ) from exc
    if process.returncode:
        raise ProviderError(
            "desktop_unavailable",
            "The desktop app could not open. Open it from your applications folder.",
            503,
        )
    return {"opened": True}


async def connect_desktop(kind, profile):
    if desktop_path(kind) is None:
        raise ProviderError(
            "desktop_missing", "Install this desktop app before connecting Canvas.", 503
        )
    launch = mcp_launcher(profile)
    if kind == "codex":
        args = [find_cli("codex"), "mcp", "add", "hkust-canvas"]
        for key, value in launch.get("env", {}).items():
            args += ["--env", f"{key}={value}"]
        args += ["--", launch["command"], *launch["args"]]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(process.wait(), 20)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProviderError(
                "client_setup_failed",
                "Codex MCP setup timed out. Use the copied setup command.",
                504,
            ) from exc
        if process.returncode:
            raise ProviderError(
                "client_setup_failed",
                "Codex MCP setup failed. Use the copied setup command.",
            )
    else:
        path = (
            Path.home()
            / "Library/Application Support/Claude/claude_desktop_config.json"
        )
        # Merge one named entry. Never replace an unreadable or malformed configuration.
        try:
            if path.is_symlink() or (path.exists() and path.stat().st_size > 1_000_000):
                raise ValueError
            config = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(config, dict) or not isinstance(
                config.get("mcpServers", {}), dict
            ):
                raise TypeError
            config.setdefault("mcpServers", {})["hkust-canvas"] = launch
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".canvas-mcp-", dir=path.parent
            )
            try:
                with os.fdopen(descriptor, "w") as output:
                    json.dump(config, output, indent=2)
                    output.write("\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except (OSError, ValueError, TypeError) as exc:
            raise ProviderError(
                "client_setup_failed",
                "Claude Desktop configuration could not be updated safely. Use the copied MCP entry in Settings → Developer.",
            ) from exc
    return {"connected": True, "restart_required": True}
