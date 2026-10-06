"""Small metadata-only event logger for the local web process."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("hkust_canvas_workbench")


def configure_logging():
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # The Canvas SDK debug logger includes request bodies and signed URLs.
    # It has no place in the web application's metadata-only logging policy.
    logging.getLogger("canvasapi.requester").disabled = True


def event(name, **fields):
    allowed = {
        k: v
        for k, v in fields.items()
        if k in {"status", "code", "elapsed_ms", "count", "kind"}
    }
    logger.info(json.dumps({"event": name, **allowed}, separators=(",", ":")))
