"""Regression tests for workbench execution timeout handling."""

from __future__ import annotations

import asyncio
import base64
import contextlib
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
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, call

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
@pytest.mark.parametrize("blocked", ["socket", "xmlrpc", "both", "neither"])
async def test_listener_port_conflicts_preserve_authenticated_transport(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, blocked: str
) -> None:
    """An occupied port must not disable or bypass authentication on the other."""
    console = MagicMock()
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(
        server_mod, "FreeCAD", MagicMock(Console=console), raising=False
    )
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "test" else None)
    )
    blockers: dict[str, socket.socket] = {}
    ports: dict[str, int] = {}
    for name in ("socket", "xmlrpc"):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        ports[name] = listener.getsockname()[1]
        if blocked in (name, "both"):
            blockers[name] = listener
        else:
            listener.close()
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1",
        port=ports["socket"],
        xmlrpc_port=ports["xmlrpc"],
        authenticator=authenticator,
    )
    plugin._start_queue_processor = MagicMock()
    plugin._start_status_updates = MagicMock()
    plugin._stop_status_updates = MagicMock()
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": "ok"}
    )
    try:
        if blocked == "both":
            with pytest.raises(RuntimeError, match="could not start") as error:
                await asyncio.to_thread(plugin.start)
            assert "XML-RPC" in str(error.value) and "JSON-RPC" in str(error.value)
            assert "preferences" in str(error.value)
            assert not plugin.is_running
        else:
            await asyncio.to_thread(plugin.start)
            status = plugin.get_status()
            assert plugin.is_running
            for name in ("socket", "xmlrpc"):
                assert status["listeners"][name] == (
                    "failed" if blocked == name else "running"
                )
                if blocked == name:
                    assert "in use" in status["listener_errors"][name]
                    assert "preferences" in status["listener_errors"][name]
                    assert status["listener_errors"][name] in "".join(
                        args.args[0] for args in console.PrintError.call_args_list
                    )
                    continue
                if sys.platform == "win32":
                    with socket.socket() as competing:
                        competing.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        with pytest.raises(OSError):
                            competing.bind(("127.0.0.1", ports[name]))
                bridge_class = SocketBridge if name == "socket" else XmlRpcBridge

                def signer(message: bytes) -> bytes:
                    return hmac.digest(secret, message, "sha256")

                bridge = bridge_class(
                    host="127.0.0.1", port=ports[name], client_id="test", signer=signer
                )
                impostor = bridge_class(
                    host="127.0.0.1",
                    port=ports[name],
                    client_id="test",
                    signer=lambda message: hmac.digest(b"b" * 32, message, "sha256"),
                )
                try:
                    with pytest.raises(ConnectionError):
                        await impostor.connect()
                    await bridge.connect()
                    result = await bridge.execute_python("pass")
                    assert result.success and result.result == "ok"
                finally:
                    await impostor.disconnect()
                    await bridge.disconnect()
    finally:
        await asyncio.to_thread(plugin.stop)
        for listener in blockers.values():
            listener.close()
    assert not plugin.is_running
    for name in ("socket", "xmlrpc"):
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", ports[name])) != 0


def test_partial_start_can_stop_and_restart_after_port_is_freed(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping a degraded bridge releases its listener and allows recovery."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", False)
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]
        plugin = server_mod.FreecadMCPPlugin(
            host="127.0.0.1", port=port, xmlrpc_port=0, authenticator=MagicMock()
        )
        plugin._start_queue_processor = MagicMock()
        plugin._start_status_updates = MagicMock()
        plugin._stop_status_updates = MagicMock()
        try:
            plugin.start()
            assert plugin.get_status()["listeners"] == {
                "socket": "failed",
                "xmlrpc": "running",
            }
            plugin.stop()
        finally:
            plugin.stop()
    try:
        plugin.start()
        assert plugin.get_status()["listeners"] == {
            "socket": "running",
            "xmlrpc": "running",
        }
    finally:
        plugin.stop()


def test_listener_startup_timeout_names_transport_and_cleans_up(
    server_mod: Any,
) -> None:
    """A stalled listener produces actionable transport-specific guidance."""
    plugin = server_mod.FreecadMCPPlugin(port=9876, xmlrpc_port=9875)
    plugin._listener_ready["socket"] = MagicMock()
    plugin._listener_ready["socket"].wait.return_value = False
    plugin._listener_ready["xmlrpc"] = MagicMock()
    plugin._listener_ready["xmlrpc"].wait.return_value = True
    plugin.stop = MagicMock()
    with pytest.raises(RuntimeError, match=r"JSON-RPC.*9876.*preferences"):
        plugin._await_listeners()
    plugin.stop.assert_called_once_with()


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
    socket_thread = plugin._socket_thread
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
    assert not socket_thread.is_alive()


