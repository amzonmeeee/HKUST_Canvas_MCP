"""Test an installed app from an isolated home with no repository/Node on PATH."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def ready(path, process):
    deadline = time.monotonic() + 30
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    if not path.exists():
        raise RuntimeError("Packaged server did not become ready")
    return json.loads(path.read_text())


def stop(process):
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=10)


def smoke(app):
    app = app.resolve()
    backend = app / "Contents/Resources/backend/workbench-server"
    native = app / "Contents/MacOS/CanvasWorkbench"
    with tempfile.TemporaryDirectory(prefix="workbench-install-smoke-") as folder:
        root = Path(folder)
        env = {
            "HOME": folder,
            "XDG_CONFIG_HOME": str(root / "config"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "TMPDIR": tempfile.gettempdir(),
            "HKUST_WORKBENCH_DATA_DIR": str(root / "data"),
            "HKUST_WORKBENCH_PORT": "0",
        }
        subprocess.run([native, "--smoke"], env=env, cwd=root, check=True, timeout=60)
        subprocess.run(
            [native, "--lifecycle-smoke"], env=env, cwd=root, check=True, timeout=60
        )
        marker = root / "data/launcher/session.json"
        assert not marker.exists(), "Native quit left a session marker"
        command = [
            backend,
            "--data-dir",
            root / "data",
            "--port",
            "0",
            "--parent-pid",
            str(os.getpid()),
            "--ready-file",
        ]
        first = subprocess.Popen(
            [*command, root / "first.json"],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            state = ready(root / "first.json", first)
            assert state["owned"] is True
            second = subprocess.run(
                [*command, root / "second.json"],
                env=env,
                cwd=root,
                check=True,
                timeout=30,
                capture_output=True,
            )
            assert (
                second.returncode == 0
                and json.loads((root / "second.json").read_text())["owned"] is False
            )
            assert first.poll() is None
            url, token = state["url"].split("#session=")
            base = url.rstrip("/")
            browser = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

            def call(path, method="GET", body=None, csrf=None):
                headers = {"Origin": base, "Authorization": "Bearer " + token}
                if csrf:
                    headers["X-Workbench-CSRF"] = csrf
                if body is not None:
                    headers["Content-Type"] = "application/json"
                with browser.open(
                    Request(
                        base + path,
                        data=json.dumps(body).encode() if body is not None else None,
                        headers=headers,
                        method=method,
                    ),
                    timeout=5,
                ) as response:
                    return response.status, response.read()

            _, session = call("/api/session", "POST", {})
            csrf = json.loads(session)["csrf_token"]
            assert call("/")[0] == 200
            assert (
                json.loads(call("/api/onboarding", csrf=csrf)[1])["completed"] is False
            )
            _, workspace = call(
                "/api/workspaces",
                "POST",
                {"title": "Synthetic installed workspace"},
                csrf,
            )
            workspace_id = json.loads(workspace)["id"]
            assert (
                json.loads(call("/api/canvas/status", csrf=csrf)[1])["auth_status"]
                == "unconfigured"
            )
            try:
                call("/api/canvas/courses", csrf=csrf)
                raise AssertionError("Fresh app accessed Canvas without selection")
            except HTTPError as exc:
                assert exc.code == 409
        finally:
            stop(first)
        assert not marker.exists()
        third = subprocess.Popen(
            [*command, root / "third.json"],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            state = ready(root / "third.json", third)
            url, token = state["url"].split("#session=")
            base = url.rstrip("/")
            _, session = call("/api/session", "POST", {})
            csrf = json.loads(session)["csrf_token"]
            assert (
                json.loads(call("/api/workspaces/" + workspace_id, csrf=csrf)[1])[
                    "title"
                ]
                == "Synthetic installed workspace"
            )
        finally:
            stop(third)
    print(
        "Installed macOS smoke passed: native quit, singleton, static UI, fresh setup, persistence; no Node or repository runtime."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    smoke(parser.parse_args().app)
