"""Optional local transcription of HKUST RVC recordings.

The transcriber is a separate project (RVC_Transcriber). It is not bundled: the user installs it
from a recording's detail view. The workbench then downloads one pinned commit, checks its git
tree hash, and calls its command line. That component downloads its own Python, FFmpeg and speech
model into its own runtime folder. Audio stays on this computer.
"""

from __future__ import annotations

import atexit
import hashlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from .. import rvc
from ..db import now
from .canvas import CanvasServiceError

COMPONENT_REPO = "amzonmeeee/RVC_Transcriber"
COMPONENT_COMMIT = "f331c871668c96e48835f78aa23dcd6184a9cbc2"
COMPONENT_TREE = "7c10dc2a26ad9c0bfb9a4ad897b5f927a6dcfdb6"
MAX_SOURCE_ARCHIVE = 20 * 1024 * 1024
MODELS = ("auto", "qwen3-asr-1.7b", "qwen3-asr-0.6b", "whisper-large-v3")
# Developer override: use an existing RVC_Transcriber checkout instead of the pinned download.
CHECKOUT_ENV = "CANVAS_RVC_TRANSCRIBER_PATH"


class TranscriberError(CanvasServiceError):
    pass


def git_tree_hash(folder: Path) -> str:
    """The git tree SHA-1 of a folder, independent of how the archive was compressed."""
    entries = []
    for child in folder.iterdir():
        if child.is_symlink():
            raise TranscriberError("component_invalid", "The transcriber download contains a link.", 502)
        if child.is_dir():
            entries.append((child.name, b"40000", git_tree_hash(child)))
        else:
            data = child.read_bytes()
            mode = b"100755" if child.stat().st_mode & 0o111 else b"100644"
            digest = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
            entries.append((child.name, mode, digest))
    entries.sort(key=lambda e: e[0].encode() + (b"/" if e[1] == b"40000" else b""))
    body = b"".join(m + b" " + n.encode() + b"\0" + bytes.fromhex(h) for n, m, h in entries)
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def extract_source(archive: bytes, destination: Path) -> Path:
    """Extract a GitHub source tarball (one top folder, regular files and folders only)."""
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.type != tarfile.XGLTYPE]
        tops = {Path(m.name).parts[0] for m in members if m.name}
        if len(tops) != 1:
            raise TranscriberError("component_invalid", "Unexpected transcriber archive layout.", 502)
        for member in members:
            parts = Path(member.name).parts
            if member.name.startswith("/") or ".." in parts or not (member.isfile() or member.isdir()):
                raise TranscriberError("component_invalid", "Unsafe path in transcriber archive.", 502)
            target = destination.joinpath(*parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    return destination / tops.pop()


class TranscriberService:
    def __init__(
        self,
        data_dir: Path,
        store,
        sources,
        canvas,
        *,
        fetch=None,
        stream_resolver=None,
        python=None,
    ):
        self.root = Path(data_dir) / "components" / "rvc-transcriber"
        self.store, self.sources, self.canvas = store, sources, canvas
        self._fetch = fetch or self._download
        self._resolve = stream_resolver or self._resolve_stream
        self._python_override = python
        self._lock = threading.Lock()
        self._job = None
        self._process = None
        atexit.register(self._stop_process)

    # ------------------------------------------------------------------ state

    def _state_path(self):
        return self.root / "state.json"

    def _state(self):
        try:
            return json.loads(self._state_path().read_text())
        except (OSError, ValueError):
            return {}

    def _save_state(self, state):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = self._state_path().with_suffix(".partial")
        temp.write_text(json.dumps(state))
        os.replace(temp, self._state_path())

    def status(self):
        state, job = self._state(), self._job
        installed = bool(state.get("installed_model")) and self._checkout_path(verify=False) is not None
        return {
            "installed": installed,
            "model": state.get("installed_model"),
            "component_commit": state.get("commit") if installed else None,
            "disk_bytes": self._disk_bytes() if self.root.exists() else 0,
            "job": dict(job) if job else None,
        }

    def _disk_bytes(self):
        total = 0
        for base, _dirs, files in os.walk(self.root, followlinks=False):
            for name in files:
                path = Path(base) / name
                if not path.is_symlink():
                    total += path.stat().st_size
        return total

    def recover(self):
        """At startup no job runs. Mark transcriptions that a previous app session left as resumable."""
        from contextlib import closing

        with closing(self.store.repository._connect()) as db, db:
            db.execute(
                """UPDATE sources SET status='not_synced',error_code='transcription_interrupted',
                error_message=?,updated_at=? WHERE kind='recording' AND status='transcribing'""",
                ("Transcription stopped when the app closed. Transcribe again to continue.", now()),
            )

    # -------------------------------------------------------------- component

    def _checkout_path(self, *, verify=True):
        override = os.environ.get(CHECKOUT_ENV)
        if override:
            path = Path(override).expanduser().resolve()
            return path if (path / "launcher.py").is_file() else None
        path = self.root / "source" / COMPONENT_COMMIT
        marker = path / ".workbench-verified"
        if not (path / "launcher.py").is_file() or not marker.is_file():
            return None
        if verify and marker.read_text().strip() != COMPONENT_TREE:
            return None
        return path

    @staticmethod
    def _download(url, max_bytes):
        import requests

        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                data = bytearray()
                for block in response.iter_content(1024 * 1024):
                    data += block
                    if len(data) > max_bytes:
                        raise TranscriberError("component_invalid", "A transcriber download is too large.", 502)
                return bytes(data)
        except requests.RequestException as exc:
            raise TranscriberError(
                "component_download_failed", "The transcriber could not be downloaded. Check your network.", 502
            ) from exc

    def _ensure_checkout(self):
        existing = self._checkout_path()
        if existing:
            return existing
        self._progress(event="downloading transcriber")
        archive = self._fetch(
            f"https://codeload.github.com/{COMPONENT_REPO}/tar.gz/{COMPONENT_COMMIT}", MAX_SOURCE_ARCHIVE
        )
        (self.root / "source").mkdir(parents=True, exist_ok=True, mode=0o700)
        staging = Path(tempfile.mkdtemp(prefix="download-", dir=self.root / "source"))
        try:
            top = extract_source(archive, staging / "x")
            if git_tree_hash(top) != COMPONENT_TREE:
                raise TranscriberError(
                    "component_invalid",
                    "The transcriber download does not match the pinned version. Nothing was installed.",
                    502,
                )
            (top / ".workbench-verified").write_text(COMPONENT_TREE)
            target = self.root / "source" / COMPONENT_COMMIT
            if target.exists():
                shutil.rmtree(target)
            os.replace(top, target)
            return target
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _python(self, checkout):
        """A Python 3.9+ for the transcriber's small standard-library supervisor."""
        if self._python_override:
            return self._python_override
        if not getattr(sys, "frozen", False):
            return sys.executable
        # The packaged app has no general interpreter. Use the component's own pinned uv to get one.
        bootstrap = (checkout / "src/lecture_transcriber/bootstrap.py").read_text()
        version = re.search(r"UV_VERSION = '([^']+)'", bootstrap).group(1)
        digest = re.search(r"UV_SHA256 = '([0-9a-f]{64})'", bootstrap).group(1)
        python_version = re.search(r"PYTHON_VERSION = '([^']+)'", bootstrap).group(1)
        base = self.root / "supervisor"
        uv = base / "uv"
        env = {**self._env(), "UV_PYTHON_INSTALL_DIR": str(base / "python"), "UV_CACHE_DIR": str(base / "cache")}
        if not uv.is_file():
            base.mkdir(parents=True, exist_ok=True, mode=0o700)
            data = self._fetch(
                f"https://github.com/astral-sh/uv/releases/download/{version}/uv-aarch64-apple-darwin.tar.gz",
                80 * 1024 * 1024,
            )
            if hashlib.sha256(data).hexdigest() != digest:
                raise TranscriberError("component_invalid", "The uv download failed its checksum.", 502)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                member = tar.getmember("uv-aarch64-apple-darwin/uv")
                with tar.extractfile(member) as source, open(uv, "wb") as out:
                    shutil.copyfileobj(source, out)
            uv.chmod(0o700)
        subprocess.run([str(uv), "python", "install", python_version, "--no-bin"], env=env, check=True,
                       capture_output=True)
        found = subprocess.run([str(uv), "python", "find", "--managed-python", python_version], env=env,
                               check=True, capture_output=True, text=True)
        return found.stdout.strip()

    @staticmethod
    def _env():
        keep = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SHELL", "TMPDIR")
        env = {k: os.environ[k] for k in keep if k in os.environ}
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        return env

    # ------------------------------------------------------------------- jobs

    def _start(self, job, target):
        with self._lock:
            if self._job and self._job["state"] == "running":
                raise TranscriberError(
                    "transcriber_busy", "The transcriber is busy. Wait for the current job, or stop it.", 409
                )
            self._job = {**job, "state": "running", "event": "starting", "started_at": now(), "message": None}
        thread = threading.Thread(target=self._run_job, args=(target,), daemon=True)
        thread.start()
        return dict(self._job)

    def _progress(self, **update):
        if self._job:
            self._job.update({k: v for k, v in update.items() if v is not None})

    def _run_job(self, target):
        try:
            target()
            self._progress(state="complete", event="complete")
        except _Cancelled:
            self._progress(state="cancelled", event="stopped", message="Stopped. Run it again to continue.")
        except (TranscriberError, CanvasServiceError) as exc:
            self._progress(state="failed", event="failed", message=str(exc))
        except Exception:  # noqa: BLE001 -- details stay in the component log, not the HTTP response
            self._progress(state="failed", event="failed",
                           message="The transcriber stopped with an error. Retry, or remove and install it again.")
        finally:
            self._process = None
            if self._job:
                self._job["finished_at"] = now()
            if self._job and self._job.get("kind") == "transcribe" and self._job["state"] != "complete":
                self.store.source_status(
                    self._job["source_id"],
                    "not_synced" if self._job["state"] == "cancelled" else "failed",
                    code="transcription_" + self._job["state"],
                    message=self._job.get("message"),
                )

    def _command(self, checkout, *args):
        """Run the component; parse @@progress lines; raise on failure."""
        python = self._python(checkout)
        tail = deque(maxlen=12)
        process = subprocess.Popen(
            [python, "-B", str(checkout / "launcher.py"), *args],
            cwd=checkout,
            env=self._env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self._process = process
        for line in process.stdout:
            line = line.rstrip("\n")
            if line.startswith("@@progress "):
                try:
                    data = json.loads(line[len("@@progress "):])
                except ValueError:
                    continue
                self._progress(**{k: data.get(k) for k in ("event", "segment", "segments", "audio_time", "model")})
            elif line.strip():
                tail.append(line)
        code = process.wait()
        if self._job and self._job.get("cancel_requested"):
            raise _Cancelled
        if code:
            detail = next((t[7:] for t in reversed(tail) if t.startswith("ERROR: ")), None)
            raise TranscriberError(
                "transcriber_failed",
                (detail or "The transcriber stopped with an error.")[:400],
                502,
            )

    def cancel(self):
        job = self._job
        if not job or job["state"] != "running":
            return {"stopped": False}
        job["cancel_requested"] = True
        self._stop_process(signal.SIGINT)
        return {"stopped": True}

    def shutdown(self):
        if self._job and self._job.get("state") == "running":
            self._job["cancel_requested"] = True
        self._stop_process(signal.SIGINT)

    def _stop_process(self, signum=signal.SIGTERM):
        process = self._process
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                pass

    # ---------------------------------------------------------------- install

    def install(self, model="auto"):
        if model not in MODELS:
            raise TranscriberError("invalid_model", "Unknown transcription model.", 422)
        if sys.platform != "darwin" or os.uname().machine != "arm64":
            raise TranscriberError("unsupported_platform", "Transcription needs an Apple Silicon Mac.", 409)

        def work():
            checkout = self._ensure_checkout()
            self._progress(event="preparing environment")
            self._command(checkout, "install", "--model", model, "--json-progress", "--yes")
            self._save_state({
                "commit": COMPONENT_COMMIT if not os.environ.get(CHECKOUT_ENV) else "local",
                "installed_model": self._job.get("model") or model,
                "installed_at": now(),
            })

        return self._start({"kind": "install", "model": None if model == "auto" else model}, work)

    def remove(self):
        with self._lock:
            if self._job and self._job["state"] == "running":
                raise TranscriberError("transcriber_busy", "Stop the current job before you remove the transcriber.", 409)
            if self.root.is_symlink():
                raise TranscriberError("storage_error", "Transcriber storage cannot be a symbolic link.", 409)
            if self.root.exists():
                shutil.rmtree(self.root)
            self._job = None
        return {"removed": True}

    # ------------------------------------------------------------- transcribe

    def _resolve_stream(self, media_path):
        import requests

        from auth.chrome_cookies import read_domain_cookies
        from auth.profiles import resolve_chrome_profile_path

        try:
            cookies = read_domain_cookies("rvcmedia.ust.hk", profile_path=resolve_chrome_profile_path())
        except Exception:  # noqa: BLE001 -- browser/keychain errors must not leak details
            cookies = []
        with requests.Session() as session:
            for cookie in cookies:
                session.cookies.set_cookie(cookie)
            response = session.get(
                rvc.RVCMEDIA + "/Media/Play", params={"path": media_path}, allow_redirects=False, timeout=30
            )
        stream = rvc.parse_player(response.text) if response.status_code == 200 else None
        if not stream:
            raise TranscriberError(
                "rvc_sign_in_required",
                "Open this recording once in Chrome and sign in to HKUST, then retry.",
                409,
            )
        return stream

    def transcribe(self, workspace, source):
        if source["kind"] != "recording":
            raise TranscriberError("not_a_recording", "Only RVC recordings can be transcribed.", 422)
        if not self.status()["installed"]:
            raise TranscriberError("transcriber_not_installed", "Install the transcriber first.", 409)
        model = self._state().get("installed_model") or "auto"

        def work():
            checkout = self._checkout_path()
            if checkout is None:
                raise TranscriberError("transcriber_not_installed", "Install the transcriber again.", 409)
            self._progress(event="finding recording")
            page = self.canvas.client_call(
                "get_page", course_id=workspace["canvas_course_id"], url_or_id=source["canvas_object_id"]
            )
            paths = rvc.media_paths(page.get("body") or "")
            if not paths:
                raise TranscriberError("no_recording", "This page has no RVC player.", 422)
            title = page.get("title") or source["title"]
            streams = []
            for number, path in enumerate(paths, 1):
                name = rvc.safe_name(title) + ("" if number == 1 else f"-part{number}")
                streams.append({"name": name, "stream": self._resolve(path), "stream_id": path})
            folder = self.root / "jobs" / source["id"]
            output = folder / "out"
            output.mkdir(parents=True, exist_ok=True, mode=0o700)
            streams_file = folder / "streams.json"
            streams_file.write_text(json.dumps(streams))
            streams_file.chmod(0o600)
            try:
                self._command(
                    checkout, "streams", "--streams", str(streams_file), "--output", str(output),
                    "--model", model, "--timestamps", "--keep-runtime", "--resume", "--json-progress", "--yes",
                )
            finally:
                # The file holds short-lived stream tokens; never keep it after the run.
                streams_file.unlink(missing_ok=True)
            texts = [(output / (s["name"] + ".txt")).read_text(encoding="utf-8") for s in streams]
            self.sources.index_transcript(source, title, texts, model=self._job.get("model") or model)
            shutil.rmtree(folder, ignore_errors=True)

        self.store.source_status(source["id"], "transcribing")
        try:
            return self._start(
                {"kind": "transcribe", "source_id": source["id"], "workspace_id": workspace["id"], "title": source["title"]},
                work,
            )
        except TranscriberError:
            self.store.source_status(source["id"], source["status"])
            raise


class _Cancelled(Exception):
    pass
