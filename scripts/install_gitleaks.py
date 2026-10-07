"""Download a pinned official scanner into a task-specific directory."""

from __future__ import annotations

import argparse
import hashlib
import platform
import tarfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "8.30.1"


def install(folder):
    system = {"Darwin": "darwin", "Linux": "linux"}[platform.system()]
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64"}[
        platform.machine()
    ]
    name = f"gitleaks_{VERSION}_{system}_{architecture}.tar.gz"
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/"
    folder.mkdir(parents=True, exist_ok=True)
    with urlopen(base + name, timeout=60) as response:
        content = response.read()
    with urlopen(base + f"gitleaks_{VERSION}_checksums.txt", timeout=30) as response:
        checksums = response.read().decode()
    expected = next(
        line.split()[0] for line in checksums.splitlines() if line.split()[-1] == name
    )
    if hashlib.sha256(content).hexdigest() != expected:
        raise SystemExit("Official scanner checksum mismatch")
    archive = folder / name
    archive.write_bytes(content)
    with tarfile.open(archive) as tar:
        tar.extract(tar.getmember("gitleaks"), folder, filter="data")
    archive.unlink()
    print(f"Installed checksum-verified Gitleaks {VERSION}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    install(parser.parse_args().folder)
