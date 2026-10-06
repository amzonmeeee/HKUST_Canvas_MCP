from __future__ import annotations

from itertools import islice
from typing import Any

from canvasapi.util import combine_kwargs

from .content import _CanvasDictItem


class CanvasActivityMixin:
    """Endpoints not covered by the existing SDK mixins.

    Keep pagination inside the authenticated SDK session and read one extra
    item so callers can distinguish an empty result from an incomplete scan.
    """

    def activity_list(
        self, endpoint: str, *, params: dict[str, Any] | None = None, limit: int = 100
    ) -> dict[str, Any]:
        def fetch(canvas):
            items = self._custom_paginated_call(
                canvas, content_class=_CanvasDictItem, endpoint=endpoint,
                params={"per_page": 100, **(params or {})},
            )
            rows = [self._item_to_dict(item) for item in islice(items, limit + 1)]
            return {"items": rows[:limit], "truncated": len(rows) > limit}

        return self._call_canvas(fetch, f"list {endpoint}")

    def activity_get(
        self, endpoint: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        return self._activity_request("GET", endpoint, params or {})

    def activity_write(
        self, method: str, endpoint: str, payload: dict[str, Any]
    ) -> Any:
        # No application-level retries: an ambiguous POST failure may already
        # have delivered a message or comment. Confirmation is consumed first.
        return self._activity_request(method, endpoint, payload)

    def _activity_request(self, method: str, endpoint: str, payload: dict[str, Any]):
        def request(canvas):
            requester = getattr(canvas, "_Canvas__requester")
            response = requester.request(method, endpoint, use_auth=False,
                                         _kwargs=combine_kwargs(**payload))
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

        return self._call_canvas(request, f"{method} {endpoint}")