@pytest.mark.asyncio
async def test_idle_socket_timeout_is_not_logged_as_error(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An idle connection closes normally without an error in FreeCAD."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    reader = MagicMock()
    reader.readline = AsyncMock(side_effect=TimeoutError())
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    console = MagicMock()
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(
        server_mod, "FreeCAD", MagicMock(Console=console), raising=False
    )
    await plugin._handle_socket_client(reader, writer)
    console.PrintError.assert_not_called()
    writer.close.assert_called_once()


def test_start_refuses_missing_authentication_before_opening_listeners(
    server_mod: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing verifier must not start the queue or either bridge listener."""
    monkeypatch.delenv("FREECAD_BRIDGE_CLIENT_ID", raising=False)
    monkeypatch.delenv("FREECAD_BRIDGE_SECRET", raising=False)
    store = importlib.import_module("freecad_mcp_bridge.credential_store")
    monkeypatch.setattr(
        store, "read_credential", MagicMock(side_effect=FileNotFoundError)
    )
    plugin = server_mod.FreecadMCPPlugin()
    plugin._start_queue_processor = MagicMock()
    with pytest.raises(RuntimeError, match="freecad-mcp --pair-bridge"):
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
    monkeypatch.setitem(
        sys.modules, "freecad.RobustMCPBridge.Qt.status_widget", status_module
    )
    plugin = server_mod.FreecadMCPPlugin()
    plugin._listener_states = {"xmlrpc": "running", "socket": "running"}
    plugin._set_status_bar = MagicMock()
    plugin._update_status_bar()
    assert (
        "client code has your permissions" in plugin._set_status_bar.call_args.args[0]
    )
    status_module.update_status_running.assert_called_once_with(
        9875,
        9876,
        0,
        xmlrpc_running=True,
        socket_running=True,
        errors="",
        review_bypassed=False,
        macro_review_bypassed=False,
    )
    status_module.update_status_running.reset_mock()
    plugin._review_controller = SimpleNamespace(
        _policy=SimpleNamespace(requires_review=lambda _action: False)
    )
    plugin._update_status_bar()
    assert (
        status_module.update_status_running.call_args.kwargs["review_bypassed"] is True
    )
    plugin._listener_states["xmlrpc"] = "disabled"
    plugin._update_status_bar()
    status_module.update_status_running.assert_called_with(
        9875,
        9876,
        0,
        xmlrpc_running=False,
        socket_running=True,
        errors="",
        review_bypassed=True,
        macro_review_bypassed=True,
    )


def test_standalone_warning_is_permanent_and_removed_on_stop(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Standalone GUI startup needs a non-modal warning without the workbench."""
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(server_mod, "FreeCAD", MagicMock(GuiUp=True), raising=False)
    monkeypatch.setattr(server_mod, "__package__", "standalone_bridge")
    monkeypatch.delitem(
        sys.modules, "freecad.RobustMCPBridge.Qt.status_widget", raising=False
    )
    status_bar, label = MagicMock(), MagicMock()
    gui = SimpleNamespace(
        getMainWindow=lambda: SimpleNamespace(statusBar=lambda: status_bar)
    )
    monkeypatch.setattr(server_mod, "FreeCADGui", gui, raising=False)
    qt = SimpleNamespace(QLabel=MagicMock(return_value=label))
    monkeypatch.setattr(server_mod, "load_qt_core_widgets", lambda: (None, qt))
    plugin = server_mod.FreecadMCPPlugin()
    plugin._listener_states = {"xmlrpc": "running", "socket": "running"}

    plugin._update_status_widget()
    plugin._update_status_widget()
    status_bar.addPermanentWidget.assert_called_once_with(label)
    assert "full user permissions" in qt.QLabel.call_args.args[0]
    assert "files and network" in label.setToolTip.call_args.args[0]

    plugin._stop_status_updates()
    label.setParent.assert_called_once_with(None)
    label.deleteLater.assert_called_once_with()
    assert plugin._standalone_warning is None


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


def test_status_timer_handles_freecad_before_guiup_exists(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Early console initialization must not read a missing GuiUp attribute."""
    freecad = types.ModuleType("FreeCAD")
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(server_mod, "FreeCAD", freecad, raising=False)
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
    namespace = types.ModuleType("freecad")
    namespace.__path__ = [str(ADDON_DIR.parent)]
    package = types.ModuleType("freecad.RobustMCPBridge")
    package.__path__ = [str(ADDON_DIR)]
    monkeypatch.setitem(sys.modules, "freecad", namespace)
    monkeypatch.setitem(sys.modules, "freecad.RobustMCPBridge", package)
    path = ADDON_DIR / "Qt" / "status_widget.py"
    spec = importlib.util.spec_from_file_location(
        "freecad.RobustMCPBridge.Qt.status_widget", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_check_main_thread", lambda _operation: True)
    widget = module.MCPStatusWidget()
    widget._widget = MagicMock()
    widget.set_running(9875, 9876, 1)
    assert "Python: full user permissions" in widget._widget.setText.call_args.args[0]
    assert "authorized clients" in widget._widget.setToolTip.call_args.args[0]
    assert "full permissions" in widget._widget.setToolTip.call_args.args[0]
    assert "files and network" in widget._widget.setToolTip.call_args.args[0]
    widget.set_running(
        9875,
        9876,
        1,
        xmlrpc_running=True,
        socket_running=False,
        errors="JSON-RPC port 9876 is in use; check preferences",
    )
    assert "partial" in widget._widget.setText.call_args.args[0]
    tooltip = widget._widget.setToolTip.call_args.args[0]
    assert "XML-RPC: listening" in tooltip and "JSON-RPC: unavailable" in tooltip
    assert "check preferences" in tooltip and "authorized clients" in tooltip
    assert module.__version__ in tooltip
    policy = MagicMock()
    policy.requires_review.return_value = False
    plugin = MagicMock(
        is_running=True, xmlrpc_port=9875, socket_port=9876, request_count=1
    )
    plugin._review_controller = types.SimpleNamespace(_policy=policy)
    plugin.get_status.return_value = {
        "listeners": {"xmlrpc": "running", "socket": "running"},
        "listener_errors": {},
    }
    monkeypatch.setitem(
        sys.modules,
        "freecad.RobustMCPBridge.commands",
        types.SimpleNamespace(_mcp_plugin=plugin),
    )
    monkeypatch.setitem(
        sys.modules,
        "freecad.RobustMCPBridge.preferences",
        types.SimpleNamespace(get_status_bar_enabled=lambda: True),
    )
    synced = MagicMock()
    synced.install.return_value = True
    monkeypatch.setattr(module, "get_status_widget", lambda: synced)
    module.sync_status_with_bridge()
    assert synced.set_running.call_args.kwargs["review_bypassed"] is True
    assert synced.set_running.call_args.kwargs["macro_review_bypassed"] is True
    for method, args in (
        (widget.set_stopped, ()),
        (widget.set_starting, ()),
        (widget.set_error, ("Example error",)),
    ):
        method(*args)
        assert module.__version__ in widget._widget.setToolTip.call_args.args[0]
    assert "Example error" in widget._widget.setToolTip.call_args.args[0]


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


@pytest.mark.parametrize("fail", [False, True])
def test_xmlrpc_screenshot_uses_and_cleans_user_directory(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail: bool
) -> None:
    """Legacy XML-RPC screenshots remove their private directory on all exits."""
    import os

    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda path: str(tmp_path) if path == "~" else original_expanduser(path),
    )
    created = []

    class View3DInventor:
        def viewIsometric(self) -> None:
            pass

        def saveImage(self, path: str, *_args: object) -> None:
            image = Path(path)
            assert image.parent.parent == tmp_path
            created.append(image.parent)
            image.write_bytes(b"png")
            if fail:
                raise RuntimeError("capture failed")

    view = View3DInventor()
    environment = {
        "FreeCAD": SimpleNamespace(GuiUp=True, ActiveDocument=object()),
        "FreeCADGui": SimpleNamespace(ActiveDocument=SimpleNamespace(ActiveView=view)),
    }
    plugin = server_mod.FreecadMCPPlugin()

    def execute(code: str, _timeout: int) -> dict[str, Any]:
        exec(code, environment)  # noqa: S102
        return {"success": True, "result": environment["_result_"]}

    plugin._execute_via_queue = execute
    if fail:
        with pytest.raises(RuntimeError, match="capture failed"):
            plugin._xmlrpc_get_view()
    else:
        assert base64.b64decode(plugin._xmlrpc_get_view()["data"]) == b"png"
    assert created and not created[0].exists()


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


def test_bounded_capture_stops_after_partial_unicode_character(server_mod: Any) -> None:
    """Later writes cannot fill space left by a truncated multibyte character."""
    capture = server_mod._BoundedCapture(limit=32)
    capture.write("a" * 31)
    capture.write("é")
    assert capture.truncated
    capture.write("z")
    assert "z" not in capture.getvalue()
    assert capture.getvalue().endswith(server_mod.OUTPUT_TRUNCATION_MARKER)


def test_captured_output_escapes_xml_incompatible_characters(server_mod: Any) -> None:
    """Control and noncharacter output remains readable on both transports."""
    capture = server_mod._BoundedCapture(limit=100)
    original = "a\x00\x0b\uffff\t\nb"
    assert capture.write(original) == len(original)
    assert capture.getvalue() == r"a\x00\x0b\uffff" + "\t\nb"


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


@pytest.mark.parametrize(
    "exception", ["SystemExit", "KeyboardInterrupt", "GeneratorExit"]
)
def test_execution_contains_base_exceptions(server_mod: Any, exception: str) -> None:
    """Submitted code must not terminate the FreeCAD execution worker."""
    plugin = server_mod.FreecadMCPPlugin()
    failure = plugin._execute_code_sync(f"raise {exception}('test')")
    assert not failure["success"]
    assert failure["error_type"] == exception
    assert plugin._execute_code_sync("_result_ = 42")["result"] == 42


def test_exception_rendering_contains_base_exception(server_mod: Any) -> None:
    """An exception's broken string method cannot terminate the worker."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync(
        "class BadError(Exception):\n"
        "    def __str__(self):\n"
        "        raise SystemExit()\n"
        "raise BadError()"
    )
    assert not result["success"]
    assert result["error_type"] == "BadError"
    assert result["error_message"] == "Exception message could not be rendered"


@pytest.mark.parametrize(
    "code",
    [
        "_result_ = 'x' * 1000001",
        "_result_ = [None] * 100000",
        "_result_ = []; _result_.append(_result_)",
        "_result_ = {'bad': float('nan')}",
        "_result_ = {1: 'non-string key'}",
        "_result_ = 2 ** 50",
        "_result_ = object()",
    ],
)
def test_execution_rejects_unbounded_or_nonportable_result(
    server_mod: Any, code: str
) -> None:
    """Results are rejected before serialization, with execution ambiguity explicit."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync(code)
    assert result["success"] is False
    assert result["error_type"] == "ResultValidationError"
    assert "FreeCAD changes may have occurred" in result["error_message"]


def test_execution_accepts_portable_nested_result(server_mod: Any) -> None:
    """Normal nested CAD data is preserved without truncation."""
    plugin = server_mod.FreecadMCPPlugin()
    result = plugin._execute_code_sync(
        "_result_ = {'items': [1, 2.5, 'é', None, True]}"
    )
    assert result["success"] is True
    assert result["result"] == {"items": [1, 2.5, "é", None, True]}


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
        for method, path in (("GET", "/challenge"), ("POST", "/RPC2")):
            for host in ("example.com", "localhost.example.com", "localhost@evil.test"):
                assert request(method, path, body, Host=host)[0] == 403
            assert request(method, path, body, Origin="http://localhost:3000")[0] == 403
            assert request(method, path, body, Origin="null")[0] == 403
        assert request("GET", "/challenge", Host="localhost:54321")[0] == 200
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.putrequest("GET", "/challenge", skip_host=True)
            connection.putheader("Host", "localhost")
            connection.putheader("Host", "127.0.0.1")
            connection.endheaders()
            response = connection.getresponse()
            assert response.status == 403
            response.read()
        finally:
            connection.close()
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
            except (ConnectionResetError, ConnectionAbortedError):
                pass
        assert thread.is_alive()
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            assert response.status == 200
            response.read()
        finally:
            connection.close()
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


@pytest.mark.asyncio
async def test_socket_disconnect_does_not_cancel_inflight_handler(
    server_mod: Any,
) -> None:
    """Document why a future approval path needs explicit disconnect handling.

    This probes the socket loop only: authentication and code execution are
    replaced by a blocked coroutine so no FreeCAD mutation can occur.
    """
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    entered = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()
    handler_finished = asyncio.Event()
    readers: list[Any] = []

    async def blocked_handler(
        _envelope: Any, _session: Any, _owners: Any
    ) -> dict[str, Any]:
        entered.set()
        await release.wait()
        completed.set()
        return {"result": "probe"}

    plugin._process_socket_envelope = blocked_handler

    async def handle(reader: Any, writer: Any) -> None:
        readers.append(reader)
        try:
            await plugin._handle_socket_client(reader, writer)
        finally:
            handler_finished.set()

    listener = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = listener.sockets[0].getsockname()[1]
    writer = None
    try:
        _reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"{}\n")
        await writer.drain()
        await asyncio.wait_for(entered.wait(), timeout=2)
        writer.close()
        await writer.wait_closed()
        async with asyncio.timeout(2):
            while not readers[0].at_eof():  # noqa: ASYNC110 - no EOF event API
                await asyncio.sleep(0.01)
        assert not completed.is_set()
        release.set()
        await asyncio.wait_for(completed.wait(), timeout=2)
    finally:
        release.set()
        plugin._running = False
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        listener.close()
        await listener.wait_closed()
        if writer is not None:
            await asyncio.wait_for(handler_finished.wait(), timeout=2)


@pytest.mark.asyncio
async def test_socket_review_requires_authenticated_owner_and_explicit_commit(
    server_mod: Any,
) -> None:
    """A verified socket identity cannot commit another client's review."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    secrets = {"alice": b"a" * 32, "bob": b"b" * 32}
    authenticator = auth.BridgeAuthenticator(auth.create_hmac_verifier(secrets.get))
    plugin = server_mod.FreecadMCPPlugin(authenticator=authenticator)
    coordinator = approval.ReviewCoordinator(2)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 2)

    async def call(
        client: str, method: str, params: dict, *, wrong: bool = False
    ) -> dict:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode()
        challenge = authenticator.issue_challenge()
        message = auth.request_proof_message(client, challenge, "socket", body)
        secret = b"z" * 32 if wrong else secrets[client]
        return await plugin._process_socket_envelope(
            {
                "client": client,
                "challenge": challenge,
                "body": base64.b64encode(body).decode(),
                "proof": base64.b64encode(
                    hmac.digest(secret, message, "sha256")
                ).decode(),
            },
            "test-session",
            set(),
        )

    begin = await call("alice", "review_begin", {"code": "print(1)"})
    review_id = begin["result"]["review_id"]
    request = coordinator.next_review()
    assert request is not None and request.decide(approved=True)
    assert coordinator.next_execution() is None
    assert (
        await call("alice", "review_commit", {"review_id": review_id}, wrong=True)
    ) == {"error": "Bridge authentication required"}
    assert not (await call("bob", "review_commit", {"review_id": review_id}))["result"][
        "scheduled"
    ]
    assert (await call("alice", "review_commit", {"review_id": review_id}))["result"][
        "scheduled"
    ]
    assert not (await call("alice", "review_commit", {"review_id": review_id}))[
        "result"
    ]["scheduled"]
    claimed = coordinator.next_execution()
    assert claimed == (review_id, request.payload)
    assert claimed[1].content == b"print(1)"
    assert coordinator.next_execution() is None
    coordinator.close()


@pytest.mark.asyncio
async def test_socket_review_disabled_without_local_broker(server_mod: Any) -> None:
    """An authenticated request cannot silently downgrade to raw execution."""
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_via_queue = MagicMock()
    response = await plugin._process_jsonrpc_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "review_begin",
            "params": {"code": "pass"},
        },
        "alice",
    )
    assert response["error"]["message"] == "Local review is unavailable"
    plugin._execute_via_queue.assert_not_called()


