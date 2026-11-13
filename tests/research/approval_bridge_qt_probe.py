"""Run an isolated reviewed socket execution through a real offscreen Qt loop.

This uses a synthetic FreeCAD module, not an installed FreeCAD host. It starts
and stops its own authenticated loopback listener and never uses user documents.
"""

import asyncio
import hmac
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

from PySide6 import QtCore, QtWidgets

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "freecad" / "RobustMCPBridge"
sys.path.insert(0, str(ADDON))
freecad = ModuleType("FreeCAD")
freecad.GuiUp = True  # type: ignore[attr-defined]
freecad.Console = SimpleNamespace(  # type: ignore[attr-defined]
    PrintMessage=lambda *_: None,
    PrintWarning=lambda *_: None,
    PrintError=lambda message: print(message, file=sys.stderr),
)
sys.modules["FreeCAD"] = freecad

from freecad_mcp_bridge.authentication import (  # noqa: E402
    BridgeAuthenticator,
    create_hmac_verifier,
)
from freecad_mcp_bridge.server import FreecadMCPPlugin  # noqa: E402

from freecad_mcp.bridge.socket import SocketBridge  # noqa: E402
from freecad_mcp.tools.execution import register_execution_tools  # noqa: E402


async def exercise(port: int, secret: bytes, shown: threading.Event) -> None:
    """Run approval and denial flows without executing user-provided content."""
    bridge = SocketBridge(
        host="127.0.0.1",
        port=port,
        client_id="probe",
        signer=lambda message: hmac.digest(secret, message, "sha256"),
    )
    try:
        await bridge.connect()
        tools = {}

        class ToolRegistry:
            def tool(self, **_kwargs):
                def register(func):
                    tools[func.__name__] = func
                    return func

                return register

        async def get_bridge():
            return bridge

        register_execution_tools(ToolRegistry(), get_bridge, allow_unsafe_code=True)
        approved = await tools["execute_python"]("_result_ = 42", 5000)
        assert approved["success"] and approved["result"] == 42
        denied = await tools["execute_python"]("_result_ = 99", 5000)
        assert not denied["success"] and "denied" in denied["stderr"]
        cancelled = asyncio.create_task(
            tools["execute_python"]("FreeCAD.cancelled_probe = True", 5000)
        )
        if not await asyncio.to_thread(shown.wait, 5):
            raise RuntimeError("Cancellation review was not shown")
        cancelled.cancel()
        try:
            await cancelled
        except asyncio.CancelledError:
            pass
        else:
            raise RuntimeError("Pending review did not propagate cancellation")
        assert await bridge.ping() >= 0
    finally:
        await bridge.disconnect()


async def exercise_production_http(  # noqa: PLR0912
    port: int, secret: bytes, plugin: Any, shown: threading.Event
) -> None:
    """Exercise the production HTTP authentication and guarded tool together."""
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.types import TextContent

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        http_port = listener.getsockname()[1]
    key = "test-only-key-0123456789abcdef0123456789"
    env = {
        **os.environ,
        "FREECAD_MODE": "socket",
        "FREECAD_SOCKET_HOST": "127.0.0.1",
        "FREECAD_SOCKET_PORT": str(port),
        "FREECAD_BRIDGE_CLIENT_ID": "probe",
        "FREECAD_BRIDGE_SECRET": secret.hex(),
        "FREECAD_TRANSPORT": "http",
        "FREECAD_HTTP_HOST": "127.0.0.1",
        "FREECAD_HTTP_PORT": str(http_port),
        "FREECAD_HTTP_API_KEY": key,
        "FREECAD_ALLOW_UNSAFE_CODE": "true",
    }
    script = ROOT / "tests" / "fixtures" / "authenticated_mcp_server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if process.returncode is not None:
                raise RuntimeError("Production MCP HTTP server exited during startup")
            try:
                _reader, writer = await asyncio.open_connection("127.0.0.1", http_port)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise RuntimeError("Production MCP HTTP server did not start")
        url = f"http://127.0.0.1:{http_port}/mcp"
        async with httpx2.AsyncClient() as http:
            if (await http.post(url)).status_code != 401:
                raise RuntimeError("Production MCP HTTP did not reject a missing key")
            http.headers["Authorization"] = f"Bearer {key}"
            async with streamable_http_client(url, http_client=http) as streams:
                async with ClientSession(*streams[:2]) as session:
                    await session.initialize()
                    for code, expected in (
                        ("_result_ = 42", True),
                        ("FreeCAD.http_denied_probe = True", False),
                    ):
                        result = await session.call_tool(
                            "execute_python", {"code": code}
                        )
                        if (
                            result.is_error
                            or not result.content
                            or not isinstance(result.content[0], TextContent)
                        ):
                            raise RuntimeError("Production MCP HTTP tool call failed")
                        payload = json.loads(result.content[0].text)
                        if payload["success"] is not expected:
                            raise RuntimeError(
                                f"Unexpected production HTTP result: {payload}"
                            )
                    cancelled_code = "FreeCAD.http_cancelled_probe = True"
                    pending = asyncio.create_task(
                        session.call_tool("execute_python", {"code": cancelled_code})
                    )
                    if not await asyncio.to_thread(shown.wait, 5):
                        raise RuntimeError("HTTP cancellation review was not shown")
                    pending.cancel()
                    try:
                        await pending
                    except asyncio.CancelledError:
                        pass
                    else:
                        raise RuntimeError("HTTP tool cancellation did not propagate")
                    async with asyncio.timeout(5):
                        while plugin._review_controller._request is not None:  # noqa: ASYNC110
                            await asyncio.sleep(0.05)
                    after_cancel = await session.call_tool(
                        "execute_python", {"code": "_result_ = 42"}
                    )
                    if (
                        after_cancel.is_error
                        or not after_cancel.content
                        or not isinstance(after_cancel.content[0], TextContent)
                        or json.loads(after_cancel.content[0].text).get("result") != 42
                    ):
                        raise RuntimeError(
                            "HTTP review did not recover after cancellation"
                        )
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()


