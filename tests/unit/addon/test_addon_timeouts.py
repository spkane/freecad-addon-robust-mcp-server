"""Regression tests for workbench execution timeout handling."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import http.client
import importlib
import importlib.util
import json
import socket
import sys
import threading
import time
import types
import xmlrpc.client
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, call

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from freecad_mcp.bridge.socket import SocketBridge
from freecad_mcp.bridge.xmlrpc import XmlRpcBridge

if TYPE_CHECKING:
    from collections.abc import Iterator

ADDON_DIR = Path(__file__).parent.parent.parent.parent / "freecad" / "RobustMCPBridge"


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["socket", "xmlrpc"])
@pytest.mark.parametrize("algorithm", ["ed25519", "p256"])
async def test_real_signatures_across_client_and_listener(
    server_mod: Any, transport: str, algorithm: str
) -> None:
    """Both real transports authorize a paired signature and enforce revocation."""
    auth_module = importlib.import_module("freecad_mcp_bridge.authentication")
    if algorithm == "ed25519":
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        signer = private_key.sign
        wrong_signer = Ed25519PrivateKey.generate().sign
        make_verifier = auth_module.create_ed25519_verifier
    else:
        p256_key = ec.generate_private_key(ec.SECP256R1())
        public_key = p256_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        signer = partial(p256_key.sign, signature_algorithm=ec.ECDSA(hashes.SHA256()))
        wrong_key = ec.generate_private_key(ec.SECP256R1())
        wrong_signer = partial(
            wrong_key.sign, signature_algorithm=ec.ECDSA(hashes.SHA256())
        )
        make_verifier = auth_module.create_p256_verifier
    client_id = hashlib.sha256(public_key).hexdigest()
    approved = {client_id: public_key}

    authenticator = auth_module.BridgeAuthenticator(make_verifier(approved.get))
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, xmlrpc_port=0, authenticator=authenticator
    )
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": "done"}
    )
    plugin._running = True
    thread = None
    bridge: SocketBridge | XmlRpcBridge | None = None
    try:
        if transport == "socket":
            await plugin._start_socket_server()
            port = plugin._socket_server.sockets[0].getsockname()[1]
            bridge = SocketBridge(
                host="127.0.0.1",
                port=port,
                client_id=client_id,
                signer=signer,
            )
        else:
            thread = threading.Thread(target=plugin._run_xmlrpc_server)
            thread.start()
            deadline = time.monotonic() + 5
            while plugin._xmlrpc_server is None and time.monotonic() < deadline:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
            assert plugin._xmlrpc_server is not None
            port = plugin._xmlrpc_server.server_address[1]
            bridge = XmlRpcBridge(
                host="127.0.0.1",
                port=port,
                client_id=client_id,
                signer=signer,
            )

        assert bridge is not None
        impostor = type(bridge)(
            host="127.0.0.1",
            port=port,
            client_id=client_id,
            signer=wrong_signer,
        )
        try:
            with pytest.raises(ConnectionError):
                await impostor.connect()
            plugin._execute_via_queue.assert_not_called()
        finally:
            await impostor.disconnect()

        await bridge.connect()
        result = await bridge.execute_python("pass")
        assert result.success and result.result == "done"
        prior_calls = plugin._execute_via_queue.call_count
        del approved[client_id]
        result = await bridge.execute_python("revoked()")
        assert not result.success
        assert plugin._execute_via_queue.call_count == prior_calls
    finally:
        if bridge is not None:
            await bridge.disconnect()
        plugin._running = False
        if plugin._socket_server is not None:
            plugin._socket_server.close()
            await plugin._socket_server.wait_closed()
        if thread is not None:
            await asyncio.to_thread(thread.join, 3)
            if plugin._xmlrpc_server is not None:
                plugin._xmlrpc_server.server_close()
            assert not thread.is_alive()


def test_socket_shutdown_releases_active_client_slots(server_mod: Any) -> None:
    """Stopping a listener with an idle client must release its client slot."""
    plugin = server_mod.FreecadMCPPlugin(port=0, enable_xmlrpc=False)
    plugin._running = True
    plugin._socket_thread = threading.Thread(target=plugin._run_socket_server)
    plugin._socket_thread.start()
    client = None
    try:
        deadline = time.monotonic() + 5
        while plugin._socket_server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._socket_server is not None
        port = plugin._socket_server.sockets[0].getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        while plugin._socket_client_count == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._socket_client_count == 1
    finally:
        plugin.stop()
        if client is not None:
            client.close()
    assert plugin._socket_client_count == 0


def test_start_refuses_missing_authentication_before_opening_listeners(
    server_mod: Any,
) -> None:
    """A missing verifier must not start the queue or either bridge listener."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._start_queue_processor = MagicMock()
    with pytest.raises(RuntimeError, match="authentication provider is required"):
        plugin.start()
    plugin._start_queue_processor.assert_not_called()
    assert not plugin.is_running
    assert plugin._socket_thread is None
    assert plugin._xmlrpc_thread is None


