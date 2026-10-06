from __future__ import annotations

from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def isolated_auth_and_network(monkeypatch, tmp_path):
    """Tests must mock browser access and HTTP instead of using personal sessions."""
    def blocked(*args, **kwargs):
        raise AssertionError("Mock Chrome cookies and HTTP requests in tests")

    monkeypatch.setattr("browser_cookie3.chrome", blocked)
    monkeypatch.setattr("requests.sessions.Session.send", blocked)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    for module in ("tools.common", "tools.files", "tools.submissions"):
        monkeypatch.setattr(f"{module}.download_dir", lambda: downloads)
    from tools.common import reset_canvas_client

    reset_canvas_client()
    yield
    reset_canvas_client()


@pytest.fixture
def mock_client():
    client = mock.MagicMock()
    patches = [
        mock.patch("tools.assignments.canvas_client", return_value=client),
        mock.patch("tools.common.canvas_client", return_value=client),
        mock.patch("tools.courses.canvas_client", return_value=client),
        mock.patch("tools.discussions.canvas_client", return_value=client),
        mock.patch("tools.files.canvas_client", return_value=client),
        mock.patch("tools.grades.canvas_client", return_value=client),
        mock.patch("tools.misc.canvas_client", return_value=client),
        mock.patch("tools.submissions.canvas_client", return_value=client),
        mock.patch("tools.activity.canvas_client", return_value=client),
        mock.patch("tools.interactions.canvas_client", return_value=client),
    ]
    for patch in patches:
        patch.start()
    try:
        yield client
    finally:
        for patch in reversed(patches):
            patch.stop()
