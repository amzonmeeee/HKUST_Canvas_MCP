"""Inspect archives for runtime/user files and require frontend and prompts."""

from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def audit(folder):
    archives = sorted(
        [*folder.glob("*.whl"), *folder.glob("*.tar.gz"), *folder.glob("*.zip")]
    )
    assert archives, "No release archives found"
    for archive in archives:
        if archive.name.endswith(".tar.gz"):
            with tarfile.open(archive) as handle:
                names = handle.getnames()
        else:
            with zipfile.ZipFile(archive) as handle:
                names = handle.namelist()
        for name in names:
            parts = PurePosixPath(name).parts
            assert not (name.startswith("/") or ".." in parts), "Unsafe archive path"
            assert not set(parts).intersection(
                {
                    ".git",
                    ".venv",
                    "node_modules",
                    "smoke-results",
                    "debug-dumps",
                    "browser-profiles",
                    "Chrome",
                    "Cookies",
                    "Login Data",
                }
            ), f"Private/runtime path in {archive.name}: {name}"
            assert not re.search(
                r"(?:^|/)(?:\.env(?:\.[^/]*)?|session[^/]*\.json|cookies[^/]*\.(?:json|txt)|direct_url\.json)$|\.(?:sqlite3?|db|keychain|p12|pfx|log|har)$",
                name,
                re.IGNORECASE,
            ), f"Private/runtime file in {archive.name}: {name}"
        assert any("webapp/static/index.html" in name for name in names), (
            f"Frontend missing: {archive.name}"
        )
        assert any("webapp/prompts/chat_v1.md" in name for name in names), (
            f"Prompts missing: {archive.name}"
        )
        print(f"Archive audit passed: {archive.name} ({len(names)} entries)")


def checksums(folder):
    files = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    lines = []
    for path in files:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(f"{digest}  {path.name}\n")
    (folder / "SHA256SUMS").write_text("".join(lines))
    print(f"SHA256SUMS written for {len(files)} files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--checksums", action="store_true")
    args = parser.parse_args()
    audit(args.folder)
    if args.checksums:
        checksums(args.folder)
