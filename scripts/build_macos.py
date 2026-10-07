"""Build a self-contained native launcher + Python backend from whitelisted source."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def build(output: Path):
    if sys.platform != "darwin":
        raise SystemExit("Build macOS artifacts on macOS.")
    if not (ROOT / "webapp/static/index.html").is_file():
        raise SystemExit(
            "Build the production frontend first: cd web && npm ci && npm run build"
        )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    version = "3.0.0" if version == "3.0" else version
    arch = platform.machine()
    app = output / "HKUST Canvas Workbench.app"
    if app.exists():
        raise SystemExit(
            "Choose an empty output directory; existing app artifacts are preserved."
        )
    with tempfile.TemporaryDirectory(
        prefix="workbench-build-", dir=output.parent
    ) as temporary:
        stage = Path(temporary) / "source"
        stage.mkdir()
        for name in (
            "auth",
            "client",
            "cli",
            "specs",
            "tools",
            "schedule",
            "canvas_mcp",
            "webapp",
            "desktop",
        ):
            shutil.copytree(
                ROOT / name,
                stage / name,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "*.log", "*.db", "*.sqlite*"
                ),
            )
        for name in ("canvas_cli.py", "mcp_entry.py"):
            shutil.copy2(ROOT / name, stage / name)
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--name",
            "workbench-server",
            "--onedir",
            "--paths",
            str(stage),
            "--distpath",
            str(Path(temporary) / "dist"),
            "--workpath",
            str(Path(temporary) / "build"),
            "--specpath",
            temporary,
            "--add-data",
            f"{stage / 'webapp/static'}:webapp/static",
            "--add-data",
            f"{stage / 'webapp/prompts'}:webapp/prompts",
            "--collect-all",
            "fastmcp",
            "--collect-all",
            "keyring",
            "--collect-all",
            "jaraco",
            "--collect-all",
            "uvicorn",
            "--copy-metadata",
            "hkust-canvas-mcp",
            "--exclude-module",
            "pytest",
            str(stage / "desktop/backend_entry.py"),
        ]
        run(
            *command,
            cwd=stage,
            env={
                **os.environ,
                "PYINSTALLER_CONFIG_DIR": str(Path(temporary) / "cache"),
            },
        )
        macos, resources = app / "Contents/MacOS", app / "Contents/Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        shutil.copytree(
            Path(temporary) / "dist/workbench-server", resources / "backend"
        )
        # Build provenance can contain the builder's local repository path.
        # It is not needed to run installed packages and must not ship.
        for provenance in (resources / "backend").rglob("direct_url.json"):
            provenance.unlink()
        run(
            "swiftc",
            "-O",
            "-module-cache-path",
            Path(temporary) / "swift-cache",
            stage / "desktop/Launcher.swift",
            "-o",
            macos / "CanvasWorkbench",
        )
        run(
            "swiftc",
            "-O",
            "-module-cache-path",
            Path(temporary) / "swift-cache",
            stage / "desktop/Icon.swift",
            "-o",
            Path(temporary) / "render-icon",
        )
        run(Path(temporary) / "render-icon", Path(temporary) / "Workbench.iconset")
        run(
            "iconutil",
            "-c",
            "icns",
            Path(temporary) / "Workbench.iconset",
            "-o",
            resources / "Workbench.icns",
        )
        with (app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(
                {
                    "CFBundleIdentifier": "io.github.amzonmeeee.canvas-workbench",
                    "CFBundleName": "HKUST Canvas Workbench",
                    "CFBundleDisplayName": "HKUST Canvas Workbench",
                    "CFBundleExecutable": "CanvasWorkbench",
                    "CFBundlePackageType": "APPL",
                    "CFBundleShortVersionString": version,
                    "CFBundleVersion": version,
                    "CFBundleIconFile": "Workbench.icns",
                    "LSMinimumSystemVersion": "13.0",
                    "NSHighResolutionCapable": True,
                },
                stream,
            )
        for name in ("LICENSE", "SECURITY.md"):
            shutil.copy2(ROOT / name, resources / name)
        identity = os.environ.get("MACOS_SIGNING_IDENTITY", "-")
        run(
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--sign",
            identity,
            app,
        )
        run("codesign", "--verify", "--deep", "--strict", app)
        fresh_home = Path(temporary) / "fresh-home"
        fresh_home.mkdir()
        run(
            macos / "CanvasWorkbench",
            "--smoke",
            cwd=temporary,
            env={
                "HOME": str(fresh_home),
                "XDG_CONFIG_HOME": str(fresh_home / "config"),
                "XDG_DATA_HOME": str(fresh_home / "data"),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "TMPDIR": tempfile.gettempdir(),
            },
        )
        zip_path = output / f"HKUST-Canvas-Workbench-{version}-macOS-{arch}.zip"
        run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, zip_path)
        dmg = output / f"HKUST-Canvas-Workbench-{version}-macOS-{arch}.dmg"
        image = Path(temporary) / "image"
        image.mkdir()
        shutil.copytree(app, image / app.name, symlinks=True)
        (image / "Applications").symlink_to("/Applications")
        run(
            "hdiutil",
            "create",
            "-volname",
            "HKUST Canvas Workbench",
            "-srcfolder",
            image,
            "-ov",
            "-format",
            "UDZO",
            dmg,
        )
        profile = os.environ.get("MACOS_NOTARY_PROFILE")
        if profile and identity != "-":
            run(
                "xcrun",
                "notarytool",
                "submit",
                dmg,
                "--keychain-profile",
                profile,
                "--wait",
            )
            run("xcrun", "stapler", "staple", dmg)
        print(
            f"Built macOS {arch}; signing={'ad-hoc (not notarized)' if identity == '-' else 'Developer ID'}."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist/macos")
    build(parser.parse_args().output)
