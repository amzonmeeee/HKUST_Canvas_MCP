from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 4


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "HKUST_Canvas_MCP"
    if sys.platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            / "HKUST_Canvas_MCP"
        )
    return (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "HKUST_Canvas_MCP"
    )


def validate_data_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved in {
        Path(resolved.anchor),
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    }:
        raise ValueError("Choose a dedicated application-data directory.")
    for parent in (resolved, *resolved.parents):
        if (parent / ".git").exists():
            raise ValueError(
                "Web application data must be stored outside the Git repository."
            )
    return resolved


def now() -> str:
    return datetime.now(UTC).isoformat()


class WorkspaceRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = validate_data_dir(data_dir)
        self.path = self.data_dir / "app.db"

    def initialize(self) -> None:
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("The application database cannot be a symbolic link.")
        os.chmod(self.data_dir, 0o700)
        # Reserve owner-only permissions before SQLite opens the database.
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        with closing(self._connect()) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError(
                    "This database needs a newer version of the web application."
                )
            # Concurrent first launches can fail the journal-mode lock upgrade
            # immediately, even with SQLite's busy timeout. Retry only that lock.
            deadline = time.monotonic() + 10
            while True:
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if (
                        getattr(exc, "sqlite_errorcode", 0) & 0xFF
                        not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
                        or time.monotonic() >= deadline
                    ):
                        raise
                    time.sleep(0.025)
            with db:
                db.execute("BEGIN IMMEDIATE")
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    db.execute("""CREATE TABLE workspaces (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL CHECK(kind IN ('canvas_course', 'custom')),
                        canvas_course_id TEXT UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        course_code TEXT,
                        term_name TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_sync_at TEXT,
                        CHECK((kind = 'custom' AND canvas_course_id IS NULL) OR
                              (kind = 'canvas_course' AND canvas_course_id IS NOT NULL))
                    )""")
                    db.execute("PRAGMA user_version=1")
                from .store import migrate

                migrate(db)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def list(self) -> list[dict]:
        with closing(self._connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM workspaces ORDER BY updated_at DESC, id"
                )
            ]

    def get(self, workspace_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM workspaces WHERE id=?", (workspace_id,)
            ).fetchone()
            return dict(row) if row else None

    def for_course(self, course_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM workspaces WHERE canvas_course_id=?", (course_id,)
            ).fetchone()
            return dict(row) if row else None

    def create(
        self, *, title: str, description: str = "", course: dict | None = None
    ) -> dict:
        workspace_id, stamp = str(uuid4()), now()
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO workspaces
                (id, kind, canvas_course_id, title, description, course_code, term_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canvas_course_id) DO NOTHING""",
                (
                    workspace_id,
                    "canvas_course" if course else "custom",
                    course["id"] if course else None,
                    title,
                    description,
                    course.get("course_code") if course else None,
                    course.get("term_name") if course else None,
                    stamp,
                    stamp,
                ),
            )
        result = self.for_course(course["id"]) if course else self.get(workspace_id)
        assert result is not None
        return result

    def update(self, workspace_id: str, changes: dict) -> dict | None:
        allowed = {
            key: value
            for key, value in changes.items()
            if key in {"title", "description"}
        }
        if not allowed:
            return self.get(workspace_id)
        fields = ", ".join(f"{key}=?" for key in allowed)
        with closing(self._connect()) as db, db:
            db.execute(
                f"UPDATE workspaces SET {fields}, updated_at=? WHERE id=?",
                (*allowed.values(), now(), workspace_id),
            )
        return self.get(workspace_id)

    def delete(self, workspace_id: str) -> bool:
        with closing(self._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM workspaces WHERE id=?", (workspace_id,)
                ).rowcount
                > 0
            )
