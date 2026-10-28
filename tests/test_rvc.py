"""RVC recordings and the optional local transcriber. No network, Chrome or real model.

All course data is fictional. A small fake component stands in for RVC_Transcriber and
speaks the same command-line contract (install, streams, @@progress lines).
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from tests.test_study_webapp import setup  # noqa: F401 -- shared app fixture
from webapp import rvc
from webapp.services import transcriber as transcriber_module
from webapp.services.canvas import CanvasServiceError
from webapp.services.transcriber import TranscriberError, extract_source, git_tree_hash

RVC_PAGE_BODY = '<iframe src="https://rvcmedia.ust.hk/media/?path=26FA_COMP1000-L1_260901_AbCdEf1234"></iframe>'
MODULE_BODY = """<p>RVC Recordings:</p>
<a href="https://canvas.ust.hk/courses/101/pages/comp1000-l1-2026-09-01-09-00">Lecture 1</a>
<a href="https://canvas.ust.hk/courses/101/pages/comp1000-l1-2026-09-03-09-00">Lecture 2 (unpublished)</a>
<a href="https://canvas.ust.hk/courses/999/pages/comp1000-l1-2026-09-05-09-00">Other course</a>"""
PLAYER = """var streamingServer = 'stream01.ust.hk';
var streamingUrl = 'rvcsecured/mp4:26FA_X.mp4/playlist.m3u8?rvctokenendtime=1&rvctokenhash=Zz=';"""

FAKE_LAUNCHER = r'''
import json, sys, time
from pathlib import Path
args = sys.argv[1:]
def progress(**data):
    print("@@progress " + json.dumps(data), flush=True)
if args[0] == "install":
    progress(event="downloading model", model="qwen3-asr-0.6b")
    progress(event="installed", model="qwen3-asr-0.6b")
elif args[0] == "streams":
    streams = json.loads(Path(args[args.index("--streams") + 1]).read_text())
    output = Path(args[args.index("--output") + 1])
    assert "--keep-runtime" in args and "--resume" in args and "--timestamps" in args
    for entry in streams:
        assert entry["stream"].startswith("https://") and entry["stream_id"]
        if entry["stream_id"] == "SLOW":
            time.sleep(30)
        progress(event="transcribing", segment=1, segments=2, audio_time="00:00:00")
        (output / (entry["name"] + ".txt")).write_text(
            "[00:00:00] 今日講 retrieval practice。\n\n[00:00:28] 下一部分講 spacing effect。\n", encoding="utf-8")
        progress(event="complete")
else:
    sys.exit(2)
'''


@pytest.fixture
def apple_silicon(monkeypatch):
    # CI also runs on Linux; the component itself supports only Apple Silicon macOS.
    monkeypatch.setattr(transcriber_module, "supported_platform", lambda: True)


def fake_component(tmp_path, monkeypatch):
    checkout = tmp_path / "fake-transcriber"
    checkout.mkdir()
    (checkout / "launcher.py").write_text(FAKE_LAUNCHER)
    monkeypatch.setenv(transcriber_module.CHECKOUT_ENV, str(checkout))
    return checkout


def wait_for_job(client, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get("/api/transcriber").json()["job"]
        if job and job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("transcriber job did not finish")


def course_workspace(client, canvas, pages):
    def call(method, **args):
        if method == "list_pages":
            return [{"url": slug, "title": data["title"], "updated_at": "v1"} for slug, data in pages.items()]
        if method == "get_page":
            if args["url_or_id"] not in pages:
                raise CanvasServiceError("canvas_not_found", "Not found.", 404)
            return {**pages[args["url_or_id"]], "updated_at": "v1"}
        if method == "activity_list":
            return {"items": [], "truncated": False}
        return []

    canvas.client_call.side_effect = call
    return client.post(
        "/api/workspaces", json={"kind": "canvas_course", "canvas_course_id": "101"}
    ).json()


# ---------------------------------------------------------------- patterns


def test_recording_patterns():
    assert rvc.is_recording("COMP1000-L1-2026-09-01-09-00")
    assert rvc.is_recording("comp1000-l1-l3-2026-09-01-09-00")
    assert not rvc.is_recording("lecture-notes-week-1")
    assert rvc.media_paths(RVC_PAGE_BODY * 2) == ["26FA_COMP1000-L1_260901_AbCdEf1234"]
    assert rvc.recording_links(MODULE_BODY, 101) == [
        "comp1000-l1-2026-09-01-09-00",
        "comp1000-l1-2026-09-03-09-00",
    ]
    assert rvc.parse_player(PLAYER) == (
        "https://stream01.ust.hk/rvcsecured/mp4:26FA_X.mp4/playlist.m3u8?rvctokenendtime=1&rvctokenhash=Zz="
    )
    assert rvc.parse_player(PLAYER.replace("stream01.ust.hk", "evil.example.com")) is None
    assert rvc.parse_player("Sign in is required to view this video") is None
    assert rvc.safe_name("a/b:c?") == "a-b-c"


def test_transcript_sections_keep_time_locators():
    text = "[00:00:00] first\n\n[00:00:28] second\n\n[00:00:56] " + "x" * 1600
    sections = rvc.transcript_sections(text)
    assert sections[0] == ("first\n\nsecond", {"time": "00:00:00"})
    assert sections[1][1] == {"time": "00:00:56"}
    assert rvc.transcript_sections("[00:01:00] a", part=2) == [("a", {"time": "00:01:00", "part": 2})]


# ------------------------------------------------------- component checks


@pytest.mark.skipif(shutil.which("git") is None, reason="git is needed to compute a reference tree")
def test_git_tree_hash_matches_git(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "run.sh").write_text("#!/bin/sh\necho hi\n")
    (repo / "run.sh").chmod(0o755)
    (repo / "src" / "pkg" / "a.py").write_text("print('a')\n")
    (repo / "src-file").write_text("sorting: 'src' tree sorts after 'src-file'\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "x"], check=True)
    expected = subprocess.run([*git, "rev-parse", "HEAD^{tree}"], check=True, capture_output=True, text=True)
    shutil.rmtree(repo / ".git")
    assert git_tree_hash(repo) == expected.stdout.strip()


def tarball(entries):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for name, kind, content in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
            elif kind == "link":
                info.type, info.linkname = tarfile.SYMTYPE, content
                tar.addfile(info)
    return data.getvalue()


def test_source_archive_extraction_is_strict(tmp_path):
    top = extract_source(tarball([("RVC-abc/launcher.py", "file", b"x")]), tmp_path / "ok")
    assert (top / "launcher.py").read_bytes() == b"x"
    unsafe = [
        [("RVC-abc/../../escape.py", "file", b"x")],
        [("RVC-abc/link", "link", "/etc/passwd")],
        [("one/a", "file", b"x"), ("two/b", "file", b"x")],
    ]
    for number, entries in enumerate(unsafe):
        with pytest.raises(TranscriberError):
            extract_source(tarball(entries), tmp_path / f"bad{number}")
    assert not (tmp_path / "escape.py").exists()


def test_install_refused_on_unsupported_platform(setup, monkeypatch):  # noqa: F811
    client, *_ = setup
    monkeypatch.setattr(transcriber_module, "supported_platform", lambda: False)
    refused = client.post("/api/transcriber/install", json={"model": "auto"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "unsupported_platform"
    assert client.get("/api/transcriber").json()["job"] is None


def test_pinned_download_must_match_tree(setup, tmp_path, monkeypatch, apple_silicon):  # noqa: F811
    client, app, *_ = setup
    monkeypatch.delenv(transcriber_module.CHECKOUT_ENV, raising=False)
    service = app.state.transcriber
    service._fetch = lambda url, limit: tarball([("RVC-x/launcher.py", "file", b"tampered")])
    service.install("auto")
    job = wait_for_job(client)
    assert job["state"] == "failed" and "pinned version" in job["message"]
    assert client.get("/api/transcriber").json()["installed"] is False
    assert not (service.root / "source" / transcriber_module.COMPONENT_COMMIT).exists()


# ------------------------------------------------------ sources and jobs


def test_recordings_found_by_title_and_from_module_links(setup):  # noqa: F811
    client, _app, _w, _p, _f, _s, canvas = setup
    workspace = course_workspace(client, canvas, {
        "comp1000-l1-2026-09-01-09-00": {"title": "COMP1000-L1-2026-09-01-09-00", "body": RVC_PAGE_BODY},
        "lecture-notes-week-1": {"title": "Week 1 notes", "body": MODULE_BODY},
    })
    base = f"/api/workspaces/{workspace['id']}/sources"
    found = client.post(base + "/inventory").json()["sources"]
    kinds = {s["title"]: s["kind"] for s in found if s["kind"] != "syllabus"}
    assert kinds == {"COMP1000-L1-2026-09-01-09-00": "recording", "Week 1 notes": "page"}

    # A course without a visible Pages index: the module page links reveal the recordings.
    canvas.client_call.side_effect = lambda method, **a: (
        {"title": "Week 1 notes", "body": MODULE_BODY, "updated_at": "v1"}
        if method == "get_page" and a["url_or_id"] == "lecture-notes-week-1"
        else {"title": "COMP1000-L1-2026-09-01-09-00", "body": RVC_PAGE_BODY}
        if method == "get_page" and a["url_or_id"] == "comp1000-l1-2026-09-01-09-00"
        else (_ for _ in ()).throw(CanvasServiceError("canvas_not_found", "Not found.", 404))
        if method == "get_page"
        else []
    )
    client.delete(f"{base}/{next(s['id'] for s in found if s['kind'] == 'recording')}")
    notes = next(s for s in found if s["kind"] == "page")
    client.post(base + "/sync", json={"source_ids": [notes["id"]]})
    recordings = [s for s in client.get(base).json()["sources"] if s["kind"] == "recording"]
    # The unpublished and the other-course links are not added.
    assert [(r["title"], r["status"]) for r in recordings] == [("COMP1000-L1-2026-09-01-09-00", "not_synced")]

    # An ordinary sync never starts a transcription or contacts Canvas for a recording.
    canvas.client_call.reset_mock()
    synced = client.post(base + "/sync", json={"source_ids": [recordings[0]["id"]]}).json()
    assert synced["sources"][0]["status"] == "not_synced"
    canvas.client_call.assert_not_called()


def test_install_transcribe_index_and_cite(setup, tmp_path, monkeypatch, apple_silicon):  # noqa: F811
    client, app, _w, _p, _f, _s, canvas = setup
    fake_component(tmp_path, monkeypatch)
    resolved = []
    app.state.transcriber._resolve = lambda path: resolved.append(path) or "https://stream01.ust.hk/p.m3u8?t=1"
    workspace = course_workspace(client, canvas, {
        "comp1000-l1-2026-09-01-09-00": {"title": "COMP1000-L1-2026-09-01-09-00", "body": RVC_PAGE_BODY},
    })
    base = f"/api/workspaces/{workspace['id']}/sources"
    recording = next(s for s in client.post(base + "/inventory").json()["sources"] if s["kind"] == "recording")

    refused = client.post(f"{base}/{recording['id']}/transcribe")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "transcriber_not_installed"

    assert client.post("/api/transcriber/install", json={"model": "auto"}).status_code == 202
    assert wait_for_job(client)["state"] == "complete"
    status = client.get("/api/transcriber").json()
    assert status["installed"] is True and status["model"] == "qwen3-asr-0.6b"

    assert client.post(f"{base}/{recording['id']}/transcribe").status_code == 202
    job = wait_for_job(client)
    assert job["state"] == "complete", job
    assert resolved == ["26FA_COMP1000-L1_260901_AbCdEf1234"]

    details = client.get(f"{base}/{recording['id']}").json()
    assert details["source"]["status"] == "ready"
    assert "retrieval practice" in details["display_text"]
    assert details["transcript"]["model"] == "qwen3-asr-0.6b"
    assert details["chunks"][0]["locator"]["time"] == "00:00:00"
    # Stream tokens are never kept after the run.
    assert not list((app.state.transcriber.root / "jobs").rglob("streams.json"))
    # The transcript is now an ordinary ready source for search and citations.
    hits = app.state.study_store.search(workspace["id"], [recording["id"]], "spacing")
    assert hits and hits[0]["source_id"] == recording["id"]


def test_sign_in_failure_and_busy_and_stop(setup, tmp_path, monkeypatch):  # noqa: F811
    client, app, _w, _p, _f, _s, canvas = setup
    fake_component(tmp_path, monkeypatch)
    service = app.state.transcriber
    service._save_state({"installed_model": "qwen3-asr-0.6b", "commit": "local"})
    slow_body = '<iframe src="https://rvcmedia.ust.hk/media/?path=SLOW"></iframe>'
    workspace = course_workspace(client, canvas, {
        "comp1000-l1-2026-09-01-09-00": {"title": "COMP1000-L1-2026-09-01-09-00", "body": RVC_PAGE_BODY},
        "comp1000-l1-2026-09-03-09-00": {"title": "COMP1000-L1-2026-09-03-09-00", "body": slow_body},
    })
    base = f"/api/workspaces/{workspace['id']}/sources"
    first, second = sorted(
        (s for s in client.post(base + "/inventory").json()["sources"] if s["kind"] == "recording"),
        key=lambda s: s["title"],
    )

    def signed_out(path):
        raise TranscriberError("rvc_sign_in_required", "Open this recording once in Chrome and sign in to HKUST, then retry.", 409)

    service._resolve = signed_out
    client.post(f"{base}/{first['id']}/transcribe")
    job = wait_for_job(client)
    assert job["state"] == "failed" and "sign in" in job["message"]
    assert client.get(f"{base}/{first['id']}").json()["source"]["status"] == "failed"

    service._resolve = lambda path: "https://stream01.ust.hk/p.m3u8"
    assert client.post(f"{base}/{second['id']}/transcribe").status_code == 202
    deadline = time.monotonic() + 10
    while client.get("/api/transcriber").json()["job"].get("event") != "finding recording" and service._process is None:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    busy = client.post(f"{base}/{first['id']}/transcribe")
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "transcriber_busy"
    assert client.get(f"{base}/{first['id']}").json()["source"]["status"] == "failed"
    while service._process is None:
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert client.post("/api/transcriber/stop").json() == {"stopped": True}
    job = wait_for_job(client)
    assert job["state"] == "cancelled"
    assert client.get(f"{base}/{second['id']}").json()["source"]["status"] == "not_synced"
    assert client.delete("/api/transcriber").json() == {"removed": True}
    assert not service.root.exists()
    assert sys.executable  # supervisor ran with this interpreter in a source checkout