@pytest.mark.asyncio
async def test_undisplayable_review_code_reports_reason_without_echoing_content(
    server_mod: Any,
) -> None:
    """Reject misleading review text without returning its contents."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._execute_via_queue = MagicMock()
    coordinator = approval.ReviewCoordinator(1)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    code = "sensitive_example\r\npass"
    response = await plugin._process_jsonrpc_request(
        {"jsonrpc": "2.0", "id": 1, "method": "review_begin", "params": {"code": code}},
        "alice",
    )
    assert response["error"]["code"] == -32602
    assert "cannot be displayed" in response["error"]["message"]
    assert "sensitive_example" not in str(response)
    assert coordinator.next_review() is None
    plugin._execute_via_queue.assert_not_called()


@pytest.mark.asyncio
async def test_socket_review_disconnect_cancels_session_approvals(
    server_mod: Any,
) -> None:
    """Disconnect cancels pending and committed tickets for that connection."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=authenticator
    )
    coordinator = approval.ReviewCoordinator(1)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._running = True
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    bridge = SocketBridge(
        host="127.0.0.1",
        port=port,
        client_id="alice",
        signer=lambda message: hmac.digest(secret, message, "sha256"),
    )
    other = SocketBridge(
        host="127.0.0.1",
        port=port,
        client_id="alice",
        signer=lambda message: hmac.digest(secret, message, "sha256"),
    )
    try:
        await bridge.connect()
        response = await bridge._send_request("review_begin", {"code": "print(1)"})
        review_id = response["review_id"]
        request = coordinator.next_review()
        assert request is not None
        await bridge.disconnect()
        assert (
            await asyncio.wait_for(asyncio.to_thread(request.wait_for_decision), 2)
            == approval.ApprovalState.DENIED
        )
        assert not request.decide(approved=True)
        assert coordinator.next_execution() is None
        await bridge.connect()
        result = await bridge._send_request("review_commit", {"review_id": review_id})
        assert result == {"scheduled": False}

        response2 = await bridge._send_request("review_begin", {"code": "print(2)"})
        request2 = coordinator.next_review()
        assert request2 is not None and request2.decide(approved=True)
        await other.connect()
        assert not (
            await other._send_request(
                "review_commit", {"review_id": response2["review_id"]}
            )
        )["scheduled"]
        assert (
            await bridge._send_request(
                "review_commit", {"review_id": response2["review_id"]}
            )
        )["scheduled"]
        await bridge.disconnect()
        async with asyncio.timeout(2):
            while request2.state == approval.ApprovalState.APPROVED:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
        assert coordinator.next_execution() is None
    finally:
        await bridge.disconnect()
        await other.disconnect()
        coordinator.close()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_xmlrpc_does_not_expose_unbound_review_methods(server_mod: Any) -> None:
    """XML-RPC cannot bypass session ownership with experimental review calls."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", xmlrpc_port=0, authenticator=authenticator
    )
    plugin._execute_via_queue = MagicMock(
        return_value={"success": True, "result": True}
    )
    plugin._running = True
    thread = threading.Thread(target=plugin._run_xmlrpc_server)
    thread.start()
    bridge = None
    try:
        assert await asyncio.to_thread(plugin._listener_ready["xmlrpc"].wait, 3)
        port = plugin._xmlrpc_server.server_address[1]
        bridge = XmlRpcBridge(
            host="127.0.0.1",
            port=port,
            timeout=2,
            client_id="alice",
            signer=lambda message: hmac.digest(secret, message, "sha256"),
        )
        await bridge.connect()
        with pytest.raises(xmlrpc.client.Fault, match="not supported"):
            await bridge._run_proxy_call(lambda proxy: proxy.review_begin("pass"), 2)
    finally:
        if bridge is not None:
            await bridge.disconnect()
        plugin._running = False
        await asyncio.to_thread(thread.join, 3)
        if plugin._xmlrpc_server is not None:
            plugin._xmlrpc_server.server_close()
        assert not thread.is_alive()


def test_reviewed_queue_executes_only_claimed_content_and_returns_owner_result(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The GUI queue executes a committed, approved ticket exactly once."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    coordinator = approval.ReviewCoordinator(2)
    broker = approval.LeasedReviewBroker(coordinator, 2)
    plugin._review_broker = broker
    plugin._execute_code_sync = MagicMock(return_value={"success": True, "result": 5})
    payload = approval.ApprovalPayload("execute_python", b"_result_ = 5")
    review_id = broker.begin("alice", payload, 30)
    request = coordinator.next_review()
    assert request is not None
    plugin._process_queue()
    plugin._execute_code_sync.assert_not_called()
    assert request.decide(approved=True)
    plugin._process_queue()
    plugin._execute_code_sync.assert_not_called()
    assert broker.commit("alice", review_id)
    plugin._process_queue()
    plugin._process_queue()
    plugin._execute_code_sync.assert_called_once_with("_result_ = 5")
    assert broker.result("alice", review_id) == {"success": True, "result": 5}
    assert broker.result("bob", review_id) is None
    broker.close()


def test_reviewed_queue_fails_closed_without_gui(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A headless queue cannot run an approved GUI review ticket."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: False)
    console = SimpleNamespace(PrintWarning=MagicMock())
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(
        server_mod, "FreeCAD", SimpleNamespace(Console=console), raising=False
    )
    coordinator = approval.ReviewCoordinator(1)
    broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._review_broker = broker
    plugin._execute_code_sync = MagicMock()
    review_id = broker.begin(
        "alice", approval.ApprovalPayload("execute_python", b"pass"), 30
    )
    assert coordinator.next_review().decide(approved=True)
    assert broker.commit("alice", review_id)
    plugin._process_queue()
    plugin._execute_code_sync.assert_not_called()
    assert broker.result("alice", review_id) is None
    assert plugin._review_broker is None
    response = plugin._review_request(1, "review_begin", {"code": "pass"}, "alice")
    assert response["error"]["message"] == "Local review is unavailable"
    plugin._process_queue()
    console.PrintWarning.assert_called_once_with(
        "MCP Bridge: reviewed execution disabled; GUI thread unavailable.\n"
    )


@pytest.mark.asyncio
async def test_review_preference_bypass_runs_only_on_review_protocol(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local bypass still uses authenticated review and single-use commit."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    policy_module = importlib.import_module("freecad_mcp_bridge.review_policy")
    dialog = importlib.import_module("freecad_mcp_bridge.review_dialog")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=authenticator
    )
    plugin._running = True
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    plugin._execute_code_sync = MagicMock(return_value={"success": True, "result": 42})
    coordinator = approval.ReviewCoordinator(1)
    policy = policy_module.ReviewPolicy()
    policy.configure("execute_python", require_review=False)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._review_controller = dialog.ReviewDialogController(
        coordinator, policy=policy
    )
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    bridge = SocketBridge(
        host="127.0.0.1",
        port=port,
        client_id="alice",
        signer=lambda message: hmac.digest(secret, message, "sha256"),
    )

    async def process_queue() -> None:
        while True:
            plugin._process_queue()
            await asyncio.sleep(0.005)

    worker = asyncio.create_task(process_queue())
    try:
        result = await bridge.execute_reviewed_python("_result_ = 42")
        assert result.success and result.result == 42
        plugin._execute_code_sync.assert_called_once_with("_result_ = 42")
    finally:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        plugin._review_controller.close()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_oversized_review_is_rejected_before_dispatch(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An oversized authenticated review never reaches the local broker."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=authenticator
    )
    plugin._running = True
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    plugin._execute_code_sync = MagicMock()
    coordinator = approval.ReviewCoordinator(1)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]
    bridge = SocketBridge(
        host="127.0.0.1",
        port=port,
        client_id="alice",
        signer=lambda message: hmac.digest(secret, message, "sha256"),
    )
    try:
        await bridge.connect()
        result = await bridge.execute_reviewed_python("x" * 50_000)
        assert not result.success
        assert result.error_type == "ReviewUnavailable"
        assert "socket frame limit" in result.stderr
        assert coordinator.next_review() is None
        plugin._execute_code_sync.assert_not_called()
        assert await bridge.ping() >= 0
    finally:
        await bridge.disconnect()
        coordinator.close()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_socket_reviewed_execution_returns_result_only_to_same_session(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An authenticated review result remains bound to its socket session."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=authenticator
    )
    plugin._running = True
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    plugin._execute_code_sync = MagicMock(return_value={"success": True, "result": 5})
    coordinator = approval.ReviewCoordinator(1)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]

    def signer(message: bytes) -> bytes:
        return hmac.digest(secret, message, "sha256")

    first = SocketBridge(host="127.0.0.1", port=port, client_id="alice", signer=signer)
    second = SocketBridge(host="127.0.0.1", port=port, client_id="alice", signer=signer)
    try:
        await first.connect()
        await second.connect()
        review_id = (
            await first._send_request("review_begin", {"code": "_result_ = 5"})
        )["review_id"]
        request = coordinator.next_review()
        assert request.decide(approved=True)
        assert (await first._send_request("review_commit", {"review_id": review_id}))[
            "scheduled"
        ]
        plugin._process_queue()
        plugin._execute_code_sync.assert_called_once_with("_result_ = 5")
        assert (await second._send_request("review_result", {"review_id": review_id}))[
            "result"
        ] is None
        assert (await first._send_request("review_result", {"review_id": review_id}))[
            "result"
        ] == {"success": True, "result": 5}
    finally:
        await first.disconnect()
        await second.disconnect()
        coordinator.close()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


def test_experimental_review_refuses_unavailable_gui(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A headless or stopped bridge cannot enable local GUI approval."""
    plugin = server_mod.FreecadMCPPlugin()
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: False)
    with pytest.raises(RuntimeError, match="running GUI queue"):
        plugin._enable_experimental_review()
    plugin._running = True
    plugin._timer = MagicMock()
    with pytest.raises(RuntimeError, match="running GUI queue"):
        plugin._enable_experimental_review()
    assert plugin._review_broker is None
    plugin._timer = None
    plugin._running = False


