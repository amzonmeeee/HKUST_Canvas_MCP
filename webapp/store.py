"""Local study data. No Canvas credentials or provider keys belong in this database."""

from __future__ import annotations

import json
import re
from contextlib import closing
from uuid import uuid4

from .db import WorkspaceRepository, now


def migrate(db):
    # The caller holds BEGIN IMMEDIATE, so simultaneous launches cannot race DDL.
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        for statement in (
            """CREATE TABLE sources (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                source_key TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                canvas_object_id TEXT, canvas_url TEXT, mime_type TEXT, remote_updated_at TEXT,
                synced_remote_updated_at TEXT, checksum TEXT, status TEXT NOT NULL DEFAULT 'not_synced',
                error_code TEXT, error_message TEXT, last_sync_at TEXT,
                metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, source_key))""",
            """CREATE TABLE source_chunks (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL, text TEXT NOT NULL, locator TEXT NOT NULL,
                UNIQUE(source_id, ordinal))""",
            "CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED, text, tokenize='unicode61')",
            """CREATE TRIGGER chunks_delete AFTER DELETE ON source_chunks BEGIN
                DELETE FROM chunks_fts WHERE chunk_id = old.id; END""",
            """CREATE TRIGGER chunks_insert AFTER INSERT ON source_chunks BEGIN
                INSERT INTO chunks_fts(chunk_id,text) VALUES(new.id,new.text); END""",
            """CREATE TABLE conversations (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
            """CREATE TABLE messages (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
                citations TEXT NOT NULL DEFAULT '[]', provider_id TEXT, model TEXT,
                created_at TEXT NOT NULL)""",
            """CREATE TABLE artifacts (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                kind TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                provenance TEXT NOT NULL, created_at TEXT NOT NULL)""",
            """CREATE TABLE notes (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                title TEXT NOT NULL, content TEXT NOT NULL, provenance TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
            """CREATE TABLE provider_configs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                base_url TEXT NOT NULL, model TEXT NOT NULL, capabilities TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
            "CREATE INDEX chunks_scope ON source_chunks(workspace_id,source_id)",
            "CREATE INDEX messages_conversation ON messages(conversation_id,created_at)",
        ):
            db.execute(statement)
        db.execute("PRAGMA user_version=2")
        version = 2
    if version < 3:
        db.execute(
            "ALTER TABLE provider_configs ADD COLUMN key_saved INTEGER NOT NULL DEFAULT 0"
        )
        db.execute("PRAGMA user_version=3")
        version = 3
    if version < 4:
        db.execute(
            "ALTER TABLE messages ADD COLUMN source_ids TEXT NOT NULL DEFAULT '[]'"
        )
        db.execute(
            "ALTER TABLE messages ADD COLUMN live_tools INTEGER NOT NULL DEFAULT 0"
        )
        # Experimental pre-v3 messages retain the source scope recoverable from citations.
        for row in db.execute("SELECT id,citations FROM messages").fetchall():
            citations = json.loads(row["citations"])
            scope = sorted(
                {
                    c["source_id"]
                    for c in citations
                    if isinstance(c, dict) and c.get("source_id")
                }
            )
            db.execute(
                "UPDATE messages SET source_ids=? WHERE id=?",
                (json.dumps(scope), row["id"]),
            )
        db.execute("PRAGMA user_version=4")
        version = 4
    if version < 5:
        db.execute(
            "ALTER TABLE workspaces ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )
        db.execute("PRAGMA user_version=5")
        version = 5
    if version < 6:
        db.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        used = bool(db.execute("SELECT EXISTS(SELECT 1 FROM workspaces) OR EXISTS(SELECT 1 FROM provider_configs)").fetchone()[0])
        for key in ("onboarding_completed", "canvas_enabled"):
            db.execute("INSERT INTO app_settings VALUES (?, ?)", (key, json.dumps(used)))
        db.execute("PRAGMA user_version=6")


JSON_FIELDS = {
    "metadata",
    "locator",
    "citations",
    "provenance",
    "capabilities",
    "source_ids",
}


def decode(row):
    if row is None:
        return None
    result = dict(row)
    for field in JSON_FIELDS & result.keys():
        result[field] = json.loads(result[field])
    if "content" in result and "kind" in result and "provenance" in result:
        result["content"] = json.loads(result["content"])
    return result


class StudyStore:
    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    def setting(self, key, default=False):
        with closing(self.repository._connect()) as db:
            row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with closing(self.repository._connect()) as db, db:
            db.execute("INSERT INTO app_settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def sources(self, workspace_id):
        with closing(self.repository._connect()) as db:
            return [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM sources WHERE workspace_id=? ORDER BY kind,title,id",
                    (workspace_id,),
                )
            ]

    def source(self, workspace_id, source_id):
        with closing(self.repository._connect()) as db:
            return decode(
                db.execute(
                    "SELECT * FROM sources WHERE workspace_id=? AND id=?",
                    (workspace_id, source_id),
                ).fetchone()
            )

    def upsert_source(self, workspace_id, item):
        stamp = now()
        with closing(self.repository._connect()) as db, db:
            db.execute(
                """INSERT INTO sources
                (id,workspace_id,source_key,kind,title,canvas_object_id,canvas_url,mime_type,
                 remote_updated_at,metadata,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(workspace_id,source_key) DO UPDATE SET
                 title=excluded.title, canvas_url=excluded.canvas_url, mime_type=excluded.mime_type,
                 remote_updated_at=excluded.remote_updated_at, metadata=excluded.metadata,
                 status=CASE WHEN sources.status='ready' AND
                 (excluded.remote_updated_at IS NOT sources.synced_remote_updated_at OR
                  (sources.kind='module' AND excluded.metadata <> sources.metadata))
                 THEN 'stale' ELSE sources.status END, updated_at=excluded.updated_at""",
                (
                    str(uuid4()),
                    workspace_id,
                    item["source_key"],
                    item["kind"],
                    item["title"],
                    item.get("canvas_object_id"),
                    item.get("canvas_url"),
                    item.get("mime_type"),
                    item.get("remote_updated_at"),
                    json.dumps(item.get("metadata", {})),
                    item.get("status", "not_synced"),
                    stamp,
                    stamp,
                ),
            )
            return decode(
                db.execute(
                    "SELECT * FROM sources WHERE workspace_id=? AND source_key=?",
                    (workspace_id, item["source_key"]),
                ).fetchone()
            )

    def source_status(self, source_id, status, *, code=None, message=None):
        with closing(self.repository._connect()) as db, db:
            db.execute(
                "UPDATE sources SET status=?,error_code=?,error_message=?,updated_at=? WHERE id=?",
                (status, code, message, now(), source_id),
            )

    def index(self, source, chunks, checksum):
        with closing(self.repository._connect()) as db, db:
            db.execute("DELETE FROM source_chunks WHERE source_id=?", (source["id"],))
            for ordinal, chunk in enumerate(chunks):
                db.execute(
                    "INSERT INTO source_chunks VALUES(?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        source["id"],
                        source["workspace_id"],
                        ordinal,
                        chunk["text"],
                        json.dumps(chunk["locator"]),
                    ),
                )
            stamp = now()
            db.execute(
                """UPDATE sources SET status='ready',checksum=?,last_sync_at=?,
                synced_remote_updated_at=remote_updated_at,error_code=NULL,error_message=NULL,
                updated_at=? WHERE id=?""",
                (checksum, stamp, stamp, source["id"]),
            )
            db.execute(
                "UPDATE workspaces SET last_sync_at=?,updated_at=? WHERE id=?",
                (stamp, stamp, source["workspace_id"]),
            )

    def chunks(self, workspace_id, source_id):
        with closing(self.repository._connect()) as db:
            return [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM source_chunks WHERE workspace_id=? AND source_id=? ORDER BY ordinal",
                    (workspace_id, source_id),
                )
            ]

    def search(self, workspace_id, source_ids, query, limit=12):
        if not source_ids:
            return []
        terms = re.findall(r"[^\W_]+", query, re.UNICODE)[:24]
        scope = ",".join("?" for _ in source_ids)
        fields = "c.*, s.title AS source_title,s.canvas_url,s.kind AS source_kind"
        base = f"FROM source_chunks c JOIN sources s ON s.id=c.source_id WHERE c.workspace_id=? AND c.source_id IN ({scope}) AND s.status='ready'"
        args = [workspace_id, *source_ids]
        with closing(self.repository._connect()) as db:
            rows = []
            if terms:
                match = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
                rows = db.execute(
                    f"SELECT {fields} FROM chunks_fts f JOIN source_chunks c ON c.id=f.chunk_id JOIN sources s ON s.id=c.source_id WHERE chunks_fts MATCH ? AND c.workspace_id=? AND c.source_id IN ({scope}) AND s.status='ready' ORDER BY bm25(chunks_fts) LIMIT 30",
                    [match, *args],
                ).fetchall()
                if not rows:
                    clauses = " OR ".join(
                        "instr(lower(c.text), lower(?))>0" for _ in terms
                    )
                    rows = db.execute(
                        f"SELECT {fields} {base} AND ({clauses}) LIMIT 30",
                        [*args, *terms],
                    ).fetchall()
            if not terms:
                rows = db.execute(
                    f"SELECT {fields} {base} ORDER BY c.ordinal LIMIT ?", [*args, limit]
                ).fetchall()
            # Bound context and spread across sources rather than taking a whole book.
            output, counts = [], {}
            for row in rows:
                item = decode(row)
                count = counts.get(item["source_id"], 0)
                if count < 4:
                    output.append(item)
                    counts[item["source_id"]] = count + 1
                if len(output) >= limit:
                    break
            return output

    def delete_source(self, workspace_id, source_id):
        with closing(self.repository._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM sources WHERE workspace_id=? AND id=?",
                    (workspace_id, source_id),
                ).rowcount
                > 0
            )

    def providers(self):
        with closing(self.repository._connect()) as db:
            return [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM provider_configs ORDER BY created_at,id"
                )
            ]

    def provider(self, provider_id):
        return next((p for p in self.providers() if p["id"] == provider_id), None)

    def save_provider(self, config):
        stamp = now()
        with closing(self.repository._connect()) as db, db:
            db.execute(
                """INSERT INTO provider_configs
                (id,name,kind,base_url,model,capabilities,created_at,updated_at,key_saved)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,
                base_url=excluded.base_url,model=excluded.model,capabilities=excluded.capabilities,
                updated_at=excluded.updated_at,key_saved=excluded.key_saved""",
                (
                    config["id"],
                    config["name"],
                    config["kind"],
                    config["base_url"],
                    config["model"],
                    json.dumps(config["capabilities"]),
                    stamp,
                    stamp,
                    int(config.get("key_saved", False)),
                ),
            )
        return self.provider(config["id"])

    def delete_provider(self, provider_id):
        with closing(self.repository._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM provider_configs WHERE id=?", (provider_id,)
                ).rowcount
                > 0
            )

    def conversations(self, workspace_id):
        with closing(self.repository._connect()) as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM conversations WHERE workspace_id=? ORDER BY updated_at DESC",
                    (workspace_id,),
                )
            ]

    def conversation(self, workspace_id, conversation_id):
        with closing(self.repository._connect()) as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE id=? AND workspace_id=?",
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["messages"] = [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,id",
                    (conversation_id,),
                )
            ]
            return result

    def create_conversation(self, workspace_id, title):
        identifier, stamp = str(uuid4()), now()
        with closing(self.repository._connect()) as db, db:
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?,?,?)",
                (identifier, workspace_id, title[:160], stamp, stamp),
            )
        return self.conversation(workspace_id, identifier)

    def save_conversation_snapshot(self, conversation):
        """Atomically persist a temporary conversation after an explicit save."""
        with closing(self.repository._connect()) as db, db:
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?,?,?)",
                (
                    conversation["id"],
                    conversation["workspace_id"],
                    conversation["title"],
                    conversation["created_at"],
                    now(),
                ),
            )
            for message in conversation["messages"]:
                db.execute(
                    "INSERT INTO messages(id,conversation_id,role,content,status,citations,provider_id,model,created_at,source_ids,live_tools) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        message["id"],
                        conversation["id"],
                        message["role"],
                        message["content"],
                        message["status"],
                        json.dumps(message["citations"]),
                        message["provider_id"],
                        message["model"],
                        message["created_at"],
                        json.dumps(message["source_ids"]),
                        int(message["live_tools"]),
                    ),
                )
        return self.conversation(conversation["workspace_id"], conversation["id"])

    def add_message(
        self,
        conversation_id,
        role,
        content,
        *,
        status="complete",
        citations=None,
        provider=None,
        source_ids=None,
        live_tools=False,
    ):
        identifier, stamp = str(uuid4()), now()
        with closing(self.repository._connect()) as db, db:
            db.execute(
                "INSERT INTO messages(id,conversation_id,role,content,status,citations,provider_id,model,created_at,source_ids,live_tools) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    conversation_id,
                    role,
                    content,
                    status,
                    json.dumps(citations or []),
                    (provider or {}).get("id"),
                    (provider or {}).get("model"),
                    stamp,
                    json.dumps(source_ids or []),
                    int(live_tools),
                ),
            )
            db.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (stamp, conversation_id),
            )
        return identifier

    def delete_conversation(self, workspace_id, identifier):
        with closing(self.repository._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM conversations WHERE workspace_id=? AND id=?",
                    (workspace_id, identifier),
                ).rowcount
                > 0
            )

    def artifacts(self, workspace_id):
        with closing(self.repository._connect()) as db:
            return [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM artifacts WHERE workspace_id=? ORDER BY created_at DESC",
                    (workspace_id,),
                )
            ]

    def save_artifact(self, workspace_id, kind, title, content, provenance):
        identifier = str(uuid4())
        with closing(self.repository._connect()) as db, db:
            db.execute(
                "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)",
                (
                    identifier,
                    workspace_id,
                    kind,
                    title,
                    json.dumps(content),
                    json.dumps(provenance),
                    now(),
                ),
            )
        return next(a for a in self.artifacts(workspace_id) if a["id"] == identifier)

    def delete_artifact(self, workspace_id, identifier):
        with closing(self.repository._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM artifacts WHERE workspace_id=? AND id=?",
                    (workspace_id, identifier),
                ).rowcount
                > 0
            )

    def notes(self, workspace_id):
        with closing(self.repository._connect()) as db:
            return [
                decode(r)
                for r in db.execute(
                    "SELECT * FROM notes WHERE workspace_id=? ORDER BY updated_at DESC",
                    (workspace_id,),
                )
            ]

    def save_note(self, workspace_id, title, content, provenance=None, identifier=None):
        identifier, stamp = identifier or str(uuid4()), now()
        with closing(self.repository._connect()) as db, db:
            db.execute(
                """INSERT INTO notes VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,content=excluded.content,updated_at=excluded.updated_at
                WHERE notes.workspace_id=excluded.workspace_id""",
                (
                    identifier,
                    workspace_id,
                    title,
                    content,
                    json.dumps(provenance or {}),
                    stamp,
                    stamp,
                ),
            )
        return next(
            (n for n in self.notes(workspace_id) if n["id"] == identifier), None
        )

    def delete_note(self, workspace_id, identifier):
        with closing(self.repository._connect()) as db, db:
            return (
                db.execute(
                    "DELETE FROM notes WHERE workspace_id=? AND id=?",
                    (workspace_id, identifier),
                ).rowcount
                > 0
            )
