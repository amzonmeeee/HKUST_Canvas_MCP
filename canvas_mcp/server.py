from __future__ import annotations

import argparse
import os
from inspect import Parameter, Signature
from typing import Any

from fastmcp import FastMCP

from auth import ensure_canvas_auth_configured
from specs.registry import TOOL_SPECS, dispatch_tool_call
from specs.schema import ToolSpec

mcp = FastMCP("canvas-mcp")
WRITE_TOOL_NAMES = frozenset(
    spec.name
    for spec in TOOL_SPECS
    if (spec.annotations or {}).get("readOnlyHint") is False
)
_writes_enabled = False


def configure_permissions(*, allow_writes: bool) -> None:
    global _writes_enabled
    _writes_enabled = allow_writes
    if allow_writes:
        mcp.enable(names=set(WRITE_TOOL_NAMES), components={"tool"})
    else:
        mcp.disable(names=set(WRITE_TOOL_NAMES), components={"tool"})


def _annotation_from_schema(parameter_schema: dict[str, Any]) -> Any:
    type_name = parameter_schema.get("type")
    if type_name == "string":
        return str
    if type_name == "integer":
        return int
    if type_name == "boolean":
        return bool
    if type_name == "array":
        item_schema = parameter_schema.get("items", {})
        item_type = _annotation_from_schema(item_schema)
        return list[item_type if item_type is not Any else Any]
    return Any


def _signature_for_spec(spec: ToolSpec) -> Signature:
    properties = spec.parameters.get("properties", {})
    required = set(spec.parameters.get("required", []))
    parameters: list[Parameter] = []

    for name, parameter_schema in properties.items():
        annotation = _annotation_from_schema(parameter_schema)
        default: Any = Parameter.empty
        if name not in required:
            annotation = annotation | None
            default = None
        parameters.append(
            Parameter(
                name=name,
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=annotation,
            )
        )

    return Signature(parameters=parameters, return_annotation=dict[str, Any])


def _register_tool(spec: ToolSpec) -> None:
    def _tool(**kwargs: Any) -> dict[str, Any]:
        if spec.name in WRITE_TOOL_NAMES and not _writes_enabled:
            return {
                "error": "mcp_read_only",
                "message": "Canvas MCP is read-only. Restart with --allow-writes to enable preview-and-confirm mutations.",
            }
        args = {key: value for key, value in kwargs.items() if value is not None}
        return dispatch_tool_call(spec.name, args)

    signature = _signature_for_spec(spec)
    annotations = {
        parameter.name: parameter.annotation
        for parameter in signature.parameters.values()
    }
    annotations["return"] = dict[str, Any]
    _tool.__name__ = spec.name
    _tool.__doc__ = spec.description
    _tool.__signature__ = signature
    _tool.__annotations__ = annotations
    mcp.tool(
        _tool,
        name=spec.name,
        description=spec.description,
        annotations=spec.annotations,
    )


for tool_spec in TOOL_SPECS:
    _register_tool(tool_spec)

configure_permissions(allow_writes=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Canvas FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "streamable-http", "sse"),
        default="stdio",
        help="Transport to expose. FastMCP recommends http for network access.",
    )
    parser.add_argument("--host", help="Host interface for HTTP-based transports.")
    parser.add_argument("--port", type=int, help="Port for HTTP-based transports.")
    permissions = parser.add_mutually_exclusive_group()
    permissions.add_argument(
        "--allow-writes",
        action="store_true",
        default=None,
        help="Enable mutation tools. Existing preview and explicit human confirmation are still required.",
    )
    permissions.add_argument(
        "--read-only",
        action="store_false",
        dest="allow_writes",
        help="Expose only read tools, overriding CANVAS_MCP_ALLOW_WRITES.",
    )
    parser.add_argument(
        "--path",
        help="Custom MCP endpoint path for HTTP-based transports (default FastMCP path is /mcp for http).",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable the FastMCP startup banner.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    allow_writes = args.allow_writes
    if allow_writes is None:
        value = os.getenv("CANVAS_MCP_ALLOW_WRITES", "").strip().lower()
        if value not in {"", "0", "1", "false", "true"}:
            parser.error("CANVAS_MCP_ALLOW_WRITES must be 0/1 or false/true.")
        allow_writes = value in {"1", "true"}
    configure_permissions(allow_writes=allow_writes)
    ensure_canvas_auth_configured()

    run_kwargs: dict[str, Any] = {"show_banner": not args.no_banner}
    if args.transport != "stdio":
        if args.host is not None:
            run_kwargs["host"] = args.host
        if args.port is not None:
            run_kwargs["port"] = args.port
        if args.path is not None:
            run_kwargs["path"] = args.path

    mcp.run(args.transport, **run_kwargs)


if __name__ == "__main__":
    main()
