"""Tests for XML-RPC bridge timeout and concurrency behavior."""

from __future__ import annotations

import asyncio
import threading
import time
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, call

import pytest

from freecad_mcp.bridge.xmlrpc import (
    EXECUTION_RESPONSE_GRACE_SECONDS,
    LEGACY_EXECUTE_ARITY_FAULT,
    AuthenticatedXmlRpcTransport,
    XmlRpcBridge,
)


def test_authenticated_transport_refuses_legacy_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server without challenge support never receives the XML request."""
    connection = MagicMock()
    connection.getresponse.return_value.status = 404
    monkeypatch.setattr(
        "http.client.HTTPConnection", lambda *_args, **_kwargs: connection
    )
    transport = AuthenticatedXmlRpcTransport("paired", lambda _: b"proof", 2.0)
    with pytest.raises(ConnectionError, match="challenge"):
        transport.request("localhost:9875", "/RPC2", b"<methodCall/>")
    connection.request.assert_called_once_with("GET", "/challenge")


def test_authenticated_transport_never_retries_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed POST may have executed and must not be sent a second time."""
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = b"A" * 43
    connection.request.side_effect = [None, ConnectionResetError("reset")]
    monkeypatch.setattr(
        "http.client.HTTPConnection", lambda *_args, **_kwargs: connection
    )
    transport = AuthenticatedXmlRpcTransport("paired", lambda _: b"proof", 2.0)
    with pytest.raises(ConnectionResetError):
        transport.request("localhost:9875", "/RPC2", b"<methodCall/>")
    assert connection.request.call_count == 2
    assert connection.request.call_args_list[1].args[0] == "POST"


def _connected_bridge(
    *, execution_timeout_ms: int = 30000
) -> tuple[XmlRpcBridge, MagicMock]:
    """Create a bridge with an isolated mocked proxy and executor."""
    bridge = XmlRpcBridge(execution_timeout_ms=execution_timeout_ms)
    proxy = MagicMock()
    bridge._proxy = proxy
    bridge._executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="test-freecad-xmlrpc",
    )
    return bridge, proxy


@pytest.mark.asyncio
async def test_execute_python_passes_configured_timeout_to_server() -> None:
    """An omitted per-call timeout should use the configured bridge default."""
    bridge, proxy = _connected_bridge(execution_timeout_ms=45000)
    proxy.execute.return_value = {"success": True, "result": "done"}

    try:
        result = await bridge.execute_python("_result_ = 'done'")
    finally:
        await bridge.disconnect()

    assert result.success is True
    proxy.execute.assert_called_once_with("_result_ = 'done'", 45000)


@pytest.mark.asyncio
async def test_execute_python_passes_per_call_timeout_to_server() -> None:
    """A per-call timeout should override the configured bridge default."""
    bridge, proxy = _connected_bridge(execution_timeout_ms=45000)
    proxy.execute.return_value = {"success": True, "result": "done"}

    try:
        await bridge.execute_python("_result_ = 'done'", timeout_ms=60000)
    finally:
        await bridge.disconnect()

    proxy.execute.assert_called_once_with("_result_ = 'done'", 60000)


@pytest.mark.asyncio
async def test_execute_python_falls_back_for_legacy_workbench_arity() -> None:
    """The exact prior workbench arity fault should retry with one argument."""
    bridge, proxy = _connected_bridge()
    proxy.execute.side_effect = [
        xmlrpc.client.Fault(1, LEGACY_EXECUTE_ARITY_FAULT),
        {"success": True, "result": "legacy"},
    ]

    try:
        result = await bridge.execute_python("_result_ = 'legacy'")
    finally:
        await bridge.disconnect()

    assert result.success is True
    assert result.result == "legacy"
    assert proxy.execute.call_args_list == [
        call("_result_ = 'legacy'", 30000),
        call("_result_ = 'legacy'"),
    ]


@pytest.mark.asyncio
async def test_execute_python_does_not_retry_unrelated_xmlrpc_fault() -> None:
    """An unrelated XML-RPC TypeError must not re-execute user code."""
    bridge, proxy = _connected_bridge()
    fault = xmlrpc.client.Fault(
        1,
        "<class 'TypeError'>:operation() takes 2 positional arguments but 3 were given",
    )
    proxy.execute.side_effect = fault

    try:
        result = await bridge.execute_python("state_changing_operation()")
    finally:
        await bridge.disconnect()

    assert result.success is False
    assert result.error_type == "Fault"
    assert proxy.execute.call_args_list == [call("state_changing_operation()", 30000)]


@pytest.mark.asyncio
async def test_execute_python_preserves_server_timeout_message() -> None:
    """Server-side timeout details should be exposed to the MCP caller."""
    bridge, proxy = _connected_bridge()
    proxy.execute.return_value = {
        "success": False,
        "error_type": "TimeoutError",
        "error_message": (
            "Execution timed out after 30000ms; "
            "code already running in FreeCAD may continue"
        ),
    }

    try:
        result = await bridge.execute_python("long_operation()")
    finally:
        await bridge.disconnect()

    assert result.success is False
    assert result.error_type == "TimeoutError"
    assert "may continue" in result.stderr


@pytest.mark.asyncio
async def test_execute_python_rejects_invalid_timeout() -> None:
    """Per-call timeouts outside the configured bounds should fail locally."""
    bridge, proxy = _connected_bridge()

    try:
        result = await bridge.execute_python("pass", timeout_ms=999)
    finally:
        await bridge.disconnect()

    assert result.success is False
    assert result.error_type == "ValueError"
    proxy.execute.assert_not_called()


@pytest.mark.asyncio
async def test_xmlrpc_proxy_calls_are_serialized() -> None:
    """Concurrent bridge requests must not share ServerProxy transport state."""
    bridge, proxy = _connected_bridge()
    state_lock = threading.Lock()
    active_calls = 0
    maximum_active_calls = 0

    def execute(_code: str, _timeout_ms: int) -> dict[str, object]:
        nonlocal active_calls, maximum_active_calls
        with state_lock:
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
        time.sleep(0.05)
        with state_lock:
            active_calls -= 1
        return {"success": True, "result": True}

    proxy.execute.side_effect = execute

    try:
        results = await asyncio.gather(
            bridge.execute_python("_result_ = 1", timeout_ms=1000),
            bridge.execute_python("_result_ = 2", timeout_ms=1000),
        )
    finally:
        await bridge.disconnect()

    assert all(result.success for result in results)
    assert maximum_active_calls == 1
    assert EXECUTION_RESPONSE_GRACE_SECONDS > 0