def test_gui_status_warns_that_bridge_accepts_python(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The running status warns even when MCP code tools are not advertised."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(server_mod, "FreeCAD", MagicMock(GuiUp=True), raising=False)
    status_module = types.ModuleType("Qt.status_widget")
    status_module.update_status_running = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "Qt.status_widget", status_module)
    plugin = server_mod.FreecadMCPPlugin()
    plugin._set_status_bar = MagicMock()
    plugin._update_status_bar()
    assert "Python execution enabled" in plugin._set_status_bar.call_args.args[0]
    status_module.update_status_running.assert_called_once_with(9875, 9876, 0)


@pytest.mark.parametrize("freecad_available", [False, True])
def test_headless_start_does_not_create_gui_status_timer(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, freecad_available: bool
) -> None:
    """Headless startup must not create Qt timers or query GUI bindings."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", freecad_available)
    monkeypatch.setattr(server_mod, "FreeCAD", MagicMock(GuiUp=False), raising=False)
    qt_loader = MagicMock()
    monkeypatch.setattr(server_mod, "_get_qt_core", qt_loader)
    plugin = server_mod.FreecadMCPPlugin()
    plugin._start_status_updates()
    qt_loader.assert_not_called()
    assert plugin._status_timer is None


def test_permanent_status_widget_warns_that_bridge_accepts_python(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The permanent widget describes what an authorized client can do."""
    del server_mod
    path = ADDON_DIR / "Qt" / "status_widget.py"
    spec = importlib.util.spec_from_file_location("test_bridge_status_widget", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_check_main_thread", lambda _operation: True)
    widget = module.MCPStatusWidget()
    widget._widget = MagicMock()
    widget.set_running(9875, 9876, 1)
    assert "Python execution enabled" in widget._widget.setText.call_args.args[0]
    assert "authorized clients" in widget._widget.setToolTip.call_args.args[0]


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


def test_execution_bounds_stdout_and_stderr_without_losing_result(
    server_mod: Any,
) -> None:
    """Large multibyte output is bounded independently and visibly truncated."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync(
        "import sys\nprint('é' * 600000)\nprint('x' * 1100000, file=sys.stderr)\n_result_ = 7"
    )
    assert result["success"] is True
    assert result["result"] == 7
    for name in ("stdout", "stderr"):
        assert len(result[name].encode("utf-8")) <= server_mod.MAX_CAPTURED_OUTPUT_BYTES
        assert result[name].endswith(server_mod.OUTPUT_TRUNCATION_MARKER)


def test_bounded_capture_rejects_seeking(server_mod: Any) -> None:
    """Code cannot grow the capture by seeking beyond its bounded output."""
    capture = server_mod._BoundedCapture(limit=32)
    with pytest.raises(OSError):
        capture.seek(10**12)
    assert capture.write("a" * 1000) == 1000
    assert len(capture.getvalue().encode("utf-8")) <= 32


def test_exception_diagnostics_are_bounded(server_mod: Any) -> None:
    """Large exception messages and tracebacks have bounded encoded output."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync("raise ValueError('é' * 600000)")
    assert result["success"] is False
    assert result["error_type"] == "ValueError"
    for name in ("error_message", "error_traceback"):
        assert len(result[name].encode("utf-8")) <= server_mod.MAX_CAPTURED_OUTPUT_BYTES
        assert result[name].endswith(server_mod.OUTPUT_TRUNCATION_MARKER)


def test_unrenderable_exception_still_returns_failure(server_mod: Any) -> None:
    """A broken exception string must not leave the request unanswered."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync(
        "class BadError(Exception):\n"
        "    def __str__(self):\n"
        "        raise RuntimeError('broken')\n"
        "raise BadError()"
    )
    assert result["success"] is False
    assert result["error_type"] == "BadError"
    assert result["error_message"] == "Exception message could not be rendered"
    assert "BadError" in result["error_traceback"]


def test_xmlrpc_rejects_unsafe_framing_and_xml(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real listener rejects oversized, compressed and DTD requests."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", False)
    plugin = server_mod.FreecadMCPPlugin(host="127.0.0.1", xmlrpc_port=0)
    plugin._authenticator = MagicMock()
    plugin._authenticator.verify_xmlrpc_headers.return_value = True
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


def test_xmlrpc_listener_authenticates_before_dispatch(server_mod: Any) -> None:
    """The actual listener rejects missing, altered, and replayed request proofs."""
    auth_module = importlib.import_module("freecad_mcp_bridge.authentication")
    key = b"unit-test-only-key"

    def verify(client: str, message: bytes, proof: bytes) -> bool:
        return client == "paired" and hmac.compare_digest(
            hmac.digest(key, message, "sha256"), proof
        )

    auth = auth_module.BridgeAuthenticator(verify)
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", xmlrpc_port=0, authenticator=auth
    )
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while plugin._xmlrpc_server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert plugin._xmlrpc_server is not None
        port = plugin._xmlrpc_server.server_address[1]

        def request(
            method: str, path: str, body: bytes = b"", **headers: str
        ) -> tuple[int, bytes]:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()

        body = xmlrpc.client.dumps((), methodname="ping").encode()
        assert request("POST", "/RPC2", body)[0] == 401
        status, challenge_bytes = request("GET", "/challenge")
        assert status == 200
        challenge = challenge_bytes.decode("ascii")
        message = auth_module.request_proof_message("paired", challenge, "xmlrpc", body)
        proof = base64.b64encode(hmac.digest(key, message, "sha256")).decode()
        headers = {
            "X-FreeCAD-Client": "paired",
            "X-FreeCAD-Challenge": challenge,
            "X-FreeCAD-Proof": proof,
        }
        assert request("POST", "/RPC2", body, **headers)[0] == 200
        assert request("POST", "/RPC2", body, **headers)[0] == 401
        _, challenge_bytes = request("GET", "/challenge")
        challenge = challenge_bytes.decode("ascii")
        message = auth_module.request_proof_message("paired", challenge, "xmlrpc", body)
        headers["X-FreeCAD-Challenge"] = challenge
        headers["X-FreeCAD-Proof"] = base64.b64encode(
            hmac.digest(key, message, "sha256")
        ).decode()
        assert request("POST", "/RPC2", body + b" ", **headers)[0] == 401
    finally:
        plugin._running = False
        thread.join(timeout=3)
        if plugin._xmlrpc_server is not None:
            plugin._xmlrpc_server.server_close()
        assert not thread.is_alive()


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
async def test_xmlrpc_client_signs_requests_for_listener(
    server_mod: Any, host: str
) -> None:
    """The XML-RPC client and real listener agree on request proofs."""
    if host == "::1":
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
                probe.bind((host, 0))
        except OSError:
            pytest.skip("IPv6 loopback is unavailable")
    auth_module = importlib.import_module("freecad_mcp_bridge.authentication")
    key = b"unit-test-only-key"

    def sign(message: bytes) -> bytes:
        return hmac.digest(key, message, "sha256")

    def verify(client: str, message: bytes, proof: bytes) -> bool:
        return client == "paired" and hmac.compare_digest(sign(message), proof)

    plugin = server_mod.FreecadMCPPlugin(
        host=host,
        xmlrpc_port=0,
        authenticator=auth_module.BridgeAuthenticator(verify),
    )
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": "done"}
    )
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    bridge = None
    try:
        deadline = time.monotonic() + 5
        while plugin._xmlrpc_server is None and time.monotonic() < deadline:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
        assert plugin._xmlrpc_server is not None
        port = plugin._xmlrpc_server.server_address[1]
        bridge = XmlRpcBridge(host=host, port=port, client_id="paired", signer=sign)
        await bridge.connect()
        result = await bridge.execute_python("pass")
        assert result.success is True
        assert result.result == "done"
        plugin._execute_via_queue.assert_called_with("pass", 30000)
    finally:
        if bridge is not None:
            await bridge.disconnect()
        plugin._running = False
        await asyncio.to_thread(thread.join, 3)
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
    plugin._authenticator = MagicMock()
    plugin._authenticator.verify_xmlrpc_headers.return_value = True
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
    auth_module = importlib.import_module("freecad_mcp_bridge.authentication")
    key = b"unit-test-only-key"

    def sign(message: bytes) -> bytes:
        return hmac.digest(key, message, "sha256")

    def verify(client: str, message: bytes, proof: bytes) -> bool:
        return client == "paired" and hmac.compare_digest(sign(message), proof)

    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=auth_module.BridgeAuthenticator(verify)
    )
    plugin._running = True
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": "done"}
    )
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    bridge = SocketBridge(host="127.0.0.1", port=port, client_id="paired", signer=sign)
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
async def test_socket_listener_requires_fresh_request_proof(server_mod: Any) -> None:
    """The live socket rejects legacy, modified, and replayed request frames."""
    auth_module = importlib.import_module("freecad_mcp_bridge.authentication")
    key = b"unit-test-only-key"

    def verify(client: str, message: bytes, proof: bytes) -> bool:
        return client == "paired" and hmac.compare_digest(
            hmac.digest(key, message, "sha256"), proof
        )

    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=auth_module.BridgeAuthenticator(verify)
    )
    plugin._running = True
    plugin._execute_via_queue = MagicMock(return_value={"success": True})
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)

    async def exchange(frame: dict[str, Any]) -> Any:
        writer.write(json.dumps(frame).encode() + b"\n")
        await writer.drain()
        return json.loads(await asyncio.wait_for(reader.readline(), timeout=3))

    try:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "execute",
            "params": {"code": "pass"},
        }
        assert "error" in await exchange(request)
        plugin._execute_via_queue.assert_not_called()
        challenge = (await exchange({"type": "challenge"}))["challenge"]
        body = json.dumps(request).encode()
        message = auth_module.request_proof_message("paired", challenge, "socket", body)
        envelope = {
            "client": "paired",
            "challenge": challenge,
            "body": base64.b64encode(body).decode(),
            "proof": base64.b64encode(hmac.digest(key, message, "sha256")).decode(),
        }
        assert (await exchange(envelope))["result"]["success"] is True
        assert "error" in await exchange(envelope)
        challenge = (await exchange({"type": "challenge"}))["challenge"]
        message = auth_module.request_proof_message("paired", challenge, "socket", body)
        envelope["challenge"] = challenge
        envelope["proof"] = base64.b64encode(
            hmac.digest(key, message, "sha256")
        ).decode()
        envelope["body"] = base64.b64encode(body + b" ").decode()
        assert "error" in await exchange(envelope)
        envelope["body"] = base64.b64encode(body).decode()
        assert "error" in await exchange(envelope)
        plugin._execute_via_queue.assert_called_once()
    finally:
        writer.close()
        await writer.wait_closed()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_socket_client_rejects_legacy_server() -> None:
    """An unauthenticated peer cannot cause the client to send code."""
    received: list[bytes] = []

    async def legacy(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        received.append(await reader.readline())
        writer.write(b'{"jsonrpc":"2.0","result":"pong"}\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(legacy, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    bridge = SocketBridge(
        host="127.0.0.1", port=port, client_id="paired", signer=lambda _: b"proof"
    )
    try:
        with pytest.raises(ConnectionError, match="valid challenge"):
            await bridge.connect()
        assert received == [b'{"type":"challenge"}\n']
    finally:
        await bridge.disconnect()
        server.close()
        await server.wait_closed()


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
