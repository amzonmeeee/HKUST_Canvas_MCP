"""Short-lived, single-use confirmations that work across CLI processes.

Only hashes are saved; message bodies, recipient lists, profile paths and
authentication material are never persisted by this store.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import time

TTL_SECONDS = 600


def _directory() -> Path:
    configured = os.environ.get("CANVASMCP_CONFIRMATION_DIR")
    root = Path(configured).expanduser() if configured else Path.home() / "Library" / "Application Support" / "canvasmcp" / "write-confirmations"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def issue_confirmation(intent: dict) -> tuple[str, float]:
    root = _directory()
    now = time.time()
    # Bound long-lived disk accumulation without saving sensitive previews.
    for path in root.iterdir():
        if path.suffix not in {".json", ".used"}:
            continue
        try:
            if not path.is_symlink() and now - path.stat().st_mtime > TTL_SECONDS:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass  # Another process may have consumed or cleaned this file.
    token = secrets.token_urlsafe(32)
    expires = now + TTL_SECONDS
    path = root / f"{_digest(token)}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump({"fingerprint": _digest(intent), "expires_at": expires}, stream)
    return token, expires


def claim_confirmation(token: str, intent: dict) -> str | None:
    root = _directory()
    path = root / f"{_digest(token)}.json"
    claim = path.with_suffix(".used")
    if claim.exists():
        return "Confirmation has already been used. Preview again before retrying."
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd) as stream:
            saved = json.load(stream)
    except (OSError, ValueError):
        return "Unknown confirmation token. Preview the operation first."
    if saved["expires_at"] <= time.time():
        path.unlink(missing_ok=True)
        return "Confirmation expired. Preview the operation again."
    if saved["fingerprint"] != _digest(intent):
        return "Arguments, account, profile or target changed. Preview the operation again."
    try:
        # Exclusive creation is the claim. Concurrent CLI/MCP invocations may
        # read the same preview, but only one can send the HTTP mutation.
        fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except FileExistsError:
        return "Confirmation has already been used. Preview again before retrying."
    path.unlink(missing_ok=True)
    # Keeping no reusable preview after claiming also prevents duplicate sends
    # on connection failures where Canvas may have accepted the operation.
    # Retain the exclusive claim through the entire token lifetime: another
    # process may already have read the preview before we deleted its file.
    return None