def main() -> None:
    """Run and clean up the socket listener and Qt event loop."""
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    secret = b"x" * 32
    auth = BridgeAuthenticator(
        create_hmac_verifier(lambda client: secret if client == "probe" else None)
    )
    plugin = FreecadMCPPlugin(
        host="127.0.0.1", port=0, xmlrpc_port=0, authenticator=auth
    )
    timer = None
    thread = None
    try:
        # The synthetic host has no FreeCAD main window for the status widget.
        plugin._start_status_updates = lambda: None
        plugin._stop_status_updates = lambda: None
        plugin.start()
        if plugin._review_broker is None:
            raise RuntimeError("Normal GUI startup did not enable review")
        if (
            not plugin._listener_ready["socket"].wait(5)
            or plugin._socket_server is None
        ):
            raise RuntimeError("Listener failed to start")
        port = plugin._socket_server.sockets[0].getsockname()[1]
        if (
            not plugin._listener_ready["xmlrpc"].wait(5)
            or plugin._xmlrpc_server is None
        ):
            raise RuntimeError("XML-RPC listener failed to start")
        errors: list[BaseException] = []
        finished = threading.Event()
        socket_shown = threading.Event()
        http_shown = threading.Event()

        def worker() -> None:
            try:
                asyncio.run(exercise(port, secret, socket_shown))
                asyncio.run(exercise_production_http(port, secret, plugin, http_shown))
                controller = plugin._review_controller
                plugin._shutdown_review()
                deadline = time.monotonic() + 3
                while not controller._closed and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not controller._closed:
                    raise RuntimeError("Queued Qt review cleanup did not run")
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        seen: set[str] = set()
        deadline = time.monotonic() + 30
        timer = QtCore.QTimer()

        def tick() -> None:
            controller = plugin._review_controller
            if controller is not None and controller._request is not None:
                request = controller._request
                if request.request_id not in seen and controller._dialog is not None:
                    seen.add(request.request_id)
                    if request.payload.content == b"FreeCAD.cancelled_probe = True":
                        socket_shown.set()
                    if (
                        request.payload.content
                        == b"FreeCAD.http_cancelled_probe = True"
                    ):
                        http_shown.set()
                    if request.payload.content in (b"_result_ = 42", b"_result_ = 43"):
                        controller._dialog.accept()
                    elif request.payload.content not in (
                        b"FreeCAD.cancelled_probe = True",
                        b"FreeCAD.http_cancelled_probe = True",
                    ):
                        controller._dialog.reject()
            if finished.is_set() or time.monotonic() >= deadline:
                app.quit()

        timer.timeout.connect(tick)
        timer.start(20)
        app.exec()
    finally:
        if timer is not None:
            timer.stop()
        plugin.stop()
        if thread is not None:
            thread.join(3)
    if thread is not None and thread.is_alive():
        raise RuntimeError("Probe client did not stop")
    if errors:
        raise RuntimeError("Probe client failed") from errors[0]
    if not finished.is_set() or len(seen) != 7:
        raise RuntimeError("Probe timed out or did not show all reviews")
    if hasattr(freecad, "cancelled_probe"):
        raise RuntimeError("Cancelled review executed")
    if hasattr(freecad, "http_denied_probe"):
        raise RuntimeError("Denied HTTP review executed")
    if hasattr(freecad, "http_cancelled_probe"):
        raise RuntimeError("Cancelled HTTP review executed")
    print("Authenticated socket Qt review probe passed")


if __name__ == "__main__":
    main()
