from __future__ import annotations

import errno
import os
import secrets
import socket
import threading
import time
import webbrowser
from pathlib import Path


def reserve_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            if port == 0 or exc.errno != errno.EADDRINUSE:
                raise
            sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        return sock
    except BaseException:
        sock.close()
        raise


def launch(
    *,
    port: int = 8765,
    open_browser: bool = True,
    data_dir: Path | None = None,
    on_ready=None,
    parent_pid: int | None = None,
):
    import uvicorn

    from .api import create_app

    secret = secrets.token_urlsafe(32)
    sock = reserve_socket(port)
    try:
        actual_port = sock.getsockname()[1]
        app = create_app(port=actual_port, launch_secret=secret, data_dir=data_dir)
        url = f"http://127.0.0.1:{actual_port}/#session={secret}"

        class WorkbenchServer(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if self.started:
                    if on_ready:
                        on_ready(url)
                        print(
                            f"Workbench ready on loopback port {actual_port}.",
                            flush=True,
                        )
                    else:
                        print(f"HKUST Canvas Workbench running at:\n{url}", flush=True)
                    print(
                        "Keep this terminal open. Press Ctrl+C to stop. The launch URL is private to this local session.",
                        flush=True,
                    )
                    if open_browser:
                        try:
                            webbrowser.open(url)
                        except webbrowser.Error:
                            print("Open the URL above in your browser.", flush=True)

        server = WorkbenchServer(
            uvicorn.Config(app, host="127.0.0.1", port=actual_port, access_log=False)
        )
        if parent_pid is not None:

            def monitor_owner():
                while not server.should_exit:
                    if os.getppid() != parent_pid:
                        server.should_exit = True
                        return
                    time.sleep(0.5)

            threading.Thread(target=monitor_owner, daemon=True).start()
        server.run(sockets=[sock])
    finally:
        sock.close()