@pytest.mark.parametrize("gui", [True, False])
def test_test_instance_marker_uses_informational_gui_output(
    server_mod: Any,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gui: bool,
) -> None:
    """The test marker is informational in GUI and remains on stderr headlessly."""
    console = MagicMock()
    monkeypatch.setenv("FREECAD_MCP_TESTING", "1")
    monkeypatch.setattr(server_mod, "FREECAD_AVAILABLE", True)
    monkeypatch.setattr(
        server_mod,
        "FreeCAD",
        SimpleNamespace(GuiUp=gui, Console=console),
        raising=False,
    )
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: False)
    plugin = server_mod.FreecadMCPPlugin(authenticator=MagicMock())
    plugin._start_queue_processor = MagicMock()
    plugin._start_status_updates = MagicMock()
    plugin._launch_listeners = MagicMock()
    plugin._await_listeners = MagicMock(return_value={})
    plugin._report_started = MagicMock()
    try:
        plugin.start()
        marker = f"FREECAD_MCP_BRIDGE_INSTANCE_ID={plugin.instance_id}"
        if gui:
            console.PrintMessage.assert_any_call(marker + "\n")
            assert marker not in capsys.readouterr().err
        else:
            assert marker in capsys.readouterr().err
    finally:
        plugin.stop()


