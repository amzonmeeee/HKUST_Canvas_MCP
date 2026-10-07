import json
import os
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

from webapp.desktop import verified_session, write_private_json


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8765/#session=" + "a" * 43,
        "http://example.com:8765/#session=" + "a" * 43,
        "http://user@127.0.0.1:8765/#session=" + "a" * 43,
        "http://127.0.0.1:8765/evil#session=" + "a" * 43,
        "http://127.0.0.1:8765/?query=x#session=" + "a" * 43,
        "http://127.0.0.1:8765/#session=short",
    ],
)
def test_session_marker_rejects_untrusted_targets(tmp_path, monkeypatch, url):
    marker = tmp_path / "session.json"
    marker.write_text(json.dumps({"url": url}))
    transport = Mock(side_effect=AssertionError("Must not contact untrusted targets"))
    monkeypatch.setattr("webapp.desktop.urlopen", transport)
    assert verified_session(marker) is None
    transport.assert_not_called()


def test_private_state_is_owner_only(tmp_path):
    marker = tmp_path / "state" / "ready.json"
    write_private_json(marker, {"owned": True})
    assert marker.stat().st_mode & 0o777 == 0o600
    assert marker.parent.stat().st_mode & 0o777 == 0o700
    assert json.loads(marker.read_text()) == {"owned": True}
    assert list(marker.parent.iterdir()) == [marker]


def test_frozen_mcp_uses_bundled_executable_and_read_only(monkeypatch):
    from webapp.local_clients import mcp_launcher

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    result = mcp_launcher("Synthetic profile")
    assert result["command"] == sys.executable
    assert result["args"] == [
        "--mcp",
        "--transport",
        "stdio",
        "--no-banner",
        "--read-only",
    ]
    assert result["env"] == {"CANVAS_CHROME_PROFILE": "Synthetic profile"}


def test_frozen_schedule_uses_bundled_cli(tmp_path, monkeypatch):
    import plistlib

    from schedule.launchd import write_plist

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("CANVASMCP_LAUNCH_AGENTS_DIR", str(tmp_path))
    monkeypatch.delenv("CANVASMCP_CANVAS_BIN", raising=False)
    path = write_plist("synthetic-job", "2030-01-01T12:00:00+08:00")
    assert plistlib.loads(path.read_bytes())["ProgramArguments"] == [
        sys.executable,
        "--cli",
        "scheduled",
        "fire",
        "synthetic-job",
    ]


def test_desktop_reuses_owner_and_cleans_up_on_exit(tmp_path):
    # Real loopback subprocesses, isolated HOME and app data; no browser/Canvas/provider calls.
    ready = tmp_path / "first.json"
    marker = tmp_path / "data/launcher/session.json"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "CANVAS_MCP_ALLOW_WRITES": "false",
    }
    command = [
        sys.executable,
        "-m",
        "webapp.desktop",
        "--port",
        "0",
        "--data-dir",
        str(tmp_path / "data"),
        "--parent-pid",
        str(os.getpid()),
        "--ready-file",
    ]
    owner = subprocess.Popen(
        [*command, str(ready)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while (
            not ready.exists() and owner.poll() is None and time.monotonic() < deadline
        ):
            time.sleep(0.05)
        assert ready.exists(), "Owned backend did not start"
        assert json.loads(ready.read_text())["owned"] is True
        assert verified_session(marker) is not None
        other_ready = tmp_path / "second.json"
        duplicate = subprocess.run(
            [*command, str(other_ready)],
            env=env,
            timeout=15,
            capture_output=True,
            check=False,
        )
        assert duplicate.returncode == 0, "Duplicate launcher failed"
        assert json.loads(other_ready.read_text())["owned"] is False
        assert owner.poll() is None, "Duplicate launcher stopped the original server"
    finally:
        if owner.poll() is None:
            owner.terminate()
        owner.wait(timeout=10)
    assert not marker.exists()
    assert verified_session(ready) is None


def test_backend_exits_when_its_launcher_disappears(tmp_path):
    ready = tmp_path / "ready.json"
    script = """import subprocess, sys, os, time
child = subprocess.Popen([sys.executable, '-m', 'webapp.desktop', '--port', '0', '--data-dir', sys.argv[1], '--ready-file', sys.argv[2], '--parent-pid', str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
from pathlib import Path
deadline = time.monotonic() + 20
while not Path(sys.argv[2]).exists() and child.poll() is None and time.monotonic() < deadline:
    time.sleep(0.05)
if not Path(sys.argv[2]).exists():
    child.terminate(); child.wait(); sys.exit(1)
"""
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "data"), str(ready)],
        check=True,
        env=env,
        timeout=25,
    )
    marker = tmp_path / "data/launcher/session.json"
    deadline = time.monotonic() + 10
    while marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not marker.exists(), "Backend outlived its launcher"
    assert verified_session(ready) is None
