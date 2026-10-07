from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from webapp import local_clients
from webapp import native_providers as native
from webapp.providers import ProviderError


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    capture = tmp_path / "requests.jsonl"
    script = tmp_path / "fake_codex.py"
    script.write_text("""import json,sys,time
capture=sys.argv[1]
mode=sys.argv[2]
def emit(value):
 print(json.dumps(value),flush=True)
for line in sys.stdin:
 request=json.loads(line)
 with open(capture,'a') as f:f.write(json.dumps(request)+'\\n')
 method=request.get('method')
 identifier=request.get('id')
 if identifier is None:continue
 result={}
 if method=='account/read':result={'account':None if mode=='no_login' else {'type':'chatgpt','email':'PRIVATE'}}
 if method=='config/read':result={'config':{'model':'synthetic-model','mcp_servers':{'existing':{},'with.dot':{}}}}
 if method=='thread/start':result={'thread':{'id':'synthetic-thread'}}
 emit({'id':identifier,'result':result})
 if method=='turn/start':
  if mode=='approval':emit({'id':99,'method':'item/commandExecution/requestApproval','params':{}});continue
  emit({'method':'item/started','params':{'item':{'id':'user','type':'userMessage'}}})
  if mode=='tool':emit({'method':'item/started','params':{'item':{'id':'tool','type':'mcpToolCall'}}});continue
  if mode=='hang':time.sleep(60);continue
  if mode=='malformed':print('PRIVATE INVALID OUTPUT',flush=True);continue
  emit({'method':'item/started','params':{'item':{'id':'thought','type':'agentMessage','channel':'analysis'}}})
  emit({'method':'item/agentMessage/delta','params':{'itemId':'thought','delta':'PRIVATE REASONING'}})
  emit({'method':'item/started','params':{'item':{'id':'answer','type':'agentMessage','channel':'final'}}})
  text='{"answer":"synthetic"}' if 'outputSchema' in request['params'] else 'Synthetic answer.'
  if mode!='failed':emit({'method':'item/agentMessage/delta','params':{'itemId':'answer','delta':text}})
  emit({'method':'item/completed','params':{'item':{'id':'answer','type':'agentMessage','channel':'final','text':text}}})
  emit({'method':'turn/completed','params':{'turn':{'status':'failed' if mode=='failed' else 'completed','error':{'message':'PRIVATE ERROR'}}}})
""")

    def select(mode="success"):
        monkeypatch.setattr(
            native,
            "codex_command",
            lambda: [sys.executable, str(script), str(capture), mode],
        )

    select()
    return select, capture


def collect(provider, **kwargs):
    async def run():
        return [
            event
            async for event in provider.stream_chat(
                [
                    {"role": "system", "content": "Synthetic policy"},
                    {"role": "user", "content": "Synthetic question"},
                ],
                **kwargs,
            )
        ]

    return asyncio.run(run())


def test_codex_stream_and_isolated_thread(fake_codex):
    _, capture = fake_codex
    events = collect(native.CodexProvider({"model": "synthetic-model"}))
    assert [e["type"] for e in events] == ["message_start", "text_delta", "message_end"]
    assert events[1]["text"] == "Synthetic answer."
    requests = [json.loads(line) for line in capture.read_text().splitlines()]
    params = next(r["params"] for r in requests if r["method"] == "thread/start")
    assert params["ephemeral"] is True
    assert params["sandbox"] == "read-only" and params["approvalPolicy"] == "never"
    assert params["config"] == {
        "mcp_servers": {"existing": {"enabled": False}, "with.dot": {"enabled": False}},
    }
    assert not Path(params["cwd"]).exists()
    assert params["model"] == "synthetic-model"
    assert "PRIVATE" not in json.dumps(events)


@pytest.mark.parametrize(
    "mode,code",
    [
        ("no_login", "cli_auth"),
        ("failed", "cli_generation_failed"),
        ("tool", "cli_tools_disabled"),
        ("approval", "cli_tools_disabled"),
        ("malformed", "cli_protocol_error"),
    ],
)
def test_codex_rejects_unsafe_or_incomplete_output(fake_codex, mode, code):
    select, _ = fake_codex
    select(mode)
    with pytest.raises(ProviderError) as error:
        collect(native.CodexProvider({"model": "default"}))
    assert error.value.code == code
    assert "PRIVATE" not in str(error.value)


def test_codex_schema_uses_native_contract_and_local_validation(fake_codex):
    _, capture = fake_codex
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string", "minLength": 1}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    result = asyncio.run(
        native.CodexProvider({"model": "default"}).generate_structured(
            [{"role": "user", "content": "Synthetic question"}], schema
        )
    )
    assert result == {"answer": "synthetic"}
    requests = [json.loads(line) for line in capture.read_text().splitlines()]
    wire = next(
        r["params"]["outputSchema"] for r in requests if r["method"] == "turn/start"
    )
    assert "minLength" not in wire["properties"]["answer"]


def test_codex_timeout_cleans_process_and_cwd(fake_codex, monkeypatch):
    select, capture = fake_codex
    select("hang")
    monkeypatch.setattr(native, "TIMEOUT", 0.15)
    with pytest.raises(ProviderError) as error:
        collect(native.CodexProvider({"model": "default"}))
    assert error.value.code == "provider_timeout"
    params = next(
        json.loads(line)["params"]
        for line in capture.read_text().splitlines()
        if json.loads(line).get("method") == "thread/start"
    )
    assert not Path(params["cwd"]).exists()