def test_review_setup_failure_leaves_regular_bridge_available(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A review setup error disables review without disabling modeling."""
    plugin = server_mod.FreecadMCPPlugin(authenticator=MagicMock())
    plugin._timer = MagicMock()
    plugin._start_queue_processor = MagicMock()
    plugin._start_status_updates = MagicMock()
    plugin._stop_status_updates = MagicMock()
    plugin._launch_listeners = MagicMock()
    plugin._await_listeners = MagicMock(return_value={})
    plugin._report_started = MagicMock()
    plugin._enable_experimental_review = MagicMock(side_effect=RuntimeError("Qt"))
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    try:
        plugin.start()
        assert plugin.is_running
        assert plugin._review_broker is None
        plugin._launch_listeners.assert_called_once()
        response = plugin._review_request(1, "review_begin", {"code": "pass"}, "alice")
        assert response["error"]["message"] == "Local review is unavailable"
    finally:
        plugin.stop()


def test_experimental_review_stop_cancels_pending_requests(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping on the GUI thread closes the broker and denies pending review."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    review_dialog = importlib.import_module("freecad_mcp_bridge.review_dialog")
    monkeypatch.setattr(
        review_dialog, "create_close_relay", lambda _controller: MagicMock()
    )
    plugin._running = True
    plugin._timer = MagicMock()
    plugin._stop_status_updates = MagicMock()
    plugin._enable_experimental_review()
    broker = plugin._review_broker
    review_id = broker.begin(
        "alice", approval.ApprovalPayload("execute_python", b"pass"), 30
    )
    plugin.stop()
    assert broker.status("alice", review_id) is None
    assert not broker.commit("alice", review_id)
    assert plugin._review_controller is None
    assert plugin._review_broker is None
    plugin._running = True
    plugin._timer = MagicMock()
    plugin._enable_experimental_review()
    assert plugin._review_broker is not broker
    plugin.stop()


@pytest.mark.asyncio
async def test_reviewed_macro_executes_captured_bytes(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file replacement after approval cannot change the executed macro."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    plugin._macro_review_roots = (str(tmp_path),)
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    coordinator = approval.ReviewCoordinator(1)
    broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._review_broker = broker
    macro = tmp_path / "example.FCMacro"
    macro.write_bytes(b"_result_ = value + 1\n")
    response = await plugin._review_begin_macro(
        1, {"macro_name": "example", "args": {"value": 41}}, "alice"
    )
    review_id = response["result"]["review_id"]
    request = coordinator.next_review()
    assert request.payload.content == b"_result_ = value + 1\n"
    assert request.decide(approved=True)
    macro.write_bytes(b"_result_ = 999\n")
    assert broker.commit("alice", review_id)
    plugin._process_reviewed_queue()
    assert broker.result("alice", review_id)["result"] == 42
    broker.close()


@pytest.mark.asyncio
async def test_reviewed_macro_rejects_reserved_argument(
    server_mod: Any, tmp_path: Path
) -> None:
    """An argument cannot replace the execution environment or built-ins."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._macro_review_roots = (str(tmp_path),)
    coordinator = approval.ReviewCoordinator(1)
    plugin._review_broker = approval.LeasedReviewBroker(coordinator, 1)
    (tmp_path / "example.FCMacro").write_text("_result_ = 42\n")
    response = await plugin._review_begin_macro(
        1, {"macro_name": "example", "args": {"__builtins__": {}}}, "alice"
    )
    assert "error" in response
    assert coordinator.next_review() is None
    valid = await plugin._review_begin_macro(
        2, {"macro_name": "example", "args": {}}, "alice"
    )
    assert "review_id" in valid["result"]
    plugin._review_broker.close()


@pytest.mark.asyncio
async def test_socket_reviewed_macro_uses_authenticated_session(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Only the requesting session can commit its reviewed macro snapshot."""
    auth = importlib.import_module("freecad_mcp_bridge.authentication")
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    secret = b"a" * 32
    authenticator = auth.BridgeAuthenticator(
        auth.create_hmac_verifier(lambda client: secret if client == "alice" else None)
    )
    plugin = server_mod.FreecadMCPPlugin(
        host="127.0.0.1", port=0, authenticator=authenticator
    )
    plugin._running = True
    plugin._macro_review_roots = (str(tmp_path),)
    (tmp_path / "example.FCMacro").write_bytes(b"_result_ = value\n")
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    coordinator = approval.ReviewCoordinator(1)
    broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._review_broker = broker
    await plugin._start_socket_server()
    port = plugin._socket_server.sockets[0].getsockname()[1]

    def signer(message: bytes) -> bytes:
        return hmac.digest(secret, message, "sha256")

    first = SocketBridge(host="127.0.0.1", port=port, client_id="alice", signer=signer)
    second = SocketBridge(host="127.0.0.1", port=port, client_id="alice", signer=signer)
    try:
        await first.connect()
        await second.connect()
        review_id = (
            await first._send_request(
                "review_begin_macro", {"macro_name": "example", "args": {"value": 42}}
            )
        )["review_id"]
        request = coordinator.next_review()
        assert request.decide(approved=True)
        assert not (
            await second._send_request("review_commit", {"review_id": review_id})
        )["scheduled"]
        assert (await first._send_request("review_commit", {"review_id": review_id}))[
            "scheduled"
        ]
        plugin._process_queue()
        assert (await first._send_request("review_result", {"review_id": review_id}))[
            "result"
        ]["result"] == 42
    finally:
        await first.disconnect()
        await second.disconnect()
        broker.close()
        plugin._running = False
        plugin._socket_server.close()
        await plugin._socket_server.wait_closed()


@pytest.mark.asyncio
async def test_reviewed_macro_executes_displayed_utf8_text(
    server_mod: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An encoding cookie cannot turn displayed comments into hidden code."""
    approval = importlib.import_module("freecad_mcp_bridge.approval")
    plugin = server_mod.FreecadMCPPlugin()
    plugin._running = True
    plugin._macro_review_roots = (str(tmp_path),)
    monkeypatch.setattr(server_mod, "_review_gui_thread_ready", lambda: True)
    coordinator = approval.ReviewCoordinator(1)
    broker = approval.LeasedReviewBroker(coordinator, 1)
    plugin._review_broker = broker
    (tmp_path / "example.FCMacro").write_bytes(
        b"# coding: unicode_escape\r\n# harmless\\u000a_result_ = 999\r\n"
        b'if __name__ == "__main__" and "_result_" not in globals():\r\n'
        b"    _result_ = 42\r\n"
    )
    response = await plugin._review_begin_macro(
        1, {"macro_name": "example", "args": {}}, "alice"
    )
    review_id = response["result"]["review_id"]
    assert coordinator.next_review().decide(approved=True)
    assert broker.commit("alice", review_id)
    plugin._process_reviewed_queue()
    result = broker.result("alice", review_id)
    assert result["success"] and result["result"] == 42
    broker.close()
