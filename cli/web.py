from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer


def register(app: typer.Typer):
    @app.command("web")
    def web(
        port: Annotated[
            int,
            typer.Option(
                min=0,
                max=65535,
                help="Preferred loopback port; 0 chooses an unused port.",
            ),
        ] = 8765,
        open_browser: Annotated[
            bool,
            typer.Option(
                "--open/--no-open", help="Open the local workbench in your browser."
            ),
        ] = True,
        data_dir: Annotated[
            Path | None,
            typer.Option(help="Store local app data outside the repository."),
        ] = None,
    ):
        """Start the optional localhost study workbench."""
        try:
            from webapp.launcher import launch

            launch(port=port, open_browser=open_browser, data_dir=data_dir)
        except ModuleNotFoundError as exc:
            if exc.name not in {"fastapi", "uvicorn", "starlette"}:
                raise
            typer.echo(
                "Web dependencies are missing. Install hkust-canvas-mcp[web], or run uv sync --extra web in this repository.",
                err=True,
            )
            raise typer.Exit(1)
        except (OSError, ValueError) as exc:
            typer.echo(f"Could not start the local workbench: {exc}", err=True)
            raise typer.Exit(1)
