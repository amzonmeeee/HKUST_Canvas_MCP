"""Bounded, process-memory chat transcripts; never written unless explicitly saved."""

from copy import deepcopy
from threading import RLock
from time import monotonic
from uuid import uuid4

from .db import now
from .providers import ProviderError


class TemporaryChats:
    def __init__(self):
        self._rows = {}
        self._lock = RLock()

    def _prune(self):
        for key in list(self._rows):
            if monotonic() - self._rows[key][0] > 4 * 3600:
                del self._rows[key]

    def create_conversation(self, workspace_id, title):
        with self._lock:
            self._prune()
            if len(self._rows) >= 20:
                raise ProviderError(
                    "temporary_limit",
                    "Close a temporary chat before starting another.",
                    429,
                )
            identifier, stamp = str(uuid4()), now()
            row = {
                "id": identifier,
                "workspace_id": workspace_id,
                "title": title[:160],
                "created_at": stamp,
                "updated_at": stamp,
                "messages": [],
                "temporary": True,
            }
            self._rows[identifier] = (monotonic(), row)
            return deepcopy(row)

    def conversation(self, workspace_id, identifier):
        with self._lock:
            self._prune()
            entry = self._rows.get(identifier)
            if not entry or entry[1]["workspace_id"] != workspace_id:
                return None
            self._rows[identifier] = (monotonic(), entry[1])
            return deepcopy(entry[1])

    def add_message(
        self,
        identifier,
        role,
        content,
        *,
        status="complete",
        citations=None,
        provider=None,
        source_ids=None,
        live_tools=False,
    ):
        with self._lock:
            row = self._rows[identifier][1]
            row["messages"].append(
                {
                    "id": str(uuid4()),
                    "role": role,
                    "content": content,
                    "status": status,
                    "citations": citations or [],
                    "provider_id": (provider or {}).get("id"),
                    "model": (provider or {}).get("model"),
                    "source_ids": source_ids or [],
                    "live_tools": live_tools,
                    "created_at": now(),
                }
            )
            row["updated_at"] = now()
            self._rows[identifier] = (monotonic(), row)

    def delete_conversation(self, workspace_id, identifier):
        with self._lock:
            if not self.conversation(workspace_id, identifier):
                return False
            del self._rows[identifier]
            return True

    def save(self, store, workspace_id, identifier):
        with self._lock:
            row = self.conversation(workspace_id, identifier)
            if not row:
                raise ProviderError(
                    "conversation_not_found",
                    "Temporary chat expired or was discarded.",
                    404,
                )
            result = store.save_conversation_snapshot(row)
            del self._rows[identifier]
            return result
