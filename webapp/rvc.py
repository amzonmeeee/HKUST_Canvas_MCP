"""HKUST RVC (Remote Video Capture) recording patterns. Pure functions; no network.

Observed on canvas.ust.hk in 2026 (example names are fictional):

1. Each lecture is a Canvas page titled ``COMP1000-L1-2026-09-01-09-00`` (course-section-date-time).
   Module pages usually link to these pages.
2. The page embeds ``https://rvcmedia.ust.hk/media/?path=<media id>``.
3. With an HKUST sign-in, ``https://rvcmedia.ust.hk/Media/Play?path=<media id>`` configures its
   player with ``streamingServer`` and ``streamingUrl``: an HLS playlist with a time-limited token.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

RVCMEDIA = "https://rvcmedia.ust.hk"
RECORDING_TITLE = re.compile(
    r"^[A-Za-z]{4}\d{4}[A-Za-z]?(?:-[A-Za-z0-9]+)+-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}$"
)
_MEDIA_PATH = re.compile(
    r"rvcmedia\.ust\.hk/(?:media/?|Media/Play)\?(?:[^\"'<>\s]*&(?:amp;)?)?path=([A-Za-z0-9_\-]+)",
    re.IGNORECASE,
)
_PAGE_LINK = re.compile(r"/courses/(\d+)/pages/([A-Za-z0-9_\-%.]+)")
_TIMESTAMP = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*")


def is_recording(title_or_slug) -> bool:
    return bool(RECORDING_TITLE.match(str(title_or_slug or "").strip()))


def media_paths(html) -> list[str]:
    found = []
    for path in _MEDIA_PATH.findall(html or ""):
        if path not in found:
            found.append(path)
    return found


def recording_links(html, course_id) -> list[str]:
    """Slugs of linked pages in this course that follow the RVC title pattern."""
    found = []
    for course, slug in _PAGE_LINK.findall(html or ""):
        slug = unquote(slug)
        if course == str(course_id) and is_recording(slug) and slug not in found:
            found.append(slug)
    return found


def parse_player(html) -> str | None:
    """HLS playlist URL from an rvcmedia /Media/Play page, or None (for example, signed out)."""
    server = re.search(r"streamingServer\s*=\s*'([^']+)'", html or "")
    path = re.search(r"streamingUrl\s*=\s*'([^']+)'", html or "")
    if not (server and path):
        return None
    host = server.group(1).strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]+\.ust\.hk", host):
        return None
    return f"https://{host}/{path.group(1).lstrip('/')}"


def safe_name(text) -> str:
    text = re.sub(r"[\x00-\x1f/\\:*?\"<>|]+", "-", str(text)).strip(" .-")
    return text[:100] or "recording"


def transcript_sections(text, *, part=None, max_chars=1500):
    """Group "[HH:MM:SS] text" paragraphs into searchable sections with a time locator."""
    sections, buffer, start = [], [], None

    def flush():
        if buffer:
            locator = {"time": start} if start else {}
            if part:
                locator["part"] = part
            sections.append(("\n\n".join(buffer), locator))

    for paragraph in re.split(r"\n\s*\n", text or ""):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        match = _TIMESTAMP.match(paragraph)
        stamp = match.group(1) if match else None
        body = paragraph[match.end():] if match else paragraph
        if buffer and sum(len(b) for b in buffer) + len(body) > max_chars:
            flush()
            buffer, start = [], None
        if start is None:
            start = stamp
        buffer.append(body)
    flush()
    return sections
