"""Regression tests for workbench execution timeout handling."""

from __future__ import annotations

import asyncio
import http.client
import importlib
import socket
import sys
import threading
import time
import xmlrpc.client
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call

import pytest

from freecad_mcp.bridge.socket import SocketBridge

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        ([], -32600),
        ({"id": "test", "method": "execute"}, -32600),
        ({"jsonrpc": "2.0", "id": [], "method": "execute"}, -32600),
        ({"jsonrpc": "2.0", "id": 1, "method": "execute", "params": []}, -32602),
    ],
)
async def test_socket_rejects_invalid_request_before_queueing(
    server_mod: Any, payload: Any, error_code: int
) -> None:
    """Malformed JSON-RPC envelopes must not reach the execution queue."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_via_queue = MagicMock()
    response = await plugin._process_jsonrpc_request(payload)
    assert response["error"]["code"] == error_code
    plugin._execute_via_queue.assert_not_called()


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


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1", "example.com", "::"])  # noqa: S104
def test_bridge_rejects_non_loopback_listener(server_mod: Any, host: str) -> None:
    """A bridge listener cannot be configured on a network interface."""
    with pytest.raises(ValueError, match="loopback"):
        server_mod.FreecadMCPPlugin(host=host)


@pytest.mark.parametrize(
    ("host", "expected"),
    [("localhost", "127.0.0.1"), ("127.0.0.2", "127.0.0.2"), ("::1", "::1")],
)
def test_bridge_accepts_literal_loopback_addresses(
    server_mod: Any, host: str, expected: str
) -> None:
    """Localhost resolves to a fixed loopback address without DNS lookup."""
    assert server_mod.FreecadMCPPlugin(host=host)._host == expected


@pytest.mark.parametrize("code", [None, 123, "x" * (64 * 1024 + 1), "\ud800"])
def test_execute_rejects_invalid_or_oversized_code(
    server_mod: Any, code: object
) -> None:
    """Invalid code is rejected before a work request is queued."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_via_queue(code)  # type: ignore[arg-type]
    assert result["success"] is False
    assert result["error_type"] == "ValueError"
    assert plugin._request_queue.empty()


def test_full_queue_rejects_request_without_blocking(server_mod: Any) -> None:
    """A full execution queue rejects new work instead of growing unbounded."""
    plugin = server_mod.FreecadMCPPlugin()
    for _ in range(server_mod.MAX_PENDING_REQUESTS):
        plugin._request_queue.put_nowait(server_mod.ExecutionRequest("pass"))
    result = plugin._execute_via_queue("pass")
    assert result["error_type"] == "Overloaded"
    assert plugin._request_queue.qsize() == server_mod.MAX_PENDING_REQUESTS


def test_xmlrpc_rejects_unsafe_framing_and_xml(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real listener rejects oversized, compressed and DTD requests."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", False)
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", xmlrpc_port=0)
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while plugin._xmlrpc_server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._xmlrpc_server is not None
        port = plugin._xmlrpc_server.server_address[1]

        def post(body: bytes, headers: dict[str, str] | None = None) -> int:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request("POST", "/RPC2", body=body, headers=headers or {})
                response = connection.getresponse()
                response.read()
                return response.status
            finally:
                connection.close()

        ping = xmlrpc.client.dumps((), methodname="ping").encode()
        assert post(ping) == 200
        assert post(b"x" * (server_mod.MAX_BRIDGE_REQUEST_BYTES + 1)) == 413
        assert post(ping, {"Content-Encoding": "gzip"}) == 400
        assert post(b'<!DOCTYPE x [<!ENTITY x "bad">]><methodCall/>') == 400
        assert post(b"\xff\xfe") == 400
    finally:
        plugin._running = False
        thread.join(timeout=3)
        if plugin._xmlrpc_server is not None:
            plugin._xmlrpc_server.server_close()
        assert not thread.is_alive()


def test_xmlrpc_total_read_deadline_stops_a_slow_client(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trickled headers cannot hold the XML-RPC listener indefinitely."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", False)
    monkeypatch.setattr(server_mod, "REQUEST_READ_TIMEOUT_SECONDS", 0.25)
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", xmlrpc_port=0)
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while plugin._xmlrpc_server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._xmlrpc_server is not None
        port = plugin._xmlrpc_server.server_address[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            client.sendall(b"POST /RPC2 HTTP/1.1\r\nX-Slow: ")
            for _ in range(6):
                time.sleep(0.06)
                try:
                    client.sendall(b"x")
                except OSError:
                    break
            try:
                assert client.recv(1) == b""
            except ConnectionResetError:
                pass
    finally:
        plugin._running = False
        thread.join(timeout=3)
        if plugin._xmlrpc_server is not None:
            plugin._xmlrpc_server.server_close()
        assert not thread.is_alive()


def test_xmlrpc_can_bind_ipv6_loopback_when_available(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The validated IPv6 loopback host uses an IPv6 XML-RPC listener."""
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::1", 0))
    except OSError:
        pytest.skip("IPv6 loopback is unavailable")

    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", False)
    plugin = server_mod.FreecadMCPPlugin(host="::1", xmlrpc_port=0)
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while plugin._xmlrpc_server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._xmlrpc_server is not None
        port = plugin._xmlrpc_server.server_address[1]
        with xmlrpc.client.ServerProxy(f"http://[::1]:{port}") as proxy:
            response: Any = proxy.ping()
            assert response["pong"] is True
    finally:
        plugin._running = False
        thread.join(timeout=3)
        if plugin._xmlrpc_server is not None:
            plugin._xmlrpc_server.server_close()
        assert not thread.is_alive()


@pytest.mark.asyncio
async def test_socket_reconnects_after_server_idle_deadline(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real client reconnects before its next request after an idle close."""
    monkeypatch.setattr(server_mod, "REQUEST_READ_TIMEOUT_SECONDS", 0.1)
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", port=0)
    plugin._running = True
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": "done"}
    )
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    bridge = SocketBridge(host="127.0.0.1", port=port)
    try:
        await bridge.connect()
        await asyncio.sleep(0.25)
        result = await bridge.execute_python("_result_ = 'done'")
        assert result.success is True
        assert result.result == "done"
        plugin._execute_via_queue.assert_called_once()
    finally:
        await bridge.disconnect()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_socket_rejects_oversized_frame_before_execution(
    server_mod: Any,
) -> None:
    """An oversized socket frame closes the connection without executing code."""
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", port=0)
    plugin._running = True
    plugin._execute_via_queue = MagicMock()
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"x" * (server_mod.MAX_BRIDGE_REQUEST_BYTES + 1) + b"\n")
        await writer.drain()
        assert await asyncio.wait_for(reader.read(), timeout=3) == b""
        plugin._execute_via_queue.assert_not_called()
    finally:
        writer.close()
        await writer.wait_closed()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_socket_limits_simultaneous_clients(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connections beyond the cap are closed while an existing client remains."""
    monkeypatch.setattr(server_mod, "MAX_SOCKET_CLIENTS", 1)
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", port=0)
    plugin._running = True
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    first_reader, first_writer = await asyncio.open_connection("127.0.0.1", port)
    second_writer = None
    try:
        first_writer.write(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
        await first_writer.drain()
        assert await asyncio.wait_for(first_reader.readline(), timeout=3)
        second_reader, second_writer = await asyncio.open_connection("127.0.0.1", port)
        assert await asyncio.wait_for(second_reader.read(), timeout=3) == b""
    finally:
        first_writer.close()
        await first_writer.wait_closed()
        if second_writer is not None:
            second_writer.close()
            await second_writer.wait_closed()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


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
