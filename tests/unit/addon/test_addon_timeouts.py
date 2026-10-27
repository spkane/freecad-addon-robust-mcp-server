"""Regression tests for workbench execution timeout handling."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ADDON_DIR = Path(__file__).parent.parent.parent.parent / "freecad" / "RobustMCPBridge"


@pytest.fixture
def server_mod(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Import the bundled bridge server without importing the FreeCAD addon."""
    monkeypatch.syspath_prepend(str(ADDON_DIR))
    for name in list(sys.modules):
        if name == "freecad_mcp_bridge" or name.startswith("freecad_mcp_bridge."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module("freecad_mcp_bridge.server")
    yield module
    for name in list(sys.modules):
        if name == "freecad_mcp_bridge" or name.startswith("freecad_mcp_bridge."):
            del sys.modules[name]


def test_xmlrpc_execute_accepts_timeout_and_preserves_one_argument_clients(
    server_mod: Any,
) -> None:
    """XML-RPC should forward overrides while retaining its legacy default."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_via_queue = MagicMock(return_value={"success": True})

    plugin._xmlrpc_execute("first")
    plugin._xmlrpc_execute("second", 60000)

    assert plugin._execute_via_queue.call_args_list == [
        call("first", 30000),
        call("second", 60000),
    ]


@pytest.mark.asyncio
async def test_socket_execute_forwards_timeout(server_mod: Any) -> None:
    """JSON-RPC execute requests should forward their timeout to the queue."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_via_queue = MagicMock(return_value={"success": True})

    response = await plugin._process_jsonrpc_request(
        {
            "jsonrpc": "2.0",
            "id": "request-1",
            "method": "execute",
            "params": {"code": "pass", "timeout_ms": 45000},
        }
    )

    assert response["result"] == {"success": True}
    plugin._execute_via_queue.assert_called_once_with("pass", 45000)


@pytest.mark.parametrize("timeout_ms", [999, 600001, 1.5, True])
def test_execute_via_queue_rejects_invalid_timeout(
    server_mod: Any,
    timeout_ms: object,
) -> None:
    """Protocol clients should not be able to submit invalid wait durations."""
    plugin = server_mod.FreecadMCPPlugin()

    result = plugin._execute_via_queue("pass", timeout_ms)  # type: ignore[arg-type]

    assert result["success"] is False
    assert result["error_type"] == "ValueError"
    assert plugin._request_queue.empty()


def test_timed_out_queued_request_is_not_executed(server_mod: Any) -> None:
    """Work that has not started should be cancelled when its caller times out."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_code_sync = MagicMock(return_value={"success": True})
    request = server_mod.ExecutionRequest("mutate_document()")
    plugin._request_queue.put(request)

    assert request.mark_timed_out() == "cancelled"
    plugin._process_queue()

    plugin._execute_code_sync.assert_not_called()


def test_running_request_reports_that_execution_may_continue(
    server_mod: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeout should state when already-running FreeCAD code cannot stop."""

    class RunningRequest:
        """Execution request stub that is already running at timeout."""

        def __init__(self, _code: str, _timeout_ms: int) -> None:
            self.completed = MagicMock()
            self.completed.wait.return_value = False
            self.result = None

        def mark_timed_out(self) -> str:
            """Report an execution that already entered FreeCAD."""
            return "running"

    monkeypatch.setattr(server_mod, "ExecutionRequest", RunningRequest)
    plugin = server_mod.FreecadMCPPlugin()

    result = plugin._execute_via_queue("mutate_document()", 1000)

    assert result["error_type"] == "TimeoutError"
    assert "may continue" in result["error_message"]
