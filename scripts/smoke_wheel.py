"""Install a release wheel into a fresh venv and run outside the checkout."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def smoke(wheel, uv):
    wheel, uv = wheel.resolve(), Path(shutil.which(str(uv)) or uv).resolve()
    with tempfile.TemporaryDirectory(prefix="workbench-wheel-install-") as folder:
        root = Path(folder)
        environment = root / "venv"
        subprocess.run(
            [uv, "venv", "--python", sys.executable, environment], check=True
        )
        python = environment / "bin/python"
        subprocess.run(
            [uv, "pip", "install", "--python", python, str(wheel) + "[web]"], check=True
        )
        env = {
            "HOME": folder,
            "XDG_CONFIG_HOME": str(root / "config"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "TMPDIR": tempfile.gettempdir(),
            "CANVAS_MCP_ALLOW_WRITES": "false",
        }
        subprocess.run(
            [python, "-m", "webapp.desktop", "--self-test"],
            cwd=root,
            env=env,
            check=True,
            timeout=60,
        )
        for binary in ("canvas", "canvas-mcp"):
            result = subprocess.run(
                [environment / "bin" / binary, "--help"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                timeout=30,
            )
            assert result.stdout, f"Installed {binary} help missing"
    print(
        "Fresh wheel smoke passed: CLI/MCP help, frontend, onboarding, read-only MCP, isolated document parsing."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--uv", type=Path, default=Path("uv"))
    args = parser.parse_args()
    smoke(args.wheel, args.uv)
