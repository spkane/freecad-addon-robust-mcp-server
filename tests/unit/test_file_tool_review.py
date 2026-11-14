"""Exercise routing of model-selected file paths to local review."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from freecad_mcp.bridge.base import ExecutionResult
from freecad_mcp.bridge.file_review import file_review_target
from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge
from freecad_mcp.tools.documents import register_document_tools


class Tools:
    """Collect registered functions without running an MCP transport."""

    def __init__(self):
        self.functions = {}

    def tool(self, **_kwargs):
        def register(function):
            self.functions[function.__name__] = function
            return function

        return register


def _result(path: str) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        result={"name": "Doc", "path": path},
        stdout="",
        stderr="",
        execution_time_ms=1,
    )


@pytest.mark.asyncio
async def test_open_document_reviews_its_exact_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit path uses the reviewed protocol rather than raw execution."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    bridge.execute_reviewed_file = AsyncMock(return_value=_result("/tmp/model.FCStd"))
    bridge._send_request = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    result = await mcp.functions["open_document"]("/tmp/model.FCStd")
    assert result["name"] == "Doc"
    args = bridge.execute_reviewed_file.await_args.args
    assert args[1:] == ("/tmp/model.FCStd", "read", "path")
    assert "FreeCAD.openDocument" in args[0]
    bridge._send_request.assert_not_awaited()
    assert file_review_target.get() is None


@pytest.mark.asyncio
async def test_existing_document_save_uses_reviewed_path() -> None:
    """Implicit saves bind the current path and document before approval."""
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(
            return_value=SimpleNamespace(name="Model", path="/tmp/model.FCStd")
        ),
        save_document=AsyncMock(return_value="/tmp/model.FCStd"),
    )
    observed = []

    async def save(name, path):
        observed.append((name, path, file_review_target.get()))
        return path

    bridge.save_document.side_effect = save
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["save_document"]()
    assert observed == [
        ("Model", "/tmp/model.FCStd", ("/tmp/model.FCStd", "write", "path"))
    ]
    assert file_review_target.get() is None


@pytest.mark.asyncio
async def test_close_with_save_propagates_review_denial() -> None:
    """Denying a save does not silently close the document."""
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(
            return_value=SimpleNamespace(name="Model", path="/tmp/model.FCStd")
        ),
        get_documents=AsyncMock(
            return_value=[SimpleNamespace(name="Model", path="/tmp/model.FCStd")]
        ),
        save_document=AsyncMock(side_effect=ToolError("ReviewDenied")),
        close_document=AsyncMock(),
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match="ReviewDenied"):
        await mcp.functions["close_document"](save_changes=True)
    bridge.close_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_with_save_keeps_original_active_document() -> None:
    """A switch of the active document during approval cannot close another one."""
    doc = SimpleNamespace(name="Model", path="/tmp/model.FCStd")
    bridge = SimpleNamespace(
        get_active_document=AsyncMock(return_value=doc),
        get_documents=AsyncMock(return_value=[doc]),
        save_document=AsyncMock(return_value=doc.path),
        close_document=AsyncMock(),
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["close_document"](save_changes=True)
    bridge.close_document.assert_awaited_once_with("Model")


@pytest.mark.asyncio
async def test_explicit_automation_override_uses_existing_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an explicit local server setting bypasses the review path."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=True),
    )
    bridge: Any = SocketBridge()
    bridge._send_request = AsyncMock(
        return_value={"success": True, "result": {"name": "Doc"}}
    )
    bridge.execute_reviewed_file = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await mcp.functions["open_document"]("/tmp/model.FCStd")
    bridge._send_request.assert_awaited_once()
    bridge.execute_reviewed_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_xmlrpc_has_no_unreviewed_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the local socket review protocol, file operations fail closed."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = XmlRpcBridge()
    bridge._run_proxy_call = AsyncMock()
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match="ReviewUnavailable"):
        await mcp.functions["open_document"]("/tmp/model.FCStd")
    bridge._run_proxy_call.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type", ["ReviewDenied", "FileTargetChanged", "ReviewExecutionUnknown"]
)
async def test_review_failures_are_not_hidden_by_generic_tool_errors(
    monkeypatch: pytest.MonkeyPatch, error_type: str
) -> None:
    """Denial, target replacement, and unknown execution remain distinguishable."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    bridge.execute_reviewed_file = AsyncMock(
        return_value=ExecutionResult(
            success=False,
            result=None,
            stdout="",
            stderr="review stopped",
            execution_time_ms=0,
            error_type=error_type,
        )
    )
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    with pytest.raises(ToolError, match=error_type):
        await mcp.functions["open_document"]("/tmp/model.FCStd")


@pytest.mark.asyncio
async def test_concurrent_file_targets_do_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel requests retain separate task-local targets."""
    monkeypatch.setattr(
        "freecad_mcp.config.get_config",
        lambda: SimpleNamespace(allow_unreviewed_file_operations=False),
    )
    bridge: Any = SocketBridge()
    seen = []

    async def review(_code, path, action, kind, timeout_ms=None):
        assert timeout_ms is None
        await asyncio.sleep(0)
        seen.append((path, action, kind, file_review_target.get()))
        return _result(path)

    bridge.execute_reviewed_file = AsyncMock(side_effect=review)
    mcp = Tools()

    async def get_bridge():
        return bridge

    register_document_tools(mcp, get_bridge)
    await asyncio.gather(
        mcp.functions["open_document"]("/tmp/a.FCStd"),
        mcp.functions["open_document"]("/tmp/b.FCStd"),
    )
    assert sorted(seen) == [
        ("/tmp/a.FCStd", "read", "path", ("/tmp/a.FCStd", "read", "path")),
        ("/tmp/b.FCStd", "read", "path", ("/tmp/b.FCStd", "read", "path")),
    ]