def test_cancel_closes_ephemeral_process(fake_codex, monkeypatch):
    select, _ = fake_codex
    select("hang")
    processes = []
    spawn = asyncio.create_subprocess_exec

    async def capture(*args, **kwargs):
        process = await spawn(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(native.asyncio, "create_subprocess_exec", capture)

    async def run():
        iterator = native.CodexProvider({"model": "default"}).stream_chat(
            [{"role": "user", "content": "Synthetic"}]
        )
        assert (await anext(iterator))["type"] == "message_start"
        task = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await iterator.aclose()

    asyncio.run(run())
    assert len(processes) == 1 and processes[0].returncode is not None


def test_codex_boot_flags_disable_external_execution(monkeypatch):
    monkeypatch.setattr(native, "find_cli", lambda _: "/synthetic/codex")
    args = native.codex_command()
    assert args[:3] == ["/synthetic/codex", "app-server", "--stdio"]
    for name in native.DISABLED_FEATURES:
        assert f"features.{name}=false" in args
    assert 'approval_policy="never"' in args and 'sandbox_mode="read-only"' in args
    assert 'web_search="disabled"' in args
    assert "project_doc_max_bytes=0" in args


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    capture = tmp_path / "claude_input.json"
    script.write_text("""import sys,json
with open(sys.argv[1],'w') as f:f.write(sys.stdin.read())
mode=sys.argv[2]
def emit(d):print(json.dumps(d),flush=True)
emit({'type':'system','subtype':'init','tools':['Bash'] if mode=='tool' else ['StructuredOutput'] if mode=='schema_tool' else [],'mcp_servers':[]})
if mode=='schema_tool':emit({'type':'stream_event','event':{'type':'content_block_start','content_block':{'type':'tool_use','name':'StructuredOutput'}}})
if mode=='malformed':print('PRIVATE MALFORMED',flush=True);sys.exit(0)
emit({'type':'stream_event','event':{'type':'content_block_delta','delta':{'type':'text_delta','text':'Synthetic answer.'}}})
emit({'type':'result','subtype':'success' if mode!='error' else 'error','is_error':mode=='error','result':'Synthetic answer.','errors':['PRIVATE'],'structured_output':{'answer':'synthetic'}})
""")
    recorded = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        recorded.append(args)
        return await original(
            sys.executable, str(script), str(capture), mode[0], **kwargs
        )

    mode = ["success"]
    monkeypatch.setattr(native, "find_cli", lambda _: "/synthetic/claude")
    monkeypatch.setattr(native.asyncio, "create_subprocess_exec", spawn)
    return mode, recorded, capture


def test_claude_stream_has_no_duplicate_result_and_no_prompt_in_argv(fake_claude):
    _, recorded, capture = fake_claude
    events = collect(native.ClaudeCodeProvider({"model": "default"}))
    assert [e["type"] for e in events] == ["message_start", "text_delta", "message_end"]
    args = recorded[0]
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args and "--no-session-persistence" in args
    assert "Synthetic question" not in " ".join(args)
    assert "Synthetic question" in capture.read_text()


@pytest.mark.parametrize(
    "mode,code",
    [
        ("tool", "cli_tools_disabled"),
        ("error", "cli_generation_failed"),
        ("malformed", "cli_protocol_error"),
    ],
)
def test_claude_errors_are_sanitized(fake_claude, mode, code):
    modes, _, _ = fake_claude
    modes[0] = mode
    with pytest.raises(ProviderError) as error:
        collect(native.ClaudeCodeProvider({"model": "default"}))
    assert error.value.code == code and "PRIVATE" not in str(error.value)


def test_claude_native_schema_is_validated(fake_claude):
    modes, _, _ = fake_claude
    modes[0] = "schema_tool"
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    result = asyncio.run(
        native.ClaudeCodeProvider({"model": "default"}).generate_structured(
            [{"role": "user", "content": "Synthetic"}], schema
        )
    )
    assert result == {"answer": "synthetic"}


def test_desktop_config_merge_is_private_and_preserves_other_entries(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        local_clients, "desktop_path", lambda _: tmp_path / "Claude.app"
    )
    monkeypatch.setattr(
        local_clients,
        "mcp_launcher",
        lambda _: {
            "command": "/synthetic/canvas-mcp",
            "args": ["--transport", "stdio"],
        },
    )
    path = tmp_path / "Library/Application Support/Claude/claude_desktop_config.json"
    path.parent.mkdir(parents=True)
    original = {
        "preferences": {"keep": True},
        "mcpServers": {"other": {"command": "keep"}},
    }
    path.write_text(json.dumps(original))
    result = asyncio.run(local_clients.connect_desktop("claude", "Synthetic profile"))
    saved = json.loads(path.read_text())
    assert saved["preferences"] == original["preferences"]
    assert saved["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert "hkust-canvas" in saved["mcpServers"]
    assert result["restart_required"] is True
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_malformed_desktop_config_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        local_clients, "desktop_path", lambda _: tmp_path / "Claude.app"
    )
    path = tmp_path / "Library/Application Support/Claude/claude_desktop_config.json"
    path.parent.mkdir(parents=True)
    path.write_text("PRIVATE MALFORMED")
    with pytest.raises(ProviderError) as error:
        asyncio.run(local_clients.connect_desktop("claude", None))
    assert path.read_text() == "PRIVATE MALFORMED" and "PRIVATE" not in str(error.value)
